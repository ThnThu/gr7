"""US1 conversion stage and reusable output writer (T015).

The pipeline runs discover -> pair -> verify -> convert in memory first. Output
directories are created only when no blocking anomaly was found, so a failing
run leaves the output untouched. Source images are copied with
:func:`shutil.copy2`; labels are written as UTF-8 text with ``\\n`` endings and
an empty annotation becomes a zero-byte file.

Until User Story 3 supplies real split assignments, every converted sample is
written to the interim ``train`` split. This module never writes
``validation_report.json``, ``split_manifest.json`` or ``dataset.yaml``.
"""

from __future__ import annotations

import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .converter import ConversionResult, convert_annotation
from .discovery import (
    DiscoveryError,
    PairingResult,
    compare_fingerprints,
    discover_source,
    fingerprint_source,
    pair_samples,
)
from .models import (
    AnomalyRecord,
    MatchedSample,
    Severity,
    SourceFingerprint,
)
from .validator import ImageVerification, verify_image

INTERIM_SPLIT = "train"
KNOWN_ARTIFACTS = ("images", "labels", "rejected")
KNOWN_FILES = ("validation_report.json", "split_manifest.json")


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


@dataclass
class PipelineResult:
    """Summary of a completed US1 conversion run."""

    output: Path
    split: str
    samples_written: int = 0
    images_written: int = 0
    labels_written: int = 0
    objects_written: int = 0
    present_classes: list[int] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    fingerprint: SourceFingerprint = field(default_factory=SourceFingerprint)


@dataclass
class _PreparedSample:
    sample: MatchedSample
    source_image: Path
    source_annotation: Path
    verification: ImageVerification
    conversion: ConversionResult
    output_name: str = ""


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


def _source_relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _error_anomalies(anomalies: list[AnomalyRecord]) -> list[AnomalyRecord]:
    return [
        anomaly
        for anomaly in anomalies
        if anomaly.severity == Severity.ERROR
    ]


def _size_mismatch(
    sample: MatchedSample,
    source_path: str,
    declared: dict[str, int],
    actual: dict[str, int],
) -> AnomalyRecord:
    return AnomalyRecord(
        code="size_mismatch",
        severity="warning",
        scope="sample",
        sample_id=sample.sample_id,
        source_subset=sample.source_subset,
        paths=[source_path],
        reason=(
            "XML <size> does not match the actual image size; the actual "
            "image size is used for normalization"
        ),
        details={"declared": declared, "actual": actual},
    )


def _empty_annotation(
    sample: MatchedSample,
    source_path: str,
) -> AnomalyRecord:
    return AnomalyRecord(
        code="empty_annotation",
        severity="info",
        scope="sample",
        sample_id=sample.sample_id,
        source_subset=sample.source_subset,
        paths=[source_path],
        reason="XML contains zero objects; a zero-byte label is written",
        details={"object_count": 0},
    )


def _apply_overwrite(output: Path) -> None:
    """Remove only artifacts this pipeline owns."""
    for name in KNOWN_ARTIFACTS:
        target = output / name
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()
    for name in KNOWN_FILES:
        target = output / name
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()


def _prepare_output(output: Path, *, overwrite: bool) -> None:
    if output.exists() or output.is_symlink():
        if not output.is_dir():
            if not overwrite:
                raise PipelineOutputExistsError(
                    f"output already exists: {output}; use --overwrite"
                )
            raise PipelineConfigError(
                f"output path exists and is not a directory: {output}"
            )
        if any(output.iterdir()):
            if not overwrite:
                raise PipelineOutputExistsError(
                    f"output directory is not empty: {output}; use --overwrite"
                )
            _apply_overwrite(output)
    output.mkdir(parents=True, exist_ok=True)


def _assign_output_names(samples: list[_PreparedSample]) -> None:
    """Assign deterministic output stems.

    A unique source stem is kept. If several samples share a stem, the source
    subset is prefixed. Remaining collisions append the first 8 characters of
    the image SHA-256; longer prefixes are used only if that is still ambiguous.
    """
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
                item.sample.sample_id: (
                    f"{name}_{(item.verification.sha256 or '')[:length]}"
                )
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


def _verify_written(
    image_dir: Path,
    label_dir: Path,
    expected: int,
) -> None:
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


def _discard_written_split(output: Path, split: str) -> None:
    """Remove this run's image/label split after a failed verification.

    A source-change or write failure must not leave a complete-looking output
    tree behind, because a later reader could mistake it for valid data.
    """
    for target in (
        output / "images" / split,
        output / "labels" / split,
    ):
        try:
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            elif target.exists() or target.is_symlink():
                target.unlink()
        except OSError:
            pass

    for parent in (output / "images", output / "labels", output):
        try:
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass


