"""Shared data entities and anomaly taxonomy for the NEU-DET pipeline.

The shapes follow ``specs/001-neu-det-data-preparation/data-model.md``. These
dataclasses are deliberately small: they carry validated data between the
discovery, conversion, validation, split and manifest stages and do not perform
file I/O themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
)
SPLIT_NAMES: tuple[str, ...] = ("train", "validation", "test")


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AnomalyScope(StrEnum):
    DATASET = "dataset"
    SUBSET = "subset"
    IMAGE = "image"
    ANNOTATION = "annotation"
    SAMPLE = "sample"
    SPLIT = "split"


class ImageStatus(StrEnum):
    DISCOVERED = "discovered"
    VALID = "valid"
    CORRUPT = "corrupt"
    UNPAIRED = "unpaired"


class AnnotationStatus(StrEnum):
    DISCOVERED = "discovered"
    VALID = "valid"
    INVALID_XML = "invalid_xml"
    UNPAIRED = "unpaired"


class SampleState(StrEnum):
    DISCOVERED = "discovered"
    UNPAIRED = "unpaired"
    PAIRED = "paired"
    INVALID = "invalid"
    VALID = "valid"
    ELIGIBLE = "eligible"
    DUPLICATE_CONFLICT = "duplicate_conflict"
    QUARANTINED = "quarantined"
    ASSIGNED = "assigned"
    WRITTEN = "written"


class DuplicateGroupState(StrEnum):
    GROUPED = "grouped"
    CONFLICT = "conflict"
    QUARANTINED = "quarantined"


class SplitName(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True)
class AnomalyDefinition:
    """One entry of the fixed anomaly taxonomy (data-model.md section 6)."""

    code: str
    severities: tuple[Severity, ...]
    scope: AnomalyScope


ANOMALY_DEFINITIONS: tuple[AnomalyDefinition, ...] = (
    AnomalyDefinition("missing_xml", (Severity.ERROR,), AnomalyScope.IMAGE),
    AnomalyDefinition("missing_image", (Severity.ERROR,), AnomalyScope.ANNOTATION),
    AnomalyDefinition("ambiguous_pairing", (Severity.ERROR,), AnomalyScope.SUBSET),
    AnomalyDefinition("invalid_xml", (Severity.ERROR,), AnomalyScope.ANNOTATION),
    AnomalyDefinition("unknown_class", (Severity.ERROR,), AnomalyScope.SAMPLE),
    AnomalyDefinition("invalid_bbox", (Severity.ERROR,), AnomalyScope.SAMPLE),
    AnomalyDefinition("corrupt_image", (Severity.ERROR,), AnomalyScope.IMAGE),
    AnomalyDefinition("empty_annotation", (Severity.INFO,), AnomalyScope.SAMPLE),
    AnomalyDefinition("size_mismatch", (Severity.WARNING,), AnomalyScope.SAMPLE),
    AnomalyDefinition("filename_mismatch", (Severity.WARNING,), AnomalyScope.ANNOTATION),
    AnomalyDefinition(
        "duplicate_content",
        (Severity.WARNING, Severity.ERROR),
        AnomalyScope.SAMPLE,
    ),
    AnomalyDefinition(
        "split_distribution_deviation",
        (Severity.WARNING,),
        AnomalyScope.SPLIT,
    ),
    AnomalyDefinition("split_class_absent", (Severity.WARNING,), AnomalyScope.SPLIT),
    AnomalyDefinition("source_tree_changed", (Severity.ERROR,), AnomalyScope.DATASET),
    AnomalyDefinition("unsupported_file", (Severity.INFO,), AnomalyScope.DATASET),
)

ANOMALY_CODES: tuple[str, ...] = tuple(
    definition.code for definition in ANOMALY_DEFINITIONS
)
ANOMALY_SEVERITIES: dict[str, Severity] = {
    definition.code: definition.severities[0] for definition in ANOMALY_DEFINITIONS
}
ANOMALY_SCOPES: dict[str, AnomalyScope] = {
    definition.code: definition.scope for definition in ANOMALY_DEFINITIONS
}
ANOMALY_ALLOWED_SEVERITIES: dict[str, frozenset[Severity]] = {
    definition.code: frozenset(definition.severities)
    for definition in ANOMALY_DEFINITIONS
}


@dataclass
class AnomalyRecord:
    """A single anomaly attached to the dataset, a subset, sample or split."""

    code: str
    severity: Severity | str
    scope: AnomalyScope | str
    sample_id: str | None = None
    source_subset: str | None = None
    paths: list[str] = field(default_factory=list)
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code not in ANOMALY_ALLOWED_SEVERITIES:
            raise ValueError(f"unknown anomaly code: {self.code!r}")

        try:
            severity = Severity(self.severity)
        except ValueError as exc:
            raise ValueError(
                f"invalid severity {self.severity!r} for anomaly code {self.code!r}"
            ) from exc
        allowed = ANOMALY_ALLOWED_SEVERITIES[self.code]
        if severity not in allowed:
            allowed_text = ", ".join(item.value for item in sorted(allowed))
            raise ValueError(
                f"invalid severity {severity.value!r} for anomaly code "
                f"{self.code!r}; allowed: {allowed_text}"
            )

        try:
            scope = AnomalyScope(self.scope)
        except ValueError as exc:
            raise ValueError(
                f"invalid scope {self.scope!r} for anomaly code {self.code!r}"
            ) from exc
        expected_scope = ANOMALY_SCOPES[self.code]
        if scope is not expected_scope:
            raise ValueError(
                f"invalid scope {scope.value!r} for anomaly code {self.code!r}; "
                f"expected {expected_scope.value!r}"
            )

        if not self.reason:
            raise ValueError("anomaly reason must not be empty")

        self.severity = severity
        self.scope = scope
        self.paths = [str(path) for path in self.paths]


@dataclass
class SourceSubset:
    name: str
    relative_prefix: str
    images_dir: Path
    annotations_dir: Path


@dataclass
class SourceFingerprint:
    algorithm: str = "sha256"
    entries: list[dict[str, Any]] = field(default_factory=list)
    tree_sha256: str = ""
    verified_after_run: bool = False
    changed: list[str] = field(default_factory=list)


@dataclass
class SourceDataset:
    root: Path
    subsets: list[SourceSubset]
    image_files: list[Path]
    annotation_files: list[Path]
    fingerprint: SourceFingerprint = field(default_factory=SourceFingerprint)
    read_only: bool = True

    def __post_init__(self) -> None:
        if self.read_only is not True:
            raise ValueError("source dataset must always be read_only=True")
        self.read_only = True


@dataclass
class ImageAsset:
    asset_id: str
    subset: str
    relative_path: Path
    stem: str
    extension: str
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    status: ImageStatus | str = ImageStatus.DISCOVERED

    def __post_init__(self) -> None:
        extension = self.extension.lower()
        if extension not in IMAGE_EXTENSIONS:
            raise ValueError(f"unsupported image extension: {self.extension!r}")
        if self.width is not None and self.width < 0:
            raise ValueError("image width must be non-negative")
        if self.height is not None and self.height < 0:
            raise ValueError("image height must be non-negative")
        self.extension = extension
        self.status = ImageStatus(self.status)


@dataclass
class AnnotationAsset:
    asset_id: str
    subset: str
    relative_path: Path
    stem: str
    objects: list[SourceObject] = field(default_factory=list)
    declared_size: dict[str, int] | None = None
    declared_filename: str | None = None
    status: AnnotationStatus | str = AnnotationStatus.DISCOVERED

    def __post_init__(self) -> None:
        self.status = AnnotationStatus(self.status)


@dataclass
class BoundingBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    image_width: int
    image_height: int
    valid: bool = True
    reason: str | None = None
    normalized: dict[str, float] | None = None


@dataclass
class SourceObject:
    index: int
    class_name_raw: str
    class_name: str
    class_id: int | None
    bbox: BoundingBox
    yolo_line: str | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("object index must be non-negative")
        if self.class_id is not None and self.class_id not in range(6):
            raise ValueError("class_id must be in 0..5")


@dataclass
class MatchedSample:
    sample_id: str
    source_subset: str
    image: ImageAsset
    annotation: AnnotationAsset
    objects: list[SourceObject] = field(default_factory=list)
    present_classes: list[int] | None = None
    label_lines: list[str] = field(default_factory=list)
    state: SampleState | str = SampleState.PAIRED
    duplicate_group: str | None = None
    anomalies: list[AnomalyRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        expected_id = f"{self.source_subset}/{self.image.stem}"
        if self.sample_id != expected_id:
            raise ValueError(
                f"sample_id must be {expected_id!r} for subset "
                f"{self.source_subset!r} and stem {self.image.stem!r}"
            )
        if self.image.stem != self.annotation.stem:
            raise ValueError(
                "image and annotation stems must match within a MatchedSample"
            )

        if self.present_classes is None:
            derived = {
                obj.class_id
                for obj in self.objects
                if obj.class_id is not None
            }
            self.present_classes = sorted(derived)
        else:
            present = {int(class_id) for class_id in self.present_classes}
            if any(class_id not in range(6) for class_id in present):
                raise ValueError("present_classes must contain class IDs in 0..5")
            self.present_classes = sorted(present)

        self.state = SampleState(self.state)

    @property
    def object_count(self) -> int:
        return len(self.objects)


@dataclass
class DuplicateGroup:
    sha256: str
    members: list[str] = field(default_factory=list)
    labels_consistent: bool = True
    assigned_split: str | None = None
    state: DuplicateGroupState | str = DuplicateGroupState.GROUPED
    group_id: str = field(init=False)

    def __post_init__(self) -> None:
        digest = str(self.sha256).removeprefix("sha256:")
        if not digest:
            raise ValueError("duplicate group sha256 must not be empty")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError("duplicate group sha256 must be hexadecimal") from exc
        self.sha256 = f"sha256:{digest}"
        self.group_id = f"sha256:{digest}"
        self.members = sorted(self.members)
        if self.assigned_split is not None and self.assigned_split not in SPLIT_NAMES:
            raise ValueError("assigned_split must be train, validation or test")
        self.state = DuplicateGroupState(self.state)


@dataclass
class SplitAssignment:
    sample_id: str
    split: SplitName | str
    source_subset: str
    source_image: str
    source_xml: str
    output_image: str
    output_label: str
    sha256: str
    present_classes: list[int] = field(default_factory=list)
    object_count: int = 0

    def __post_init__(self) -> None:
        self.split = SplitName(self.split)
        present = {int(class_id) for class_id in self.present_classes}
        if any(class_id not in range(6) for class_id in present):
            raise ValueError("present_classes must contain class IDs in 0..5")
        self.present_classes = sorted(present)
        if self.object_count < 0:
            raise ValueError("object_count must be non-negative")


@dataclass
class Split:
    name: SplitName | str
    target_ratio: float
    actual_ratio: float = 0.0
    images: int = 0
    objects: int = 0
    image_counts_by_class: dict[int, int] = field(
        default_factory=lambda: {class_id: 0 for class_id in range(6)}
    )
    object_counts_by_class: dict[int, int] = field(
        default_factory=lambda: {class_id: 0 for class_id in range(6)}
    )
    source_subset_counts: dict[str, int] = field(default_factory=dict)
    assignments: list[SplitAssignment] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = SplitName(self.name)
        if self.target_ratio <= 0:
            raise ValueError("target_ratio must be positive")
        if not 0 <= self.actual_ratio <= 1:
            raise ValueError("actual_ratio must be in [0, 1]")
        if self.images < 0 or self.objects < 0:
            raise ValueError("images and objects must be non-negative")


@dataclass
class ValidationReport:
    schema_version: str = "1.0"
    feature: str = "001-neu-det-data-preparation"
    generated_at: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    gate: dict[str, Any] = field(default_factory=dict)
    anomalies: list[AnomalyRecord] = field(default_factory=list)


@dataclass
class SplitManifest:
    schema_version: str = "1.0"
    generated_at: str = ""
    dataset: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    classes: list[dict[str, object]] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)
    splits: dict[str, Split] = field(default_factory=dict)
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    invariants: dict[str, bool] = field(default_factory=dict)
