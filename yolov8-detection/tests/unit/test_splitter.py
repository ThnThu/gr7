"""Unit tests for the US3 splitter (T025).

These tests use in-memory :class:`MatchedSample` objects only: no image files
are created and no real dataset is touched. They are written before the
splitter exists, so they fail with an explicit "not implemented yet" message
until T028/T029 land.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from detection.data.models import (
    SPLIT_NAMES,
    AnnotationAsset,
    AnnotationStatus,
    DuplicateGroup,
    ImageAsset,
    ImageStatus,
    MatchedSample,
    SampleState,
    Severity,
)


def _split_samples() -> Any:
    """Return the future splitter entry point (fails clearly while missing)."""
    try:
        module = importlib.import_module("detection.data.splitter")
    except ModuleNotFoundError as exc:
        pytest.fail(f"US3 splitter is not implemented yet: {exc}")
    for name in ("split_samples", "split_dataset", "split"):
        entry = getattr(module, name, None)
        if callable(entry):
            return entry
    pytest.fail("detection.data.splitter has no split entry point yet")


def _sample(
    index: int,
    *,
    subset: str = "train",
    classes: Sequence[int] = (),
    sha256: str | None = None,
) -> MatchedSample:
    stem = f"s{index:04d}"
    return MatchedSample(
        sample_id=f"{subset}/{stem}",
        source_subset=subset,
        image=ImageAsset(
            asset_id=f"{subset}/images/{stem}.jpg",
            subset=subset,
            relative_path=Path(f"images/{stem}.jpg"),
            stem=stem,
            extension=".jpg",
            sha256=f"sha256:{sha256 or f'{index:064x}'}",
            status=ImageStatus.VALID,
        ),
        annotation=AnnotationAsset(
            asset_id=f"{subset}/annotations/{stem}.xml",
            subset=subset,
            relative_path=Path(f"annotations/{stem}.xml"),
            stem=stem,
            status=AnnotationStatus.VALID,
        ),
        state=SampleState.ELIGIBLE,
        present_classes=list(classes),
        label_lines=[],
    )


def _assignments(result: Any, split: str) -> list[Any]:
    return list(result.splits[split].assignments)


def _ids_by_split(result: Any) -> dict[str, list[str]]:
    return {
        name: [assignment.sample_id for assignment in _assignments(result, name)]
        for name in SPLIT_NAMES
    }


def _sizes(result: Any) -> tuple[int, int, int]:
    return tuple(len(_assignments(result, name)) for name in SPLIT_NAMES)  # type: ignore[return-value]


def _mentions_class(details: dict[str, Any], class_id: int) -> bool:
    for value in details.values():
        if value == class_id:
            return True
        if isinstance(value, (list, tuple, set)) and class_id in value:
            return True
    return False


def test_1800_samples_split_into_exact_largest_remainder_sizes() -> None:
    samples = [_sample(index) for index in range(1800)]

    result = _split_samples()(samples)

    assert _sizes(result) == (1350, 270, 180)


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (2, (2, 0, 0)),
        (4, (3, 1, 0)),
        (10, (8, 1, 1)),
    ],
)
def test_largest_remainder_tie_break_prefers_train_then_validation(
    count: int, expected: tuple[int, int, int]
) -> None:
    samples = [_sample(index) for index in range(count)]

    result = _split_samples()(samples)

    assert _sizes(result) == expected


def test_same_seed_reproduces_identical_split_lists() -> None:
    samples = [_sample(index, classes=[index % 6]) for index in range(60)]
    split_samples = _split_samples()

    first = split_samples(samples, seed=42)
    second = split_samples(samples, seed=42)

    assert _ids_by_split(first) == _ids_by_split(second)


def test_multi_label_stratification_counts_every_present_class() -> None:
    samples = [
        _sample(index, classes=[index % 6, (index + 2) % 6])
        for index in range(60)
    ]
    by_id = {sample.sample_id: sample for sample in samples}

    result = _split_samples()(samples)

    for name in SPLIT_NAMES:
        expected = {class_id: 0 for class_id in range(6)}
        for assignment in _assignments(result, name):
            for class_id in by_id[assignment.sample_id].present_classes or []:
                expected[class_id] += 1
        assert {
            int(class_id): count
            for class_id, count in result.splits[name].image_counts_by_class.items()
        } == expected


def test_empty_present_classes_stay_eligible_and_are_allocated() -> None:
    samples = [
        _sample(index, classes=[] if index % 10 == 0 else [index % 6])
        for index in range(100)
    ]
    empty_ids = {
        sample.sample_id for sample in samples if not sample.present_classes
    }

    result = _split_samples()(samples)

    assert _sizes(result) == (75, 15, 10)
    written_ids = [
        assignment.sample_id
        for name in SPLIT_NAMES
        for assignment in _assignments(result, name)
    ]
    assert len(written_ids) == len(samples)
    assert empty_ids <= set(written_ids)


def test_duplicate_group_members_stay_in_one_split() -> None:
    digest = "ab" * 32
    group_samples = [
        _sample(index, classes=[0], sha256=digest) for index in range(100, 103)
    ]
    samples = [_sample(index, classes=[0]) for index in range(30)] + group_samples
    member_ids = {sample.sample_id for sample in group_samples}
    group = DuplicateGroup(
        sha256=digest,
        members=sorted(member_ids),
        labels_consistent=True,
    )

    result = _split_samples()(samples, duplicate_groups=[group])

    locations = [
        name
        for name in SPLIT_NAMES
        if any(
            assignment.sample_id in member_ids
            for assignment in _assignments(result, name)
        )
    ]
    assert len(locations) == 1


def test_splits_are_disjoint_by_id_output_path_and_sha256() -> None:
    samples = [_sample(index, classes=[index % 6]) for index in range(60)]

    result = _split_samples()(samples)

    for key in (
        "pairwise_disjoint_sample_id",
        "pairwise_disjoint_output_path",
        "pairwise_disjoint_sha256",
        "all_eligible_assigned",
        "duplicate_groups_atomic",
    ):
        assert result.invariants[key] is True

    for attribute in ("sample_id", "output_image", "sha256"):
        groups = [
            {
                getattr(assignment, attribute)
                for assignment in _assignments(result, name)
            }
            for name in SPLIT_NAMES
        ]
        assert not (groups[0] & groups[1])
        assert not (groups[0] & groups[2])
        assert not (groups[1] & groups[2])


def test_oversized_duplicate_group_records_distribution_deviation() -> None:
    digest = "cd" * 32
    group_samples = [
        _sample(index, classes=[0], sha256=digest) for index in range(200, 280)
    ]
    samples = [_sample(index, classes=[0]) for index in range(20)] + group_samples
    group = DuplicateGroup(
        sha256=digest,
        members=[sample.sample_id for sample in group_samples],
        labels_consistent=True,
    )

    result = _split_samples()(samples, duplicate_groups=[group])

    deviations = [
        anomaly
        for anomaly in result.anomalies
        if anomaly.code == "split_distribution_deviation"
    ]
    assert deviations
    assert deviations[0].severity is Severity.WARNING
    recorded = (
        deviations[0].details.get("actual_ratios")
        or getattr(result, "actual_ratios", None)
        or {
            name: result.splits[name].actual_ratio
            for name in SPLIT_NAMES
        }
    )
    assert recorded
    assert sum(float(value) for value in recorded.values()) == pytest.approx(1.0)

    locations = [
        name
        for name in SPLIT_NAMES
        if any(
            assignment.sample_id in {sample.sample_id for sample in group_samples}
            for assignment in _assignments(result, name)
        )
    ]
    assert len(locations) == 1


def test_missing_class_in_a_split_emits_split_class_absent() -> None:
    samples = [_sample(index, classes=[index % 5]) for index in range(20)]
    samples[0].present_classes = [5]

    result = _split_samples()(samples)

    absent = [
        anomaly
        for anomaly in result.anomalies
        if anomaly.code == "split_class_absent"
    ]
    assert absent
    assert any(_mentions_class(anomaly.details, 5) for anomaly in absent)


@pytest.mark.parametrize(
    "ratios",
    [
        (0.75, 0.15, 0.0),
        (-0.1, 0.6, 0.5),
        (0.5, 0.5, 0.5),
        (0.8, 0.1, 0.05),
    ],
)
def test_non_positive_or_non_summing_ratios_are_rejected(
    ratios: tuple[float, float, float],
) -> None:
    with pytest.raises(ValueError):
        _split_samples()([_sample(0)], ratios=ratios)
