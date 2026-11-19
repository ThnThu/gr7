"""Conversion stage plus US2 gate, quarantine and safe output handling.

The pipeline runs discover -> pair -> validate -> duplicate audit -> gate in
memory before touching the output. All artifacts are assembled in a sibling
``<output>.staging`` directory and only committed after the final report and
verification succeed; an existing dataset is moved to ``<output>.previous``
first so a failing run can never destroy it.

Sample validation and duplicate auditing are delegated to
:mod:`detection.data.validator` and the report is produced by
:mod:`detection.data.manifest`. Source images are copied with
:func:`shutil.copy2`; labels are UTF-8 text with ``\\n`` endings.

Until User Story 3 supplies real split assignments, every converted sample is
written to the interim ``train`` split. This module never writes
``split_manifest.json`` or ``dataset.yaml``.
"""

from __future__ import annotations

import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .discovery import (
    DiscoveryError,
    DiscoveryResult,
    PairingResult,
    compare_fingerprints,
    discover_source,
    fingerprint_source,
    pair_samples,
)
from .manifest import write_validation_report
from .models import (
    AnomalyRecord,
    MatchedSample,
    SampleState,
    Severity,
    SourceFingerprint,
)
from .validator import DuplicateAuditResult, ValidationResult, audit_duplicate_groups, validate_samples

INTERIM_SPLIT = "train"
OWNED_ARTIFACTS = (
    "images",
    "labels",
    "rejected",
    "validation_report.json",
    "split_manifest.json",
)
UNPAIRED_CODES = frozenset({"missing_xml", "missing_image", "ambiguous_pairing"})


class PipelineError(Exception):
    """Blocking data error (CLI exit code 3)."""

    exit_code = 3

    def __init__(
        self,
        message: str,
        *,
        anomalies: list[AnomalyRecord] | None = None,
    ) -> None:
        super().__init__(message)
        self.anomalies = anomalies or []


class PipelineConfigError(PipelineError):
    """Unsafe source/output combination (CLI exit code 2)."""

    exit_code = 2


class PipelineOutputExistsError(PipelineError):
    """Output exists without ``--overwrite`` (CLI exit code 4)."""

    exit_code = 4


class PipelineIOError(PipelineError):
    """Unexpected I/O or post-write verification failure (CLI exit code 5)."""

    exit_code = 5


@dataclass(frozen=True)
class ConversionOptions:
    """Inputs for one conversion run."""

    source: Path
    output: Path
    overwrite: bool = False
    on_anomaly: str = "fail"
    interim_split: str = INTERIM_SPLIT
    seed: int = 42
    ratios: tuple[float, float, float] = (0.75, 0.15, 0.10)


@dataclass
class PipelineResult:
    """Summary of a completed conversion run."""

    output: Path
    split: str
    samples_written: int = 0
    images_written: int = 0
    labels_written: int = 0
    objects_written: int = 0
    present_classes: list[int] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    fingerprint: SourceFingerprint | dict[str, Any] = field(
        default_factory=SourceFingerprint
    )
    quarantined_samples: int = 0
    gate_status: str = "pass"
    report_path: Path | None = None


@dataclass
class _PreparedSample:
    sample: MatchedSample
    source_image: Path
    source_annotation: Path
    sha256: str | None
    label_text: str
    object_count: int
    present_classes: list[int]
    output_name: str = ""


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


def _remove_tree(target: Path) -> None:
    """Remove one temporary artifact, tolerating an already-missing path."""
    try:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()
    except OSError:
        pass


def _prepare_staging(staging: Path) -> None:
    """Start from a clean staging directory (leftovers are never committed)."""
    _remove_tree(staging)
    staging.mkdir(parents=True, exist_ok=True)


