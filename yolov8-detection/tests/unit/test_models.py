"""Unit tests for shared entities and the anomaly taxonomy (T005)."""

from __future__ import annotations

from pathlib import Path

import pytest

from detection.data.models import (
    ANOMALY_ALLOWED_SEVERITIES,
    ANOMALY_CODES,
    ANOMALY_SCOPES,
    ANOMALY_SEVERITIES,
    ImageAsset,
    ImageStatus,
    AnnotationAsset,
    MatchedSample,
    AnomalyRecord,
    DuplicateGroup,
    DuplicateGroupState,
    SampleState,
    Severity,
    AnomalyScope,
    SourceDataset,
    SourceSubset,
)


EXPECTED_ANOMALY_CODES = (
    "missing_xml",
    "missing_image",
    "ambiguous_pairing",
    "invalid_xml",
    "unknown_class",
    "invalid_bbox",
    "corrupt_image",
    "empty_annotation",
    "size_mismatch",
    "filename_mismatch",
    "duplicate_content",
    "split_distribution_deviation",
    "split_class_absent",
    "source_tree_changed",
    "unsupported_file",
)


def test_anomaly_codes_match_data_model_order() -> None:
    assert ANOMALY_CODES == EXPECTED_ANOMALY_CODES


def test_anomaly_taxonomy_severity_and_scope_are_exact() -> None:
    expected = {
        "missing_xml": (Severity.ERROR, AnomalyScope.IMAGE),
        "missing_image": (Severity.ERROR, AnomalyScope.ANNOTATION),
        "ambiguous_pairing": (Severity.ERROR, AnomalyScope.SUBSET),
        "invalid_xml": (Severity.ERROR, AnomalyScope.ANNOTATION),
        "unknown_class": (Severity.ERROR, AnomalyScope.SAMPLE),
        "invalid_bbox": (Severity.ERROR, AnomalyScope.SAMPLE),
        "corrupt_image": (Severity.ERROR, AnomalyScope.IMAGE),
        "empty_annotation": (Severity.INFO, AnomalyScope.SAMPLE),
        "size_mismatch": (Severity.WARNING, AnomalyScope.SAMPLE),
        "filename_mismatch": (Severity.WARNING, AnomalyScope.ANNOTATION),
        "duplicate_content": (Severity.WARNING, AnomalyScope.SAMPLE),
        "split_distribution_deviation": (Severity.WARNING, AnomalyScope.SPLIT),
        "split_class_absent": (Severity.WARNING, AnomalyScope.SPLIT),
        "source_tree_changed": (Severity.ERROR, AnomalyScope.DATASET),
        "unsupported_file": (Severity.INFO, AnomalyScope.DATASET),
    }

    assert set(ANOMALY_SEVERITIES) == set(EXPECTED_ANOMALY_CODES)
    assert set(ANOMALY_SCOPES) == set(EXPECTED_ANOMALY_CODES)
    for code, (severity, scope) in expected.items():
        assert ANOMALY_SEVERITIES[code] == severity
        assert ANOMALY_SCOPES[code] == scope
        assert severity in ANOMALY_ALLOWED_SEVERITIES[code]


def test_duplicate_content_allows_warning_and_error() -> None:
    assert ANOMALY_ALLOWED_SEVERITIES["duplicate_content"] == frozenset(
        {Severity.WARNING, Severity.ERROR}
    )


def test_anomaly_record_validates_code_severity_and_scope() -> None:
    record = AnomalyRecord(
        code="missing_xml",
        severity="error",
        scope="image",
        source_subset="train",
        paths=["train/images/a.jpg"],
        reason="No XML with the same stem in subset 'train'",
        details={"stem": "a"},
    )
    assert record.severity is Severity.ERROR
    assert record.scope is AnomalyScope.IMAGE
    assert record.paths == ["train/images/a.jpg"]

    warning = AnomalyRecord(
        code="duplicate_content",
        severity=Severity.WARNING,
        scope=AnomalyScope.SAMPLE,
        reason="Same content, labels consistent",
    )
    assert warning.severity is Severity.WARNING

    with pytest.raises(ValueError, match="severity"):
        AnomalyRecord(
            code="missing_xml",
            severity="warning",
            scope="image",
            reason="wrong severity",
        )

    with pytest.raises(ValueError, match="scope"):
        AnomalyRecord(
            code="missing_xml",
            severity="error",
            scope="sample",
            reason="wrong scope",
        )

    with pytest.raises(ValueError, match="unknown anomaly code"):
        AnomalyRecord(
            code="not_a_code",
            severity="error",
            scope="dataset",
            reason="unknown",
        )


def _image(
    *,
    subset: str = "train",
    stem: str = "a",
    extension: str = ".jpg",
) -> ImageAsset:
    return ImageAsset(
        asset_id=f"{subset}/images/{stem}{extension}",
        subset=subset,
        relative_path=Path(f"images/{stem}{extension}"),
        stem=stem,
        extension=extension,
    )


def _annotation(*, subset: str = "train", stem: str = "a") -> AnnotationAsset:
    return AnnotationAsset(
        asset_id=f"{subset}/annotations/{stem}.xml",
        subset=subset,
        relative_path=Path(f"annotations/{stem}.xml"),
        stem=stem,
    )


def test_image_asset_accepts_only_supported_extensions() -> None:
    for extension in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"):
        asset = _image(extension=extension)
        assert asset.extension == extension
        assert asset.status is ImageStatus.DISCOVERED

    with pytest.raises(ValueError, match="unsupported image extension"):
        _image(extension=".gif")


def test_source_dataset_is_always_read_only() -> None:
    subset = SourceSubset(
        name="train",
        relative_prefix="train",
        images_dir=Path("/tmp/source/train/images"),
        annotations_dir=Path("/tmp/source/train/annotations"),
    )
    dataset = SourceDataset(
        root=Path("/tmp/source"),
        subsets=[subset],
        image_files=[],
        annotation_files=[],
    )
    assert dataset.read_only is True

    with pytest.raises(ValueError, match="read_only"):
        SourceDataset(
            root=Path("/tmp/source"),
            subsets=[subset],
            image_files=[],
            annotation_files=[],
            read_only=False,
        )


def test_matched_sample_id_and_present_classes_are_enforced() -> None:
    sample = MatchedSample(
        sample_id="train/a",
        source_subset="train",
        image=_image(),
        annotation=_annotation(),
        objects=[],
        present_classes=[2, 0, 2],
    )
    assert sample.object_count == 0
    assert sample.present_classes == [0, 2]
    assert sample.state is SampleState.PAIRED

    with pytest.raises(ValueError, match="sample_id"):
        MatchedSample(
            sample_id="validation/a",
            source_subset="train",
            image=_image(),
            annotation=_annotation(),
        )

    with pytest.raises(ValueError, match="stem"):
        MatchedSample(
            sample_id="train/a",
            source_subset="train",
            image=_image(stem="a"),
            annotation=_annotation(stem="b"),
        )


def test_duplicate_group_id_is_prefixed_and_members_are_sorted() -> None:
    group = DuplicateGroup(
        sha256="0b1f2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
        members=["train/b", "train/a"],
    )
    assert group.group_id.startswith("sha256:")
    assert group.group_id == f"sha256:{group.sha256.removeprefix('sha256:')}"
    assert group.members == ["train/a", "train/b"]
    assert group.state is DuplicateGroupState.GROUPED
