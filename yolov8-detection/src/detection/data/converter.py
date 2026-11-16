"""Pascal VOC annotation parsing and YOLO label conversion (T013).

The converter works entirely in memory. It never writes to, renames, moves or
deletes a source file, never clips a bounding box and never repairs an invalid
object. Output lines keep the original ``<object>`` order and use exactly six
decimal places: ``class_id cx cy w h``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from .classes import UnknownClassError, get_class_id, normalize_class_name
from .models import AnomalyRecord, BoundingBox, Severity, SourceObject

YOLO_DECIMALS = 6
YOLO_LINE_FORMAT = "{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
_BBOX_TAGS = ("xmin", "ymin", "xmax", "ymax")


@dataclass
class ConversionResult:
    """In-memory conversion outcome for one matched sample."""

    valid: bool
    objects: list[SourceObject] = field(default_factory=list)
    label_lines: list[str] = field(default_factory=list)
    present_classes: list[int] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    declared_size: dict[str, int] | None = None
    declared_filename: str | None = None

    @property
    def object_count(self) -> int:
        return len(self.objects)

    @property
    def label_text(self) -> str:
        return "".join(f"{line}\n" for line in self.label_lines)


def format_yolo_line(
    class_id: int,
    cx: float,
    cy: float,
    w: float,
    h: float,
) -> str:
    """Format one YOLO label line with single spaces and six decimals."""
    return YOLO_LINE_FORMAT.format(class_id=int(class_id), cx=cx, cy=cy, w=w, h=h)


def _rounded(value: float) -> float:
    """Round exactly the way the six-decimal output does."""
    return float(f"{value:.{YOLO_DECIMALS}f}")


def _anomaly(
    code: str,
    scope: str,
    *,
    path: str,
    reason: str,
    sample_id: str | None,
    source_subset: str | None,
    details: dict[str, object] | None = None,
) -> AnomalyRecord:
    return AnomalyRecord(
        code=code,
        severity="error",
        scope=scope,
        sample_id=sample_id,
        source_subset=source_subset,
        paths=[path],
        reason=reason,
        details=details or {},
    )


def _invalid_xml(
    path: str,
    sample_id: str | None,
    source_subset: str | None,
    reason: str,
    details: dict[str, object] | None = None,
) -> AnomalyRecord:
    return _anomaly(
        "invalid_xml",
        "annotation",
        path=path,
        reason=reason,
        sample_id=sample_id,
        source_subset=source_subset,
        details=details,
    )


def _declared_size(root: ElementTree.Element) -> dict[str, int] | None:
    size = root.find("size")
    if size is None:
        return None
    width_text = size.findtext("width")
    height_text = size.findtext("height")
    if width_text is None or height_text is None:
        return None
    try:
        width = int(float(width_text.strip()))
        height = int(float(height_text.strip()))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return {"width": width, "height": height}


def _validate_bbox(
    coords: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> BoundingBox:
    """Validate one bounding box and normalize it without clipping."""
    xmin, ymin, xmax, ymax = coords
    bbox = BoundingBox(
        xmin=xmin,
        ymin=ymin,
        xmax=xmax,
        ymax=ymax,
        image_width=image_width,
        image_height=image_height,
    )

    if xmin >= xmax:
        bbox.valid = False
        bbox.reason = "xmin must be less than xmax"
        return bbox
    if ymin >= ymax:
        bbox.valid = False
        bbox.reason = "ymin must be less than ymax"
        return bbox
    if xmin < 0 or ymin < 0:
        bbox.valid = False
        bbox.reason = "bbox coordinates must be non-negative"
        return bbox
    if xmax > image_width or ymax > image_height:
        bbox.valid = False
        bbox.reason = "bbox exceeds image bounds"
        return bbox

    cx = _rounded((xmin + xmax) / 2 / image_width)
    cy = _rounded((ymin + ymax) / 2 / image_height)
    width = _rounded((xmax - xmin) / image_width)
    height = _rounded((ymax - ymin) / image_height)

    if width <= 0 or height <= 0:
        bbox.valid = False
        bbox.reason = "bbox width or height rounds to zero at 6 decimals"
        return bbox
    if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < width <= 1 and 0 < height <= 1):
        bbox.valid = False
        bbox.reason = "normalized bbox is outside the documented ranges"
        return bbox

    bbox.normalized = {"cx": cx, "cy": cy, "w": width, "h": height}
    return bbox


def convert_annotation(
    xml_path: str | Path,
    *,
    image_width: int,
    image_height: int,
    sample_id: str | None = None,
    source_subset: str | None = None,
    source_path: str | None = None,
) -> ConversionResult:
    """Parse one VOC XML file and convert it to YOLO label lines.

    Args:
        xml_path: Existing XML file to read. It is opened read-only.
        image_width: Actual image width; the only width used for normalization.
        image_height: Actual image height.
        sample_id: Optional ``<subset>/<stem>`` used in anomaly records.
        source_subset: Optional source subset used in anomaly records.
        source_path: Optional relative path used in anomaly records.

    Returns:
        A :class:`ConversionResult`. When any object fails, ``valid`` is
        ``False`` and no label lines are produced at all.
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_width and image_height must be positive")

    path = Path(xml_path)
    label_path = source_path or path.name

    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError) as exc:
        return ConversionResult(
            valid=False,
            anomalies=[
                _invalid_xml(
                    label_path,
                    sample_id,
                    source_subset,
                    f"cannot parse XML: {exc}",
                )
            ],
        )

    if root.tag != "annotation":
        return ConversionResult(
            valid=False,
            anomalies=[
                _invalid_xml(
                    label_path,
                    sample_id,
                    source_subset,
                    f"unexpected root element <{root.tag}>; expected <annotation>",
                )
            ],
        )

    declared_size = _declared_size(root)
    filename_text = root.findtext("filename")
    declared_filename = (
        filename_text.strip() if filename_text is not None and filename_text.strip() else None
    )

    objects: list[SourceObject] = []
    anomalies: list[AnomalyRecord] = []

    for index, element in enumerate(root.findall("object")):
        name_element = element.find("name")
        if name_element is None:
            anomalies.append(
                _invalid_xml(
                    label_path,
                    sample_id,
                    source_subset,
                    f"object {index} is missing the required <name> element",
                    {"object_index": index},
                )
            )
            continue

        raw_name = name_element.text or ""
        normalized_name = normalize_class_name(raw_name)

        bndbox = element.find("bndbox")
        if bndbox is None:
            anomalies.append(
                _invalid_xml(
                    label_path,
                    sample_id,
                    source_subset,
                    f"object {index} is missing the required <bndbox> element",
                    {"object_index": index},
                )
            )
            continue

        coordinate_texts: dict[str, str] = {}
        missing_tags = [
            tag for tag in _BBOX_TAGS if bndbox.find(tag) is None
        ]
        if missing_tags:
            anomalies.append(
                _invalid_xml(
                    label_path,
                    sample_id,
                    source_subset,
                    (
                        f"object {index} <bndbox> is missing "
                        f"{', '.join(f'<{tag}>' for tag in missing_tags)}"
                    ),
                    {"object_index": index, "missing": missing_tags},
                )
            )
            continue
        for tag in _BBOX_TAGS:
            coordinate_texts[tag] = bndbox.findtext(tag) or ""

        parse_error: str | None = None
        try:
            coords = tuple(
                float(coordinate_texts[tag].strip()) for tag in _BBOX_TAGS
            )
        except (TypeError, ValueError):
            coords = None
            parse_error = "bbox coordinate is not a number"
        if coords is not None and not all(math.isfinite(value) for value in coords):
            coords = None
            parse_error = "bbox coordinate is not a finite number"

        try:
            class_id: int | None = get_class_id(raw_name)
        except UnknownClassError:
            class_id = None
            anomalies.append(
                _anomaly(
                    "unknown_class",
                    "sample",
                    path=label_path,
                    reason=(
                        f"object {index} class {raw_name!r} is not one of the six "
                        "fixed NEU-DET classes"
                    ),
                    sample_id=sample_id,
                    source_subset=source_subset,
                    details={
                        "object_index": index,
                        "name_raw": raw_name,
                        "name_normalized": normalized_name,
                    },
                )
            )

        if coords is None:
            anomalies.append(
                _anomaly(
                    "invalid_bbox",
                    "sample",
                    path=label_path,
                    reason=f"object {index}: {parse_error}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    details={
                        "object_index": index,
                        "bbox": [coordinate_texts[tag] for tag in _BBOX_TAGS],
                        "image": {"width": image_width, "height": image_height},
                    },
                )
            )
            continue

        bbox = _validate_bbox(coords, image_width, image_height)
        source_object = SourceObject(
            index=index,
            class_name_raw=raw_name,
            class_name=normalized_name,
            class_id=class_id,
            bbox=bbox,
        )
        objects.append(source_object)

        if not bbox.valid:
            anomalies.append(
                _anomaly(
                    "invalid_bbox",
                    "sample",
                    path=label_path,
                    reason=f"object {index}: {bbox.reason}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    details={
                        "object_index": index,
                        "class_name": normalized_name,
                        "bbox": list(coords),
                        "image": {"width": image_width, "height": image_height},
                    },
                )
            )

    valid = not any(
        anomaly.severity == Severity.ERROR for anomaly in anomalies
    )

    label_lines: list[str] = []
    if valid:
        for source_object in objects:
            normalized = source_object.bbox.normalized
            if normalized is None or source_object.class_id is None:
                valid = False
                break
            line = format_yolo_line(
                source_object.class_id,
                normalized["cx"],
                normalized["cy"],
                normalized["w"],
                normalized["h"],
            )
            source_object.yolo_line = line
            label_lines.append(line)

    present_classes = sorted(
        {
            source_object.class_id
            for source_object in objects
            if source_object.class_id is not None
        }
    )

    return ConversionResult(
        valid=valid,
        objects=objects,
        label_lines=label_lines if valid else [],
        present_classes=present_classes,
        anomalies=anomalies,
        declared_size=declared_size,
        declared_filename=declared_filename,
    )