def _move_artifact(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_dir() and not destination.is_symlink():
        shutil.rmtree(destination)
    elif destination.exists() or destination.is_symlink():
        destination.unlink()
    shutil.move(str(source), str(destination))


def _commit(staging: Path, output: Path, *, success: bool) -> None:
    """Move staged pipeline-owned artifacts into ``output`` atomically enough.

    An existing dataset is first moved to ``<output>.previous``. On failure the
    backup is retained so the last good dataset stays recoverable; a successful
    commit removes it. Unrelated files in ``output`` are never touched.
    """
    backup = Path(f"{output}.previous")
    try:
        new_names = [
            name for name in OWNED_ARTIFACTS if (staging / name).exists()
        ]
        output.mkdir(parents=True, exist_ok=True)
        has_previous_dataset = any(
            (output / name).exists() or (output / name).is_symlink()
            for name in OWNED_ARTIFACTS
        )
        if has_previous_dataset:
            _remove_tree(backup)
            backup.mkdir(parents=True, exist_ok=True)
            for name in OWNED_ARTIFACTS:
                current = output / name
                if current.exists() or current.is_symlink():
                    _move_artifact(current, backup / name)

        for name in new_names:
            _move_artifact(staging / name, output / name)

        if success:
            _remove_tree(backup)
    except OSError as exc:
        raise PipelineIOError(f"failed to commit output artifacts: {exc}") from exc


def _unavailable_fingerprint(exc: Exception) -> dict[str, Any]:
    """Represent an incomplete check without claiming the source changed."""
    return {
        "algorithm": "sha256",
        "tree_sha256": "",
        "status": "unavailable",
        "after_tree_sha256": None,
        "verified_after_run": False,
        "changed": [],
        "error": str(exc),
    }


def _error_anomalies(anomalies: list[AnomalyRecord]) -> list[AnomalyRecord]:
    return [
        anomaly for anomaly in anomalies if anomaly.severity == Severity.ERROR
    ]


def _assign_output_names(samples: list[_PreparedSample]) -> None:
    """Assign deterministic output stems (collision strategy from data-model)."""
    by_stem: dict[str, list[_PreparedSample]] = defaultdict(list)
    for prepared in samples:
        by_stem[prepared.sample.image.stem].append(prepared)

    proposed: dict[str, str] = {}
    for stem, group in by_stem.items():
        for prepared in group:
            proposed[prepared.sample.sample_id] = (
                stem if len(group) == 1 else f"{prepared.sample.source_subset}_{stem}"
            )

    by_proposed: dict[str, list[_PreparedSample]] = defaultdict(list)
    for prepared in samples:
        by_proposed[proposed[prepared.sample.sample_id]].append(prepared)

    for name, group in by_proposed.items():
        if len(group) == 1:
            group[0].output_name = name
            continue

        ordered = sorted(group, key=lambda item: item.sample.sample_id)
        for length in (8, 12, 16, 32, 64):
            candidates = {
                item.sample.sample_id: f"{name}_{(item.sha256 or '')[:length]}"
                for item in ordered
            }
            if len(set(candidates.values())) == len(ordered):
                for item in ordered:
                    item.output_name = candidates[item.sample.sample_id]
                break
        else:
            for position, item in enumerate(ordered):
                item.output_name = f"{name}_{position:03d}"


def _write_label(path: Path, label_text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(label_text)


def _verify_written(image_dir: Path, label_dir: Path, expected: int) -> None:
    images = sorted(path for path in image_dir.iterdir() if path.is_file())
    labels = sorted(path for path in label_dir.iterdir() if path.is_file())
    if len(images) != expected or len(labels) != expected:
        raise PipelineIOError(
            "post-write verification failed: "
            f"expected {expected} images and {expected} labels, found "
            f"{len(images)} images and {len(labels)} labels"
        )
    image_stems = {path.stem for path in images}
    label_stems = {path.stem for path in labels}
    if image_stems != label_stems:
        missing = sorted(image_stems - label_stems)
        extra = sorted(label_stems - image_stems)
        raise PipelineIOError(
            "post-write verification failed: image/label stems differ; "
            f"missing labels={missing}, extra labels={extra}"
        )


def _discard_dataset(staging: Path) -> None:
    """Drop interim images/labels so a failed run cannot look like a dataset."""
    for name in ("images", "labels", "split_manifest.json"):
        _remove_tree(staging / name)


def _unique_destination(
    destination: Path, sha256: str | None, used: set[Path]
) -> Path:
    if destination not in used:
        used.add(destination)
        return destination
    digest = str(sha256 or "").removeprefix("sha256:")[:8] or "00000000"
    candidate = destination.with_name(
        f"{destination.stem}__{digest}{destination.suffix}"
    )
    position = 1
    while candidate in used:
        candidate = destination.with_name(
            f"{destination.stem}__{digest}_{position}{destination.suffix}"
        )
        position += 1
    used.add(candidate)
    return candidate


def _copy_rejected(
    staging: Path,
    samples: list[MatchedSample],
    subset_roots: dict[str, Path],
) -> None:
    """Copy raw source image + XML of paired rejected samples into ``rejected/``."""
    used: set[Path] = set()
    for sample in samples:
        subset_root = subset_roots[sample.source_subset]
        assets = (
            ("images", sample.image.relative_path),
            ("annotations", sample.annotation.relative_path),
        )
        for kind, relative_path in assets:
            source_path = subset_root / relative_path
            try:
                inner = relative_path.relative_to(kind)
            except ValueError:
                inner = Path(relative_path.name)
            destination = staging / "rejected" / kind / sample.source_subset / inner
            destination = _unique_destination(
                destination, getattr(sample.image, "sha256", None), used
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)


def _report_kwargs(
    *,
    options: ConversionOptions,
    discovery: DiscoveryResult,
    pairing: PairingResult,
    anomalies: list[AnomalyRecord],
    fingerprint: SourceFingerprint | dict[str, Any],
    eligible_samples: list[MatchedSample],
    gate_status: str,
    written_samples: int,
    quarantined_samples: int,
) -> dict[str, Any]:
    objects_by_class: Counter[int] = Counter()
    for sample in eligible_samples:
        for obj in sample.objects:
            if obj.class_id is not None:
                objects_by_class[int(obj.class_id)] += 1
    return {
        "source_root": discovery.dataset.root,
        "fingerprint": fingerprint,
        "source_subsets": [subset.name for subset in discovery.subsets],
        "seed": options.seed,
        "ratios": options.ratios,
        "on_anomaly": options.on_anomaly,
        "source_images": len(discovery.images),
        "source_annotations": len(discovery.annotations),
        "matched_samples": len(pairing.samples),
        "unpaired_images": len(pairing.unpaired_images),
        "unpaired_annotations": len(pairing.unpaired_annotations),
        "eligible_samples": len(eligible_samples),
        "quarantined_samples": quarantined_samples,
        "written_samples": written_samples,
        "objects_total": sum(sample.object_count for sample in eligible_samples),
        "objects_by_class": dict(objects_by_class),
        "anomalies": anomalies,
        "gate_status": gate_status,
    }


def _write_report(staging: Path, payload: dict[str, Any]) -> Path:
    path = staging / "validation_report.json"
    try:
        write_validation_report(path, **payload)
    except OSError as exc:
        raise PipelineIOError(f"cannot write validation report: {exc}") from exc
    return path


def _finish_failure(
    *,
    staging: Path,
    output: Path,
    kwargs: dict[str, Any],
    anomalies: list[AnomalyRecord],
    fingerprint: SourceFingerprint | dict[str, Any],
    quarantined: list[MatchedSample],
    subset_roots: dict[str, Path],
    message: str,
    exit_code: int,
    discard_dataset: bool = False,
) -> None:
    """Write the failure report, keep rejected copies and commit report-only."""
    failure = {
        **kwargs,
        "anomalies": anomalies,
        "fingerprint": fingerprint,
        "gate_status": "fail",
        "written_samples": 0,
        "quarantined_samples": len(quarantined),
    }
    if discard_dataset:
        _discard_dataset(staging)
    _write_report(staging, failure)
    if quarantined:
        try:
            _copy_rejected(staging, quarantined, subset_roots)
        except OSError as exc:
            raise PipelineIOError(f"cannot copy rejected samples: {exc}") from exc
    _commit(staging, output, success=False)
    if exit_code == 5:
        raise PipelineIOError(message, anomalies=anomalies)
    raise PipelineError(message, anomalies=anomalies)


def run_conversion(options: ConversionOptions) -> PipelineResult:
    """Run discover/pair/validate/gate/write/verify with a safe commit."""
    source = Path(options.source).expanduser().resolve(strict=False)
    output = Path(options.output).expanduser().resolve(strict=False)

    if (
        output == source
        or _is_relative_to(output, source)
        or _is_relative_to(source, output)
    ):
        raise PipelineConfigError(
            "output must not be inside, equal to, or a parent of the source "
            f"directory (source={source}, output={output})"
        )

    discovery = discover_source(source)
    pairing: PairingResult = pair_samples(discovery)
    validation: ValidationResult = validate_samples(
        pairing.samples, discovery.dataset.root
    )
    eligible_valid = [
        sample
        for sample in validation.samples
        if sample.state == SampleState.VALID
    ]
    duplicates: DuplicateAuditResult = audit_duplicate_groups(eligible_valid)

    anomalies: list[AnomalyRecord] = [
        *discovery.anomalies,
        *pairing.anomalies,
        *validation.anomalies,
        *duplicates.anomalies,
    ]

    subset_roots = {
        subset.name: subset.images_dir.parent for subset in discovery.subsets
    }
    staging = Path(f"{output}.staging")
    _prepare_staging(staging)

    try:
        # Fingerprint after validation, even when the gate will fail.
        try:
            after_validate = fingerprint_source(source)
        except (DiscoveryError, OSError) as exc:
            kwargs = _report_kwargs(
                options=options,
                discovery=discovery,
                pairing=pairing,
                anomalies=anomalies,
                fingerprint=_unavailable_fingerprint(exc),
                eligible_samples=eligible_valid,
                gate_status="fail",
                written_samples=0,
                quarantined_samples=0,
            )
            _finish_failure(
                staging=staging,
                output=output,
                kwargs=kwargs,
                anomalies=anomalies,
                fingerprint=kwargs["fingerprint"],
                quarantined=[],
                subset_roots=subset_roots,
                message=f"source fingerprint verification unavailable: {exc}",
                exit_code=5,
            )

        fingerprint = compare_fingerprints(
            discovery.dataset.fingerprint, after_validate
        )
        if not fingerprint.verified_after_run:
            changed = list(fingerprint.changed)
            changed_anomaly = AnomalyRecord(
                code="source_tree_changed",
                severity="error",
                scope="dataset",
                paths=changed,
                reason=(
                    "source tree changed during the run; the source dataset "
                    "must remain read-only"
                ),
                details={"changed": changed},
            )
            kwargs = _report_kwargs(
                options=options,
                discovery=discovery,
                pairing=pairing,
                anomalies=anomalies,
                fingerprint=fingerprint,
                eligible_samples=eligible_valid,
                gate_status="fail",
                written_samples=0,
                quarantined_samples=0,
            )
            _finish_failure(
                staging=staging,
                output=output,
                kwargs=kwargs,
                anomalies=[*anomalies, changed_anomaly],
                fingerprint=fingerprint,
                quarantined=[],
                subset_roots=subset_roots,
                message="source tree changed during the run",
                exit_code=3,
            )

        conflict_ids = {
            group.group_id
            for group in duplicates.groups
            if not group.labels_consistent
        }
        conflict_samples = [
            sample
            for sample in eligible_valid
            if sample.duplicate_group in conflict_ids
        ]
        eligible_samples = [
            sample
            for sample in eligible_valid
            if sample.duplicate_group not in conflict_ids
        ]
        invalid_samples = [
            sample
            for sample in validation.samples
            if sample.state == SampleState.INVALID
        ]

        unpaired_errors = [
            anomaly
            for anomaly in anomalies
            if anomaly.severity == Severity.ERROR
            and anomaly.code in UNPAIRED_CODES
        ]
        paired_errors = [
            anomaly
            for anomaly in anomalies
            if anomaly.severity == Severity.ERROR
            and anomaly.code not in UNPAIRED_CODES
        ]

        quarantine_mode = options.on_anomaly == "quarantine"
        quarantined = (
            [*invalid_samples, *conflict_samples] if quarantine_mode else []
        )

        if paired_errors:
            if quarantine_mode and quarantined and eligible_samples:
                gate = "pass_with_quarantine"
            else:
                gate = "fail"
        elif unpaired_errors:
            # Unpaired assets are reported but never copied; a run with at
            # least one eligible paired sample can still succeed.
            gate = "pass_with_quarantine" if eligible_samples else "fail"
        else:
            gate = "pass"

        kwargs = _report_kwargs(
            options=options,
            discovery=discovery,
            pairing=pairing,
            anomalies=anomalies,
            fingerprint=fingerprint,
            eligible_samples=eligible_samples,
            gate_status=gate,
            written_samples=0,
            quarantined_samples=0,
        )

        if gate == "fail":
            _finish_failure(
                staging=staging,
                output=output,
                kwargs=kwargs,
                anomalies=anomalies,
                fingerprint=fingerprint,
                quarantined=quarantined,
                subset_roots=subset_roots,
                message=f"validation gate failed with {len(_error_anomalies(anomalies))} error(s)",
                exit_code=3,
            )

        # First write: nothing has been written or quarantined yet.
        _write_report(staging, kwargs)

        if quarantined:
            try:
                _copy_rejected(staging, quarantined, subset_roots)
            except OSError as exc:
                raise PipelineIOError(
                    f"cannot copy rejected samples: {exc}"
                ) from exc

        prepared: list[_PreparedSample] = []
        for sample in eligible_samples:
            subset_root = subset_roots[sample.source_subset]
            label_text = "".join(f"{line}\n" for line in sample.label_lines)
            prepared.append(
                _PreparedSample(
                    sample=sample,
                    source_image=subset_root / sample.image.relative_path,
                    source_annotation=subset_root / sample.annotation.relative_path,
                    sha256=getattr(sample.image, "sha256", None),
                    label_text=label_text,
                    object_count=len(sample.label_lines),
                    present_classes=list(sample.present_classes or []),
                )
            )

        if not prepared:
            _finish_failure(
                staging=staging,
                output=output,
                kwargs=kwargs,
                anomalies=anomalies,
                fingerprint=fingerprint,
                quarantined=quarantined,
                subset_roots=subset_roots,
                message="no eligible sample remains to write",
                exit_code=3,
                discard_dataset=True,
            )

        _assign_output_names(prepared)
        split = options.interim_split
        image_dir = staging / "images" / split
        label_dir = staging / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)

        objects_written = 0
        present_classes: set[int] = set()
        try:
            for item in prepared:
                extension = item.sample.image.extension
                image_name = f"{item.output_name}{extension}"
                label_name = f"{item.output_name}.txt"
                shutil.copy2(
                    item.source_image, image_dir / image_name
                )
                _write_label(label_dir / label_name, item.label_text)
                objects_written += item.object_count
                present_classes.update(item.present_classes)
                item.sample.state = SampleState.WRITTEN
            _verify_written(image_dir, label_dir, len(prepared))
        except (OSError, PipelineIOError) as exc:
            _finish_failure(
                staging=staging,
                output=output,
                kwargs=kwargs,
                anomalies=anomalies,
                fingerprint=fingerprint,
                quarantined=quarantined,
                subset_roots=subset_roots,
                message=f"write or verification failed: {exc}",
                exit_code=5,
                discard_dataset=True,
            )

        # Final source check on the success path.
        try:
            after_write = fingerprint_source(source)
        except (DiscoveryError, OSError) as exc:
            _finish_failure(
                staging=staging,
                output=output,
                kwargs=kwargs,
                anomalies=anomalies,
                fingerprint=_unavailable_fingerprint(exc),
                quarantined=quarantined,
                subset_roots=subset_roots,
                message=f"source fingerprint verification unavailable: {exc}",
                exit_code=5,
                discard_dataset=True,
            )

        final_fingerprint = compare_fingerprints(
            discovery.dataset.fingerprint, after_write
        )
        if not final_fingerprint.verified_after_run:
            changed = list(final_fingerprint.changed)
            changed_anomaly = AnomalyRecord(
                code="source_tree_changed",
                severity="error",
                scope="dataset",
                paths=changed,
                reason=(
                    "source tree changed during the run; the source dataset "
                    "must remain read-only"
                ),
                details={"changed": changed},
            )
            _finish_failure(
                staging=staging,
                output=output,
                kwargs=kwargs,
                anomalies=[*anomalies, changed_anomaly],
                fingerprint=final_fingerprint,
                quarantined=quarantined,
                subset_roots=subset_roots,
                message="source tree changed during the run",
                exit_code=3,
                discard_dataset=True,
            )

        write_validation_report(
            staging / "validation_report.json",
            **{
                **kwargs,
                "fingerprint": final_fingerprint,
                "written_samples": len(prepared),
                "quarantined_samples": len(quarantined),
            },
        )
        _commit(staging, output, success=True)

        return PipelineResult(
            output=output,
            split=split,
            samples_written=len(prepared),
            images_written=len(prepared),
            labels_written=len(prepared),
            objects_written=objects_written,
            present_classes=sorted(present_classes),
            anomalies=anomalies,
            fingerprint=final_fingerprint,
            quarantined_samples=len(quarantined),
            gate_status=gate,
            report_path=output / "validation_report.json",
        )
    finally:
        _remove_tree(staging)
