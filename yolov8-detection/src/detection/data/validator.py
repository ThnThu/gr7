"""Image-level verification and US2 sample validation for the NEU-DET pipeline.

``verify_image`` (T014) opens each image read-only, reports the actual pixel
size and checks file integrity with :meth:`PIL.Image.Image.verify`. The
orchestrator (T020) reuses :func:`verify_image` and
:func:`detection.data.converter.convert_annotation`, adds source-level checks
(``size_mismatch``, ``filename_mismatch``, ``empty_annotation``) and marks the
whole sample invalid when any object fails. Duplicate-content audit (T021)
groups eligible samples by SHA-256 and emits one ``duplicate_content`` record
per member.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

from .converter import convert_annotation
from .models import (
    AnomalyRecord,
    DuplicateGroup,
    DuplicateGroupState,
    ImageStatus,
    MatchedSample,
    SampleState,
    Severity,
)


@dataclass
class ImageVerification:
    """Outcome of verifying one source image."""

    path: Path
    valid: bool
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    image_format: str | None = None
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    reason: str | None = None


@dataclass
class ValidationResult:
    """Result of validating paired samples."""

    samples: list[MatchedSample] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)


@dataclass
class DuplicateAuditResult:
    """Result of auditing duplicate image content across eligible samples."""

    groups: list[DuplicateGroup] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _corrupt(
    path: Path,
    *,
    reason: str,
    sample_id: str | None,
    source_subset: str | None,
    label_path: str,
) -> AnomalyRecord:
    return AnomalyRecord(
        code="corrupt_image",
        severity="error",
        scope="image",
        sample_id=sample_id,
        source_subset=source_subset,
        paths=[label_path],
        reason=reason,
        details={"image": path.name},
    )


def verify_image(
    image_path: str | Path,
    *,
    sample_id: str | None = None,
    source_subset: str | None = None,
    source_path: str | None = None,
) -> ImageVerification:
    """Open, verify and hash one image without modifying it.

    Args:
        image_path: Existing image file.
        sample_id: Optional ``<subset>/<stem>`` used in anomaly records.
        source_subset: Optional source subset used in anomaly records.
        source_path: Optional path relative to the source root for anomaly
            records.

    Returns:
        An :class:`ImageVerification`. ``valid`` is ``False`` when the image
        cannot be decoded; ``width``/``height`` are the actual dimensions on
        success and the only size the converter should use.
    """
    path = Path(image_path)
    label_path = source_path or path.name

    try:
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
            image.verify()
    except (OSError, ValueError, SyntaxError) as exc:
        return ImageVerification(
            path=path,
            valid=False,
            anomalies=[
                _corrupt(
                    path,
                    reason=f"cannot open or verify image: {exc}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    label_path=label_path,
                )
            ],
            reason=str(exc),
        )

    if width <= 0 or height <= 0:
        return ImageVerification(
            path=path,
            valid=False,
            width=width,
            height=height,
            image_format=image_format,
            anomalies=[
                _corrupt(
                    path,
                    reason=f"image reports non-positive size: {width}x{height}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    label_path=label_path,
                )
            ],
            reason="non-positive image size",
        )

    try:
        digest = _sha256_file(path)
    except OSError as exc:
        return ImageVerification(
            path=path,
            valid=False,
            width=width,
            height=height,
            image_format=image_format,
            anomalies=[
                _corrupt(
                    path,
                    reason=f"cannot read image bytes for hashing: {exc}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    label_path=label_path,
                )
            ],
            reason=str(exc),
        )

    return ImageVerification(
        path=path,
        valid=True,
        width=int(width),
        height=int(height),
        sha256=digest,
        image_format=image_format,
    )


def _asset_path(root: Path, subset: str, relative_path: Path) -> Path:
    """Resolve an asset path from a source root and subset-relative path."""
    subset_prefix = Path() if subset == "root" else Path(subset)
    return root / subset_prefix / Path(relative_path)


def _contract_sort_key(anomaly: AnomalyRecord) -> tuple[Any, ...]:
    """Stable anomaly ordering defined by data-model.md section 6."""
    sample_id = anomaly.sample_id
    object_index = anomaly.details.get("object_index")
    return (
        anomaly.code,
        tuple(anomaly.paths),
        (1, "") if sample_id is None else (0, sample_id),
        (1, 0) if object_index is None else (0, int(object_index)),
        anomaly.reason,
    )


def _mark_invalid(sample: MatchedSample) -> None:
    sample.state = SampleState.INVALID
    sample.label_lines = []
    sample.present_classes = []
    sample.objects = []


def validate_samples(
    samples: Sequence[MatchedSample],
    source_root: str | Path,
) -> ValidationResult:
    """Validate paired samples by reusing image verification and annotation conversion.

    The orchestrator never parses XML, maps classes or validates bboxes itself:
    it delegates to :func:`verify_image` and
    :func:`convert_annotation`, then adds sample-level checks for declared size,
    declared filename and empty annotations. A sample becomes invalid when any
    object fails; no coordinates are clipped or repaired.
    """
    root = Path(source_root)
    collected: list[AnomalyRecord] = []
    validated: list[MatchedSample] = []

    for sample in samples:
        image_path = _asset_path(root, sample.source_subset, sample.image.relative_path)
        xml_path = _asset_path(
            root, sample.source_subset, sample.annotation.relative_path
        )
        image_rel = sample.image.asset_id
        xml_rel = sample.annotation.asset_id

        verification = verify_image(
            image_path,
            sample_id=sample.sample_id,
            source_subset=sample.source_subset,
            source_path=image_rel,
        )
        collected.extend(verification.anomalies)

        if not verification.valid:
            sample.image.status = ImageStatus.CORRUPT
            _mark_invalid(sample)
            validated.append(sample)
            continue

        sample.image.width = int(verification.width) if verification.width is not None else None
        sample.image.height = (
            int(verification.height) if verification.height is not None else None
        )
        sample.image.sha256 = verification.sha256
        sample.image.status = ImageStatus.VALID

        conversion = convert_annotation(
            xml_path,
            image_width=int(verification.width or 0),
            image_height=int(verification.height or 0),
            sample_id=sample.sample_id,
            source_subset=sample.source_subset,
            source_path=xml_rel,
        )
        collected.extend(conversion.anomalies)

        sample.annotation.declared_size = conversion.declared_size
        sample.annotation.declared_filename = conversion.declared_filename

        if conversion.declared_size is not None and verification.width is not None:
            actual = {"width": int(verification.width), "height": int(verification.height)}
            if conversion.declared_size != actual:
                collected.append(
                    AnomalyRecord(
                        code="size_mismatch",
                        severity=Severity.WARNING,
                        scope="sample",
                        sample_id=sample.sample_id,
                        source_subset=sample.source_subset,
                        paths=[image_rel, xml_rel],
                        reason=(
                            "XML <size> does not match the actual image size; "
                            "the actual image size is used for normalization"
                        ),
                        details={"declared": conversion.declared_size, "actual": actual},
                    )
                )

        if conversion.declared_filename is not None:
            actual_filename = Path(image_rel).name
            if Path(conversion.declared_filename).name != actual_filename:
                collected.append(
                    AnomalyRecord(
                        code="filename_mismatch",
                        severity=Severity.WARNING,
                        scope="annotation",
                        sample_id=sample.sample_id,
                        source_subset=sample.source_subset,
                        paths=[image_rel, xml_rel],
                        reason=(
                            "XML <filename> basename does not match the paired "
                            "image filename"
                        ),
                        details={
                            "declared_filename": conversion.declared_filename,
                            "actual_filename": actual_filename,
                        },
                    )
                )

        if conversion.valid:
            sample.objects = conversion.objects
            sample.label_lines = list(conversion.label_lines)
            sample.present_classes = list(conversion.present_classes)
            sample.state = SampleState.VALID
            sample.annotation.status = "valid"
            if conversion.object_count == 0:
                collected.append(
                    AnomalyRecord(
                        code="empty_annotation",
                        severity=Severity.INFO,
                        scope="sample",
                        sample_id=sample.sample_id,
                        source_subset=sample.source_subset,
                        paths=[xml_rel],
                        reason=(
                            "XML contains zero objects; the sample is retained as "
                            "a valid image with an empty label"
                        ),
                        details={"object_count": 0},
                    )
                )
        else:
            sample.objects = list(conversion.objects)
            sample.label_lines = []
            sample.present_classes = list(conversion.present_classes)
            sample.state = SampleState.INVALID
            # Preserve annotation status hints when possible; converter emits
            # invalid_xml anomalies for structural/XML issues.
            if any(anomaly.code == "invalid_xml" for anomaly in conversion.anomalies):
                sample.annotation.status = "invalid_xml"

        validated.append(sample)

    collected.sort(key=_contract_sort_key)
    return ValidationResult(samples=validated, anomalies=collected)


def _label_multiset(sample: MatchedSample) -> Counter[tuple[Any, ...]]:
    """Return an order-insensitive multiset of normalized label values."""
    items: list[tuple[Any, ...]] = []
    for line in sample.label_lines:
        parts = str(line).split()
        if len(parts) != 5:
            items.append((line,))
            continue
        class_id, cx, cy, w, h = parts
        try:
            class_value: Any = int(class_id)
        except ValueError:
            class_value = class_id
        items.append((class_value, cx, cy, w, h))
    return Counter(items)


def audit_duplicate_groups(
    samples: Sequence[MatchedSample],
) -> DuplicateAuditResult:
    """Audit eligible samples for duplicate image content.

    Samples with identical SHA-256 digests are grouped atomically. Label
    consistency compares the order-insensitive multiset of
    ``(class_id, cx, cy, w, h)`` values, ignoring XML object order.
    """
    by_sample_id = {sample.sample_id: sample for sample in samples}
    by_sha: dict[str, list[MatchedSample]] = {}
    for sample in samples:
        digest = getattr(sample.image, "sha256", None)
        if not digest:
            continue
        digest = str(digest).removeprefix("sha256:")
        by_sha.setdefault(digest, []).append(sample)

    groups: list[DuplicateGroup] = []
    anomalies: list[AnomalyRecord] = []

    for digest in sorted(by_sha):
        members = sorted(by_sha[digest], key=lambda item: item.sample_id)
        if len(members) < 2:
            continue

        reference = _label_multiset(members[0])
        labels_consistent = all(
            _label_multiset(member) == reference for member in members[1:]
        )
        state = (
            DuplicateGroupState.GROUPED
            if labels_consistent
            else DuplicateGroupState.CONFLICT
        )
        group = DuplicateGroup(
            sha256=digest,
            members=[member.sample_id for member in members],
            labels_consistent=labels_consistent,
            state=state,
        )
        groups.append(group)

        severity = Severity.WARNING if labels_consistent else Severity.ERROR
        for member in members:
            member.duplicate_group = group.group_id
            member_paths = [member.image.asset_id, member.annotation.asset_id]
            if labels_consistent:
                reason = (
                    "image content is duplicated and normalized labels are "
                    "consistent across all group members"
                )
            else:
                reason = (
                    "image content is duplicated but normalized labels differ "
                    "across group members"
                )
            anomalies.append(
                AnomalyRecord(
                    code="duplicate_content",
                    severity=severity,
                    scope="sample",
                    sample_id=member.sample_id,
                    source_subset=member.source_subset,
                    paths=list(member_paths),
                    reason=reason,
                    details={
                        "group_id": group.group_id,
                        "sha256": group.sha256,
                        "member_count": len(group.members),
                        "labels_consistent": labels_consistent,
                    },
                )
            )

    groups.sort(key=lambda group: group.group_id)
    anomalies.sort(key=_contract_sort_key)
    return DuplicateAuditResult(groups=groups, anomalies=anomalies)

