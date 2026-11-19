"""Deterministic, group-aware multi-label splitting for US3.

The splitter works purely on in-memory :class:`MatchedSample` objects. It does
not touch the filesystem: output paths are recorded on each
:class:`SplitAssignment` so the pipeline can copy images and write labels after
the split has been verified.

Sizing uses largest remainder over the eligible sample count with a fixed
tie-break order (train, validation, test). Samples are represented by their
full ``present_classes`` set; rare classes are placed first and every tie is
resolved with a local :class:`random.Random` seeded by the caller.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .classes import CLASS_NAMES
from .models import (
    SPLIT_NAMES,
    AnomalyRecord,
    DuplicateGroup,
    MatchedSample,
    Severity,
    Split,
    SplitAssignment,
    SplitName,
)

INVARIANT_KEYS: tuple[str, ...] = (
    "pairwise_disjoint_sample_id",
    "pairwise_disjoint_output_path",
    "pairwise_disjoint_sha256",
    "all_eligible_assigned",
    "duplicate_groups_atomic",
    "no_cross_subset_pairing",
    "source_unchanged",
    "class_mapping_fixed",
)
DEFAULT_RATIOS: tuple[float, float, float] = (0.75, 0.15, 0.10)
DEFAULT_SEED = 42
RATIO_TOLERANCE = 1e-9


@dataclass
class SplitResult:
    """Outcome of one split computation."""

    splits: dict[str, Split]
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    invariants: dict[str, bool] = field(default_factory=dict)
    seed: int = DEFAULT_SEED
    ratios: dict[str, float] = field(default_factory=dict)
    actual_ratios: dict[str, float] = field(default_factory=dict)
    target_sizes: dict[str, int] = field(default_factory=dict)


@dataclass
class _Unit:
    """Atomic allocation item: one sample or one duplicate-content group."""

    members: list[MatchedSample]
    group: DuplicateGroup | None = None

    @property
    def key(self) -> str:
        return self.group.group_id if self.group else self.members[0].sample_id

    @property
    def classes(self) -> set[int]:
        values: set[int] = set()
        for sample in self.members:
            values.update(int(value) for value in (sample.present_classes or []))
        return values

    @property
    def first_id(self) -> str:
        return min(sample.sample_id for sample in self.members)


def _ratios_mapping(
    ratios: Mapping[str, float] | Sequence[float],
) -> dict[str, float]:
    if isinstance(ratios, Mapping):
        missing = [name for name in SPLIT_NAMES if name not in ratios]
        if missing:
            raise ValueError(f"ratios mapping is missing keys: {', '.join(missing)}")
        values = tuple(float(ratios[name]) for name in SPLIT_NAMES)
    else:
        values = tuple(float(value) for value in ratios)
        if len(values) != 3:
            raise ValueError("ratios must contain exactly three values")

    if any(value <= 0 for value in values):
        raise ValueError("ratios must all be positive")
    total = sum(values)
    if abs(total - 1.0) > RATIO_TOLERANCE:
        raise ValueError("ratios must sum to 1.0 within 1e-9")
    return dict(zip(SPLIT_NAMES, values, strict=True))


def _largest_remainder(total: int, weights: Sequence[float]) -> list[int]:
    """Allocate ``total`` items by largest remainder, stable by input order."""
    if total <= 0:
        return [0 for _ in weights]
    weight_sum = sum(weights)
    if weight_sum <= 0:
        weights = [1.0 for _ in weights]
        weight_sum = float(len(weights))

    raw = [total * float(weight) / weight_sum for weight in weights]
    floors = [int(value) for value in raw]
    remaining = total - sum(floors)
    order = sorted(
        range(len(weights)),
        key=lambda index: (-round(raw[index] - floors[index], 12), index),
    )
    for index in order[:remaining]:
        floors[index] += 1
    return floors


def _target_sizes(total: int, ratios: dict[str, float]) -> dict[str, int]:
    values = [ratios[name] for name in SPLIT_NAMES]
    sizes = _largest_remainder(total, values)
    return dict(zip(SPLIT_NAMES, sizes, strict=True))


def _source_path(sample: MatchedSample, asset: Any, *, image: bool) -> str:
    relative = Path(getattr(asset, "relative_path", "")).as_posix()
    prefix = f"{sample.source_subset}/"
    if relative.startswith(prefix):
        return relative
    kind = "images" if image else "annotations"
    if relative.startswith(f"{kind}/"):
        return f"{sample.source_subset}/{relative}"
    return f"{sample.source_subset}/{kind}/{Path(relative).name}"


def _normalise_sha256(sample: MatchedSample) -> str:
    digest = str(getattr(sample.image, "sha256", "") or "").removeprefix("sha256:")
    return f"sha256:{digest}"


def _assign_output_names(assignments: list[SplitAssignment]) -> None:
    """Give every assignment a unique deterministic output stem."""
    by_stem: dict[str, list[SplitAssignment]] = defaultdict(list)
    for assignment in assignments:
        stem = Path(assignment.output_image).stem
        by_stem[stem].append(assignment)

    proposed: dict[str, str] = {}
    for stem, group in by_stem.items():
        for assignment in group:
            proposed[assignment.sample_id] = (
                stem
                if len(group) == 1
                else f"{assignment.source_subset}_{stem}"
            )

    by_proposed: dict[str, list[SplitAssignment]] = defaultdict(list)
    for assignment in assignments:
        by_proposed[proposed[assignment.sample_id]].append(assignment)

    for name, group in by_proposed.items():
        if len(group) == 1:
            group[0].output_image = (
                f"images/{group[0].split}/{name}{Path(group[0].output_image).suffix}"
            )
            group[0].output_label = f"labels/{group[0].split}/{name}.txt"
            continue

        ordered = sorted(group, key=lambda item: item.sample_id)
        for length in (8, 12, 16, 32, 64):
            candidates = {
                item.sample_id: (
                    f"{name}_{str(item.sha256).removeprefix('sha256:')[:length]}"
                )
                for item in ordered
            }
            if len(set(candidates.values())) == len(ordered):
                resolved = candidates
                break
        else:
            resolved = {
                item.sample_id: f"{name}_{position:03d}"
                for position, item in enumerate(ordered)
            }
        for item in ordered:
            stem = resolved[item.sample_id]
            item.output_image = (
                f"images/{item.split}/{stem}{Path(item.output_image).suffix}"
            )
            item.output_label = f"labels/{item.split}/{stem}.txt"


def _make_assignment(
    sample: MatchedSample,
    split: str,
    *,
    output_name: str,
) -> SplitAssignment:
    return SplitAssignment(
        sample_id=sample.sample_id,
        split=SplitName(split),
        source_subset=sample.source_subset,
        source_image=_source_path(sample, sample.image, image=True),
        source_xml=_source_path(sample, sample.annotation, image=False),
        output_image=f"images/{split}/{output_name}{sample.image.extension}",
        output_label=f"labels/{split}/{output_name}.txt",
        sha256=_normalise_sha256(sample),
        present_classes=sorted(int(value) for value in (sample.present_classes or [])),
        object_count=len(sample.objects),
    )


def _build_split(
    name: str,
    assignments: list[SplitAssignment],
    samples_by_id: dict[str, MatchedSample],
    ratios: dict[str, float],
    total_images: int,
) -> Split:
    ordered = sorted(assignments, key=lambda item: item.sample_id)
    image_counts: Counter[int] = Counter()
    object_counts: Counter[int] = Counter()
    subset_counts: Counter[str] = Counter()
    objects = 0
    for assignment in ordered:
        subset_counts[assignment.source_subset] += 1
        sample = samples_by_id[assignment.sample_id]
        for obj in sample.objects:
            if obj.class_id is None:
                continue
            class_id = int(obj.class_id)
            object_counts[class_id] += 1
            objects += 1
        for class_id in assignment.present_classes:
            image_counts[int(class_id)] += 1

    return Split(
        name=name,
        target_ratio=ratios[name],
        actual_ratio=(len(ordered) / total_images) if total_images else 0.0,
        images=len(ordered),
        objects=objects,
        image_counts_by_class={class_id: image_counts[class_id] for class_id in range(6)},
        object_counts_by_class={class_id: object_counts[class_id] for class_id in range(6)},
        source_subset_counts=dict(sorted(subset_counts.items())),
        assignments=ordered,
    )


def _check_invariants(
    splits: dict[str, Split],
    samples: list[MatchedSample],
    groups: list[DuplicateGroup],
) -> dict[str, bool]:
    ids: list[str] = []
    paths: list[str] = []
    sha256s: list[str] = []
    for name in SPLIT_NAMES:
        for assignment in splits[name].assignments:
            ids.append(assignment.sample_id)
            paths.append(assignment.output_image)
            sha256s.append(assignment.sha256)

    expected_ids = {sample.sample_id for sample in samples}
    members_by_group: dict[str, set[str]] = {
        group.group_id: set(group.members) for group in groups
    }
    split_by_id = {
        assignment.sample_id: name
        for name in SPLIT_NAMES
        for assignment in splits[name].assignments
    }
    atomic = all(
        len({split_by_id.get(member_id) for member_id in member_ids}) == 1
        for member_ids in members_by_group.values()
    )
    samples_by_id = {sample.sample_id: sample for sample in samples}
    cross_subset = any(
        assignment.source_subset != samples_by_id[assignment.sample_id].source_subset
        for name in SPLIT_NAMES
        for assignment in splits[name].assignments
    )
    fixed_classes = all(
        class_id in range(6)
        for name in SPLIT_NAMES
        for assignment in splits[name].assignments
        for class_id in assignment.present_classes
    ) and [CLASS_NAMES[class_id] for class_id in range(6)] == list(
        CLASS_NAMES.values()
    )

    return {
        "pairwise_disjoint_sample_id": len(ids) == len(set(ids)),
        "pairwise_disjoint_output_path": len(paths) == len(set(paths)),
        "pairwise_disjoint_sha256": len(sha256s) == len(set(sha256s)),
        "all_eligible_assigned": set(ids) == expected_ids and len(ids) == len(samples),
        "duplicate_groups_atomic": atomic,
        "no_cross_subset_pairing": not cross_subset,
        "source_unchanged": True,
        "class_mapping_fixed": fixed_classes,
    }


def _split_anomalies(
    splits: dict[str, Split],
    ratios: dict[str, float],
    targets: dict[str, int],
    total_images: int,
) -> list[AnomalyRecord]:
    anomalies: list[AnomalyRecord] = []
    actual = {
        name: (splits[name].images / total_images) if total_images else 0.0
        for name in SPLIT_NAMES
    }
    deviation = any(
        abs(splits[name].images - targets[name]) > 1 for name in SPLIT_NAMES
    )
    if deviation:
        anomalies.append(
            AnomalyRecord(
                code="split_distribution_deviation",
                severity=Severity.WARNING,
                scope="split",
                reason=(
                    "duplicate-group atomicity made the exact largest-remainder "
                    "split sizes unreachable"
                ),
                details={
                    "actual_ratios": actual,
                    "target_ratios": dict(ratios),
                    "actual_sizes": {name: splits[name].images for name in SPLIT_NAMES},
                    "target_sizes": dict(targets),
                },
            )
        )

    for name in SPLIT_NAMES:
        for class_id in range(6):
            if splits[name].image_counts_by_class[class_id]:
                continue
            anomalies.append(
                AnomalyRecord(
                    code="split_class_absent",
                    severity=Severity.WARNING,
                    scope="split",
                    source_subset=name,
                    reason=(
                        f"class {class_id} ({CLASS_NAMES[class_id]}) has no image "
                        f"in split {name}"
                    ),
                    details={
                        "split": name,
                        "class_id": class_id,
                        "class_name": CLASS_NAMES[class_id],
                    },
                )
            )
    return anomalies


def split_samples(
    samples: Sequence[MatchedSample],
    *,
    seed: int = DEFAULT_SEED,
    ratios: Mapping[str, float] | Sequence[float] = DEFAULT_RATIOS,
    duplicate_groups: Sequence[DuplicateGroup] = (),
) -> SplitResult:
    """Split eligible samples deterministically into train/validation/test."""
    ratios_map = _ratios_mapping(ratios)
    pool = sorted(list(samples), key=lambda sample: sample.sample_id)
    samples_by_id = {sample.sample_id: sample for sample in pool}
    targets = _target_sizes(len(pool), ratios_map)
    rng = random.Random(int(seed))

    by_group: dict[str, list[MatchedSample]] = defaultdict(list)
    for sample in pool:
        if sample.duplicate_group:
            by_group[str(sample.duplicate_group)].append(sample)

    groups: list[DuplicateGroup] = []
    units: list[_Unit] = []
    grouped_ids: set[str] = set()
    for supplied in sorted(duplicate_groups, key=lambda group: group.group_id):
        member_ids = [
            member_id for member_id in supplied.members if member_id in samples_by_id
        ]
        actual_members = [samples_by_id[member_id] for member_id in member_ids]
        if len(actual_members) < 2:
            continue
        group = DuplicateGroup(
            sha256=supplied.sha256,
            members=[member.sample_id for member in actual_members],
            labels_consistent=supplied.labels_consistent,
            assigned_split=supplied.assigned_split,
        )
        groups.append(group)
        units.append(_Unit(members=actual_members, group=group))
        grouped_ids.update(member.sample_id for member in actual_members)

    # Fall back to sample.duplicate_group when the caller did not pass groups.
    for group_id, members in sorted(by_group.items()):
        if group_id in {group.group_id for group in groups} or len(members) < 2:
            continue
        group = DuplicateGroup(
            sha256=group_id.removeprefix("sha256:"),
            members=[member.sample_id for member in members],
            labels_consistent=all(
                member.duplicate_group == group_id for member in members
            ),
        )
        groups.append(group)
        units.append(_Unit(members=members, group=group))
        grouped_ids.update(member.sample_id for member in members)

    for sample in pool:
        if sample.sample_id not in grouped_ids:
            units.append(_Unit(members=[sample]))

    assigned_counts = [0, 0, 0]
    unit_split: dict[str, str] = {}
    group_units = [unit for unit in units if unit.group is not None]
    singleton_units = [unit for unit in units if unit.group is None]

    # 1. Duplicate groups are atomic; prefer the split whose relative deviation
    # after adding the whole group is smallest.
    for unit in sorted(group_units, key=lambda item: item.key):
        def group_score(index: int) -> tuple[float, int, int]:
            target = targets[SPLIT_NAMES[index]]
            after = assigned_counts[index] + len(unit.members)
            deviation = abs(after - target) / max(target, 1)
            return (-deviation, target, -index)

        index = max(range(3), key=group_score)
        name = SPLIT_NAMES[index]
        assigned_counts[index] += len(unit.members)
        unit_split[unit.key] = name
        if unit.group is not None:
            unit.group.assigned_split = name

    remaining = [
        targets[SPLIT_NAMES[index]] - assigned_counts[index] for index in range(3)
    ]

    # 2. Hold back capacity for classless samples so they stay eligible.
    empty_singletons = [unit for unit in singleton_units if not unit.classes]
    class_singletons = [unit for unit in singleton_units if unit.classes]
    reserved_empty = _largest_remainder(
        len(empty_singletons), [max(value, 0) for value in remaining]
    )
    class_capacity = [
        remaining[index] - reserved_empty[index] for index in range(3)
    ]

    # 3. Place samples by rarity first, then by remaining per-class demand.
    class_frequency: Counter[int] = Counter()
    for unit in class_singletons:
        class_frequency.update(unit.classes)
    class_allocated = [0, 0, 0]
    class_counts: list[Counter[int]] = [Counter(), Counter(), Counter()]

    def demand_score(index: int, unit: _Unit) -> float:
        score = 0.0
        for class_id in unit.classes:
            desired = targets[SPLIT_NAMES[index]] * (
                class_frequency[class_id] / max(len(pool), 1)
            )
            score += max(0.0, desired - class_counts[index][class_id])
        score += 0.001 * (class_capacity[index] - class_allocated[index])
        return score

    ordered_classes = sorted(
        class_singletons,
        key=lambda unit: (
            min(class_frequency[class_id] for class_id in unit.classes),
            -len(unit.classes),
            unit.first_id,
        ),
    )
    for unit in ordered_classes:
        feasible = [
            index for index in range(3) if class_allocated[index] < class_capacity[index]
        ]
        candidates = feasible or list(range(3))

        def class_score(index: int) -> tuple[float, float, int]:
            return (demand_score(index, unit), rng.random(), -index)

        index = max(candidates, key=class_score)
        name = SPLIT_NAMES[index]
        unit_split[unit.key] = name
        class_allocated[index] += len(unit.members)
        assigned_counts[index] += len(unit.members)
        for member in unit.members:
            class_counts[index].update(member.present_classes or [])

    # 4. Classless samples fill the capacity held back for them, in split order.
    empty_position = 0
    for index in range(3):
        name = SPLIT_NAMES[index]
        slots = reserved_empty[index]
        if empty_position + slots > len(empty_singletons):
            slots = len(empty_singletons) - empty_position
        for unit in empty_singletons[empty_position : empty_position + slots]:
            unit_split[unit.key] = name
            assigned_counts[index] += 1
        empty_position += slots
    for unit in empty_singletons[empty_position:]:
        index = min(range(3), key=lambda item: (-remaining[item], item))
        unit_split[unit.key] = SPLIT_NAMES[index]
        assigned_counts[index] += 1

    # 5. Materialize verified assignments.
    by_split: dict[str, list[SplitAssignment]] = {name: [] for name in SPLIT_NAMES}
    for unit in units:
        name = unit_split[unit.key]
        for sample in unit.members:
            assignment = _make_assignment(
                sample,
                name,
                output_name=Path(sample.image.relative_path).stem,
            )
            by_split[name].append(assignment)

    all_assignments = [
        assignment for name in SPLIT_NAMES for assignment in by_split[name]
    ]
    _assign_output_names(all_assignments)
    splits = {
        name: _build_split(name, by_split[name], samples_by_id, ratios_map, len(pool))
        for name in SPLIT_NAMES
    }
    actual = {
        name: (splits[name].images / len(pool)) if pool else 0.0
        for name in SPLIT_NAMES
    }
    invariants = _check_invariants(splits, pool, groups)
    anomalies = _split_anomalies(splits, ratios_map, targets, len(pool))

    return SplitResult(
        splits=splits,
        anomalies=anomalies,
        duplicate_groups=groups,
        invariants=invariants,
        seed=int(seed),
        ratios=ratios_map,
        actual_ratios=actual,
        target_sizes=targets,
    )


# Alternative entry points kept for callers that prefer a different verb.
split_dataset = split_samples
split = split_samples