def run_conversion(options: ConversionOptions) -> PipelineResult:
    """Run the US1 discover/pair/verify/convert/write pipeline.

    Raises:
        PipelineConfigError: unsafe source/output combination (exit 2).
        PipelineError: blocking data anomaly (exit 3).
        PipelineOutputExistsError: output exists without ``--overwrite`` (exit 4).
        PipelineIOError: I/O or post-write verification failure (exit 5).
        DiscoveryError: source structure error (exit 2).
    """
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

    anomalies: list[AnomalyRecord] = [
        *discovery.anomalies,
        *pairing.anomalies,
    ]
    prepared: list[_PreparedSample] = []

    subset_roots = {
        subset.name: subset.images_dir.parent for subset in discovery.subsets
    }

    for sample in pairing.samples:
        subset_root = subset_roots[sample.source_subset]
        source_image = subset_root / sample.image.relative_path
        source_annotation = subset_root / sample.annotation.relative_path
        image_relative = _source_relative(discovery.dataset.root, source_image)
        annotation_relative = _source_relative(
            discovery.dataset.root, source_annotation
        )

        verification = verify_image(
            source_image,
            sample_id=sample.sample_id,
            source_subset=sample.source_subset,
            source_path=image_relative,
        )
        anomalies.extend(verification.anomalies)
        if not verification.valid:
            sample.state = "invalid"
            continue

        conversion = convert_annotation(
            source_annotation,
            image_width=int(verification.width or 0),
            image_height=int(verification.height or 0),
            sample_id=sample.sample_id,
            source_subset=sample.source_subset,
            source_path=annotation_relative,
        )
        anomalies.extend(conversion.anomalies)

        if conversion.declared_size is not None and conversion.declared_size != {
            "width": verification.width,
            "height": verification.height,
        }:
            anomalies.append(
                _size_mismatch(
                    sample,
                    annotation_relative,
                    conversion.declared_size,
                    {
                        "width": int(verification.width or 0),
                        "height": int(verification.height or 0),
                    },
                )
            )

        if not conversion.valid:
            sample.state = "invalid"
            continue

        if conversion.object_count == 0:
            anomalies.append(_empty_annotation(sample, annotation_relative))

        prepared.append(
            _PreparedSample(
                sample=sample,
                source_image=source_image,
                source_annotation=source_annotation,
                verification=verification,
                conversion=conversion,
            )
        )

    blocking = _error_anomalies(anomalies)
    if blocking:
        raise PipelineError(
            f"{len(blocking)} blocking data error(s); no output was written",
            anomalies=anomalies,
        )

    if not prepared:
        raise PipelineError(
            "source contains no samples that can be converted; no output was written",
            anomalies=anomalies,
        )

    _assign_output_names(prepared)
    _prepare_output(output, overwrite=options.overwrite)

    split = options.interim_split
    image_dir = output / "images" / split
    label_dir = output / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    objects_written = 0
    present_classes: set[int] = set()
    try:
        for item in prepared:
            extension = item.sample.image.extension
            image_name = f"{item.output_name}{extension}"
            label_name = f"{item.output_name}.txt"
            destination_image = image_dir / image_name
            destination_label = label_dir / label_name

            shutil.copy2(item.source_image, destination_image)
            _write_label(destination_label, item.conversion.label_text)

            objects_written += item.conversion.object_count
            present_classes.update(item.conversion.present_classes)
            item.sample.state = "written"

        _verify_written(image_dir, label_dir, len(prepared))
    except (OSError, PipelineIOError):
        _discard_written_split(output, split)
        raise

    try:
        after = fingerprint_source(source)
    except DiscoveryError as exc:
        _discard_written_split(output, split)
        result_anomalies = [
            *anomalies,
            AnomalyRecord(
                code="source_tree_changed",
                severity="error",
                scope="dataset",
                paths=[],
                reason=(
                    "source tree became unavailable or changed during the run; "
                    f"the source dataset must remain read-only ({exc})"
                ),
                details={"changed": [], "error": str(exc)},
            ),
        ]
        raise PipelineError(
            "source tree changed during the run",
            anomalies=result_anomalies,
        ) from exc
    except OSError:
        _discard_written_split(output, split)
        raise

    fingerprint = compare_fingerprints(discovery.dataset.fingerprint, after)
    result_anomalies = [*anomalies]
    if not fingerprint.verified_after_run:
        changed = fingerprint.changed
        _discard_written_split(output, split)
        result_anomalies.append(
            AnomalyRecord(
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
        )
        raise PipelineError(
            "source tree changed during the run",
            anomalies=result_anomalies,
        )

    return PipelineResult(
        output=output,
        split=split,
        samples_written=len(prepared),
        images_written=len(prepared),
        labels_written=len(prepared),
        objects_written=objects_written,
        present_classes=sorted(present_classes),
        anomalies=result_anomalies,
        fingerprint=fingerprint,
    )
