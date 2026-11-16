"""Shared pytest helpers for Feature 001 tests.

Every helper writes synthetic files under the path supplied by the caller
(normally pytest's ``tmp_path``). No binary fixture is committed to the
repository, and no helper reads or writes the real NEU-DET dataset.

The helpers are available in two ways:

* As plain functions, for example ``from conftest import make_image`` when a
  test needs to call them directly.
* As pytest fixtures with the same names, so tests can request ``make_image``,
  ``make_voc_xml`` or ``build_source_tree`` as arguments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import pytest
from PIL import Image

DEFAULT_SIZE: tuple[int, int] = (200, 200)
DEFAULT_COLOR: str | tuple[int, int, int] = (128, 128, 128)
DEFAULT_OBJECTS: list[dict[str, Any]] = [
    {"name": "crazing", "bbox": (20.0, 20.0, 80.0, 80.0)},
]


def _with_suffix(path: str | Path, default_suffix: str) -> Path:
    """Return *path* with *default_suffix* when it has no suffix yet."""
    result = Path(path)
    if not result.suffix:
        result = result.with_suffix(default_suffix)
    return result


def make_image(
    path: str | Path,
    size: tuple[int, int] = DEFAULT_SIZE,
    color: str | tuple[int, int, int] = DEFAULT_COLOR,
) -> Path:
    """Create a small RGB image at *path* and return the final path.

    The file extension selects the image format. When *path* has no suffix,
    ``.jpg`` is appended so a test can pass a bare stem.
    """
    target = _with_suffix(path, ".jpg")
    target.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    image = Image.new("RGB", (int(width), int(height)), color=color)
    image.save(target)
    return target


def _normalise_object(
    obj: Mapping[str, Any] | tuple[str, Sequence[float]],
) -> tuple[str, Sequence[float]]:
    """Normalise one object spec to ``(class_name, bbox)``."""
    if isinstance(obj, Mapping):
        try:
            return str(obj["name"]), obj["bbox"]
        except KeyError as exc:
            raise ValueError(
                "object mapping must contain 'name' and 'bbox'"
            ) from exc

    try:
        name, bbox = obj
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "object must be a mapping or a (name, bbox) pair"
        ) from exc
    return str(name), bbox


def make_voc_xml(
    path: str | Path,
    objects: Sequence[Mapping[str, Any] | tuple[str, Sequence[float]]] | None = None,
    size: tuple[int, int] = DEFAULT_SIZE,
    filename: str | None = None,
    *,
    declared_size: tuple[int, int] | None = None,
    malformed: bool = False,
    omit_name: bool = False,
    omit_bndbox: bool = False,
) -> Path:
    """Create a Pascal VOC annotation XML file and return the final path.

    Args:
        path: Target ``.xml`` path. ``.xml`` is appended when no suffix is given.
        objects: Object specs as ``{"name": ..., "bbox": (...)}`` mappings or
            ``(name, bbox)`` pairs. ``[]`` creates a valid empty annotation.
        size: Actual image size written to ``<size>`` by default.
        filename: Optional ``<filename>`` value. It is metadata only.
        declared_size: Optional different ``<size>`` value, useful for
            ``size_mismatch`` tests.
        malformed: Write intentionally unparsable XML.
        omit_name: Omit ``<name>`` from every object.
        omit_bndbox: Omit ``<bndbox>`` from every object.
    """
    target = _with_suffix(path, ".xml")
    target.parent.mkdir(parents=True, exist_ok=True)

    if malformed:
        target.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<annotation><object>\n',
            encoding="utf-8",
        )
        return target

    object_specs = list(DEFAULT_OBJECTS if objects is None else objects)
    declared_width, declared_height = declared_size or size

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<annotation>",
    ]
    if filename is not None:
        lines.append(f"  <filename>{escape(str(filename))}</filename>")
    lines.extend(
        [
            "  <size>",
            f"    <width>{int(declared_width)}</width>",
            f"    <height>{int(declared_height)}</height>",
            "    <depth>3</depth>",
            "  </size>",
        ]
    )

    for raw_object in object_specs:
        name, bbox = _normalise_object(raw_object)
        xmin, ymin, xmax, ymax = bbox
        lines.append("  <object>")
        if not omit_name:
            lines.append(f"    <name>{escape(name)}</name>")
        lines.extend(
            [
                "    <pose>Unspecified</pose>",
                "    <truncated>0</truncated>",
                "    <difficult>0</difficult>",
            ]
        )
        if not omit_bndbox:
            lines.extend(
                [
                    "    <bndbox>",
                    f"      <xmin>{xmin}</xmin>",
                    f"      <ymin>{ymin}</ymin>",
                    f"      <xmax>{xmax}</xmax>",
                    f"      <ymax>{ymax}</ymax>",
                    "    </bndbox>",
                ]
            )
        lines.append("  </object>")

    lines.append("</annotation>")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def build_source_tree(
    root: str | Path,
    subsets: Mapping[str | None, Sequence[Mapping[str, Any]]],
) -> Path:
    """Build a synthetic NEU-DET-like source tree and return its root.

    ``subsets`` maps a subset name to a sequence of sample specs. ``None``,
    ``""`` or ``"root"`` writes the single-subset layout
    ``<root>/images`` and ``<root>/annotations``. Any other name writes
    ``<root>/<name>/images`` and ``<root>/<name>/annotations``.

    Supported sample-spec keys:
        ``stem`` (required), ``objects``, ``size``, ``color``,
        ``write_image`` (default ``True``), ``write_xml`` (default ``True``),
        ``image_ext`` (default ``".jpg"``), ``xml_filename``,
        ``xml_malformed``, ``declared_size``, ``omit_name``, ``omit_bndbox``.

    Using the same ``stem`` in two subsets creates the cross-subset duplicate
    stem case. Setting ``write_xml=False`` creates an image without XML;
    setting ``write_image=False`` creates XML without an image.
    """
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)

    for subset_name, samples in subsets.items():
        if subset_name in (None, "", "root"):
            images_dir = root_path / "images"
            annotations_dir = root_path / "annotations"
        else:
            images_dir = root_path / str(subset_name) / "images"
            annotations_dir = root_path / str(subset_name) / "annotations"

        images_dir.mkdir(parents=True, exist_ok=True)
        annotations_dir.mkdir(parents=True, exist_ok=True)

        for spec in samples:
            stem = str(spec["stem"])
            size = tuple(spec.get("size", DEFAULT_SIZE))
            color = spec.get("color", DEFAULT_COLOR)
            objects = spec.get("objects", DEFAULT_OBJECTS)

            if spec.get("write_image", True):
                image_ext = str(spec.get("image_ext", ".jpg"))
                make_image(images_dir / f"{stem}{image_ext}", size, color)

            if spec.get("write_xml", True):
                make_voc_xml(
                    annotations_dir / f"{stem}.xml",
                    objects,
                    size,
                    spec.get("xml_filename"),
                    declared_size=spec.get("declared_size"),
                    malformed=bool(spec.get("xml_malformed", False)),
                    omit_name=bool(spec.get("omit_name", False)),
                    omit_bndbox=bool(spec.get("omit_bndbox", False)),
                )

    return root_path


@pytest.fixture(name="make_image")
def make_image_fixture():
    """Expose :func:`make_image` as a pytest fixture."""
    return make_image


@pytest.fixture(name="make_voc_xml")
def make_voc_xml_fixture():
    """Expose :func:`make_voc_xml` as a pytest fixture."""
    return make_voc_xml


@pytest.fixture(name="build_source_tree")
def build_source_tree_fixture():
    """Expose :func:`build_source_tree` as a pytest fixture."""
    return build_source_tree
