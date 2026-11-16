"""Unit tests for Pascal VOC XML -> YOLO label conversion (T011/T013).

Every XML fixture is written under ``tmp_path`` by the shared conftest helper.
No real dataset, no committed image and no source file outside ``tmp_path`` is
used.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pytest

from detection.data.converter import convert_annotation, format_yolo_line
from detection.data.models import Severity


def _convert(
    xml_path: Path,
    *,
    width: int = 200,
    height: int = 200,
    **kwargs: Any,
):
    return convert_annotation(
        xml_path,
        image_width=width,
        image_height=height,
        **kwargs,
    )


def _error_codes(result) -> list[str]:
    return [
        anomaly.code
        for anomaly in result.anomalies
        if anomaly.severity == Severity.ERROR
    ]


def test_single_object_uses_documented_formula(make_voc_xml, tmp_path: Path) -> None:
    xml = make_voc_xml(
        tmp_path / "a.xml",
        [{"name": "crazing", "bbox": (20.0, 20.0, 80.0, 80.0)}],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is True
    assert result.object_count == 1
    assert result.present_classes == [0]
    assert result.label_lines == ["0 0.250000 0.250000 0.300000 0.300000"]
    assert result.label_text == "0 0.250000 0.250000 0.300000 0.300000\n"
    assert _error_codes(result) == []


def test_multiple_objects_and_classes_keep_xml_order(make_voc_xml, tmp_path: Path) -> None:
    xml = make_voc_xml(
        tmp_path / "multi.xml",
        [
            {"name": "patches", "bbox": (10.0, 10.0, 50.0, 50.0)},
            {"name": "crazing", "bbox": (60.0, 60.0, 120.0, 120.0)},
            {"name": "scratches", "bbox": (130.0, 130.0, 190.0, 190.0)},
        ],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is True
    assert result.object_count == 3
    assert [obj.index for obj in result.objects] == [0, 1, 2]
    assert [obj.class_id for obj in result.objects] == [2, 0, 5]
    assert [obj.class_name for obj in result.objects] == [
        "patches",
        "crazing",
        "scratches",
    ]
    assert [line.split(" ")[0] for line in result.label_lines] == ["2", "0", "5"]
    assert result.present_classes == [0, 2, 5]
    assert result.label_lines == [
        "2 0.150000 0.150000 0.200000 0.200000",
        "0 0.450000 0.450000 0.300000 0.300000",
        "5 0.800000 0.800000 0.300000 0.300000",
    ]


def test_empty_annotation_is_valid_and_produces_zero_byte_label(
    make_voc_xml, tmp_path: Path
) -> None:
    xml = make_voc_xml(tmp_path / "empty.xml", [], size=(200, 200))

    result = _convert(xml)

    assert result.valid is True
    assert result.object_count == 0
    assert result.objects == []
    assert result.present_classes == []
    assert result.label_lines == []
    assert result.label_text == ""
    assert len(result.label_text.encode("utf-8")) == 0
    assert result.declared_size == {"width": 200, "height": 200}
    assert _error_codes(result) == []


def test_every_coordinate_has_exactly_six_decimals(make_voc_xml, tmp_path: Path) -> None:
    xml = make_voc_xml(
        tmp_path / "decimals.xml",
        [
            {"name": "inclusion", "bbox": (1.0, 2.0, 3.0, 4.0)},
            {"name": "pitted_surface", "bbox": (0.0, 0.0, 199.0, 199.0)},
        ],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is True
    for line in result.label_lines:
        fields = line.split(" ")
        assert len(fields) == 5
        assert fields[0] in {"0", "1", "2", "3", "4", "5"}
        for token in fields[1:]:
            assert re.fullmatch(r"\d+\.\d{6}", token), line


@pytest.mark.parametrize(
    "bbox",
    [
        (0.0, 0.0, 200.0, 200.0),
        (0.5, 0.5, 199.5, 199.5),
        (10.0, 190.0, 20.0, 200.0),
        (190.0, 0.0, 200.0, 10.0),
        (99.123, 45.678, 100.987, 46.543),
    ],
)
def test_normalized_values_stay_inside_documented_ranges(
    make_voc_xml, tmp_path: Path, bbox: tuple[float, float, float, float]
) -> None:
    xml = make_voc_xml(
        tmp_path / "ranges.xml",
        [{"name": "crazing", "bbox": bbox}],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is True
    assert len(result.label_lines) == 1
    _, cx, cy, w, h = result.label_lines[0].split(" ")
    cx, cy, w, h = float(cx), float(cy), float(w), float(h)
    assert 0.0 <= cx <= 1.0
    assert 0.0 <= cy <= 1.0
    assert 0.0 < w <= 1.0
    assert 0.0 < h <= 1.0


def test_bbox_touching_border_is_valid_and_never_clipped(
    make_voc_xml, tmp_path: Path
) -> None:
    xml = make_voc_xml(
        tmp_path / "border.xml",
        [{"name": "crazing", "bbox": (0.0, 0.0, 200.0, 200.0)}],
        size=(200, 200),
    )
    before = hashlib.sha256(xml.read_bytes()).hexdigest()

    result = _convert(xml)

    assert result.valid is True
    assert result.label_lines == ["0 0.500000 0.500000 1.000000 1.000000"]
    assert hashlib.sha256(xml.read_bytes()).hexdigest() == before


@pytest.mark.parametrize(
    "bbox",
    [
        (100.0, 20.0, 100.0, 80.0),
        (20.0, 100.0, 80.0, 100.0),
        (-1.0, 20.0, 80.0, 80.0),
        (20.0, -1.0, 80.0, 80.0),
        (20.0, 20.0, 201.0, 80.0),
        (20.0, 20.0, 80.0, 201.0),
        (-5.0, -5.0, -1.0, -1.0),
    ],
)
def test_invalid_bbox_invalidates_whole_sample_without_clipping(
    make_voc_xml, tmp_path: Path, bbox: tuple[float, float, float, float]
) -> None:
    xml = make_voc_xml(
        tmp_path / "bad_bbox.xml",
        [{"name": "crazing", "bbox": bbox}],
        size=(200, 200),
    )

    result = _convert(xml, sample_id="train/bad_bbox", source_subset="train")

    assert result.valid is False
    assert result.label_lines == []
    assert result.label_text == ""
    assert "invalid_bbox" in _error_codes(result)
    anomaly = next(item for item in result.anomalies if item.code == "invalid_bbox")
    assert anomaly.sample_id == "train/bad_bbox"
    assert anomaly.source_subset == "train"
    assert anomaly.details["object_index"] == 0
    assert anomaly.details["bbox"] == list(bbox)
    assert anomaly.details["image"] == {"width": 200, "height": 200}


@pytest.mark.parametrize(
    "bbox",
    [
        (10.0, 10.0, 10.0000004, 20.0),
        (10.0, 10.0, 20.0, 10.0000004),
    ],
)
def test_bbox_rounding_to_zero_size_is_invalid(
    make_voc_xml, tmp_path: Path, bbox: tuple[float, float, float, float]
) -> None:
    xml = make_voc_xml(
        tmp_path / "tiny.xml",
        [{"name": "scratches", "bbox": bbox}],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is False
    assert result.label_lines == []
    assert "invalid_bbox" in _error_codes(result)
    anomaly = next(item for item in result.anomalies if item.code == "invalid_bbox")
    assert "round" in anomaly.reason.lower() or "zero" in anomaly.reason.lower()


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "abc", ""])
def test_non_finite_or_non_numeric_coordinates_are_invalid(
    make_voc_xml, tmp_path: Path, value: str
) -> None:
    xml = make_voc_xml(
        tmp_path / "non_finite.xml",
        [{"name": "crazing", "bbox": (value, 20.0, 80.0, 80.0)}],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is False
    assert result.label_text == ""
    assert "invalid_bbox" in _error_codes(result)


def test_one_invalid_object_rejects_the_entire_sample(
    make_voc_xml, tmp_path: Path
) -> None:
    xml = make_voc_xml(
        tmp_path / "mixed.xml",
        [
            {"name": "inclusion", "bbox": (20.0, 20.0, 80.0, 80.0)},
            {"name": "patches", "bbox": (120.0, 20.0, 120.0, 80.0)},
            {"name": "scratches", "bbox": (20.0, 120.0, 80.0, 180.0)},
        ],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is False
    assert result.object_count == 3
    assert result.label_lines == []
    assert result.label_text == ""
    assert _error_codes(result) == ["invalid_bbox"]
    assert result.anomalies[0].details["object_index"] == 1


def test_unknown_class_rejects_whole_sample_without_remapping(
    make_voc_xml, tmp_path: Path
) -> None:
    xml = make_voc_xml(
        tmp_path / "unknown.xml",
        [
            {"name": "crazing", "bbox": (20.0, 20.0, 80.0, 80.0)},
            {"name": "Scratch", "bbox": (100.0, 100.0, 160.0, 160.0)},
        ],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is False
    assert result.label_lines == []
    assert "unknown_class" in _error_codes(result)
    unknown = next(item for item in result.anomalies if item.code == "unknown_class")
    assert unknown.details["name_raw"] == "Scratch"
    assert unknown.details["name_normalized"] == "scratch"
    assert result.objects[1].class_id is None


@pytest.mark.parametrize(
    ("raw", "expected_id"),
    [
        ("  PATCHES  ", 2),
        ("\tRolled-In_Scale\n", 4),
        (" pitted_surface ", 3),
        ("SCratches", 5),
    ],
)
def test_class_names_use_strip_lower_only(
    make_voc_xml, tmp_path: Path, raw: str, expected_id: int
) -> None:
    xml = make_voc_xml(
        tmp_path / "normalized.xml",
        [{"name": raw, "bbox": (10.0, 10.0, 50.0, 50.0)}],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is True
    assert result.objects[0].class_name_raw == raw
    assert result.objects[0].class_id == expected_id
    assert result.label_lines[0].startswith(f"{expected_id} ")


@pytest.mark.parametrize(
    "alias",
    ["pitted surface", "rolled_in_scale", "patch", "inclusions", "scratch", "crazingg"],
)
def test_aliases_and_fuzzy_class_names_are_rejected(
    make_voc_xml, tmp_path: Path, alias: str
) -> None:
    xml = make_voc_xml(
        tmp_path / "alias.xml",
        [{"name": alias, "bbox": (10.0, 10.0, 50.0, 50.0)}],
        size=(200, 200),
    )

    result = _convert(xml)

    assert result.valid is False
    assert result.label_text == ""
    assert _error_codes(result) == ["unknown_class"]


def test_malformed_xml_is_invalid_xml(make_voc_xml, tmp_path: Path) -> None:
    xml = make_voc_xml(tmp_path / "broken.xml", malformed=True)

    result = _convert(xml)

    assert result.valid is False
    assert result.objects == []
    assert result.label_text == ""
    assert _error_codes(result) == ["invalid_xml"]


@pytest.mark.parametrize("flag", ["omit_name", "omit_bndbox"])
def test_missing_required_object_structure_is_invalid_xml(
    make_voc_xml, tmp_path: Path, flag: str
) -> None:
    kwargs = {flag: True}
    xml = make_voc_xml(tmp_path / "missing.xml", [{"name": "crazing", "bbox": (10, 10, 50, 50)}], **kwargs)

    result = _convert(xml)

    assert result.valid is False
    assert result.label_text == ""
    assert "invalid_xml" in _error_codes(result)


def test_declared_size_and_filename_are_metadata_only(
    make_voc_xml, tmp_path: Path
) -> None:
    xml = make_voc_xml(
        tmp_path / "declared.xml",
        [{"name": "crazing", "bbox": (20.0, 20.0, 80.0, 80.0)}],
        size=(200, 200),
        declared_size=(400, 300),
        filename="elsewhere.jpg",
    )

    result = _convert(xml, width=200, height=200)

    assert result.valid is True
    assert result.declared_size == {"width": 400, "height": 300}
    assert result.declared_filename == "elsewhere.jpg"
    # Normalization must use the actual image size passed by the caller.
    assert result.label_lines == ["0 0.250000 0.250000 0.300000 0.300000"]


def test_anomaly_paths_use_supplied_source_path(make_voc_xml, tmp_path: Path) -> None:
    xml = make_voc_xml(
        tmp_path / "paths.xml",
        [{"name": "crazing", "bbox": (100.0, 20.0, 100.0, 80.0)}],
        size=(200, 200),
    )

    result = convert_annotation(
        xml,
        image_width=200,
        image_height=200,
        sample_id="train/paths",
        source_subset="train",
        source_path="train/annotations/paths.xml",
    )

    anomaly = result.anomalies[0]
    assert anomaly.paths == ["train/annotations/paths.xml"]


def test_format_yolo_line_uses_one_space_and_six_decimals() -> None:
    assert (
        format_yolo_line(3, 0.1234567, 0.5, 0.25, 1.0)
        == "3 0.123457 0.500000 0.250000 1.000000"
    )
