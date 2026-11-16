"""Integration tests for the US1 conversion journey (T012/T016).

All sources are synthetic trees under ``tmp_path`` built by
``tests/conftest.py``. The real NEU-DET dataset is never read or written.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from detection.cli import main


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _run(source: Path, output: Path, *extra: str) -> int:
    return main(
        ["prepare", "--source", str(source), "--output", str(output), *extra]
    )


def _build_us1_source(build_source_tree, tmp_path: Path) -> Path:
    return build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "objects": [
                        {"name": "crazing", "bbox": (20.0, 20.0, 80.0, 80.0)},
                        {"name": "patches", "bbox": (100.0, 100.0, 160.0, 160.0)},
                    ],
                },
                {
                    "stem": "b",
                    "objects": [{"name": "inclusion", "bbox": (40.0, 40.0, 120.0, 120.0)}],
                    "color": (200, 10, 10),
                },
                {"stem": "empty", "objects": [], "color": (10, 200, 10)},
            ],
            "validation": [
                {
                    "stem": "a",
                    "objects": [{"name": "scratches", "bbox": (0.0, 0.0, 200.0, 200.0)}],
                    "color": (10, 10, 200),
                },
                {
                    "stem": "c",
                    "objects": [
                        {"name": "pitted_surface", "bbox": (50.0, 50.0, 150.0, 150.0)}
                    ],
                    "color": (240, 240, 10),
                },
            ],
        },
    )


def test_cli_converts_paired_samples_into_interim_train_split(
    build_source_tree, tmp_path: Path
) -> None:
    source = _build_us1_source(build_source_tree, tmp_path)
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output) == 0

    image_dir = output / "images" / "train"
    label_dir = output / "labels" / "train"
    images = sorted(image_dir.iterdir())
    labels = sorted(label_dir.iterdir())

    assert len(images) == 5
    assert len(labels) == 5
    assert {path.stem for path in images} == {
        "train_a",
        "validation_a",
        "b",
        "empty",
        "c",
    }
    for image in images:
        label = label_dir / f"{image.stem}.txt"
        assert label.is_file()

    assert (label_dir / "train_a.txt").read_text(encoding="utf-8").splitlines() == [
        "0 0.250000 0.250000 0.300000 0.300000",
        "2 0.650000 0.650000 0.300000 0.300000",
    ]
    assert (label_dir / "validation_a.txt").read_text(
        encoding="utf-8"
    ).splitlines() == ["5 0.500000 0.500000 1.000000 1.000000"]
    assert (label_dir / "empty.txt").stat().st_size == 0

    assert (output / "images").is_dir()
    assert sorted(path.name for path in (output / "images").iterdir()) == ["train"]
    assert sorted(path.name for path in (output / "labels").iterdir()) == ["train"]

    assert not (output / "validation_report.json").exists()
    assert not (output / "split_manifest.json").exists()
    assert not (output / "dataset.yaml").exists()
    assert _tree_hashes(source) == before


def test_output_images_are_copies_not_links(build_source_tree, tmp_path: Path) -> None:
    source = _build_us1_source(build_source_tree, tmp_path)
    output = tmp_path / "processed"

    assert _run(source, output) == 0

    pairs = [
        (source / "train" / "images" / "b.jpg", output / "images" / "train" / "b.jpg"),
        (
            source / "validation" / "images" / "c.jpg",
            output / "images" / "train" / "c.jpg",
        ),
    ]
    for source_image, output_image in pairs:
        assert output_image.is_file()
        assert not output_image.is_symlink()
        assert source_image.read_bytes() == output_image.read_bytes()
        assert os.stat(source_image).st_ino != os.stat(output_image).st_ino


def test_non_empty_labels_are_utf8_and_newline_terminated(
    build_source_tree, tmp_path: Path
) -> None:
    source = _build_us1_source(build_source_tree, tmp_path)
    output = tmp_path / "processed"

    assert _run(source, output) == 0

    label_dir = output / "labels" / "train"
    for label in sorted(label_dir.iterdir()):
        raw = label.read_bytes()
        if label.name == "empty.txt":
            assert raw == b""
            continue
        text = raw.decode("utf-8")
        assert text.endswith("\n")
        assert "\r" not in text
        assert not text.endswith("\n\n")


@pytest.mark.parametrize(
    "scenario",
    [
        "missing_xml",
        "missing_image",
        "cross_subset",
        "invalid_bbox",
        "unknown_class",
        "malformed_xml",
    ],
)
def test_blocking_data_errors_exit_3_before_writing_output(
    build_source_tree, tmp_path: Path, scenario: str
) -> None:
    specs = {
        "missing_xml": {"train": [{"stem": "a", "write_xml": False}]},
        "missing_image": {"train": [{"stem": "a", "write_image": False}]},
        "cross_subset": {
            "train": [{"stem": "a", "write_xml": False}],
            "validation": [{"stem": "a", "write_image": False}],
        },
        "invalid_bbox": {
            "train": [
                {
                    "stem": "a",
                    "objects": [{"name": "crazing", "bbox": (80.0, 20.0, 80.0, 80.0)}],
                }
            ]
        },
        "unknown_class": {
            "train": [
                {
                    "stem": "a",
                    "objects": [{"name": "scratch", "bbox": (20.0, 20.0, 80.0, 80.0)}],
                }
            ]
        },
        "malformed_xml": {"train": [{"stem": "a", "xml_malformed": True}]},
    }[scenario]

    source = build_source_tree(tmp_path / "source", specs)
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output) == 3
    assert not (output / "images").exists()
    assert not (output / "labels").exists()
    assert _tree_hashes(source) == before


def test_existing_output_requires_overwrite_then_replaces_artifacts(
    build_source_tree, tmp_path: Path
) -> None:
    source = _build_us1_source(build_source_tree, tmp_path)
    output = tmp_path / "processed"
    output.mkdir()
    (output / "old.txt").write_text("old", encoding="utf-8")

    assert _run(source, output) == 4
    assert not (output / "images").exists()

    assert _run(source, output, "--overwrite") == 0
    assert (output / "images" / "train").is_dir()
    assert len(list((output / "images" / "train").iterdir())) == 5


def test_output_inside_source_exits_2_and_preserves_source(
    build_source_tree, tmp_path: Path
) -> None:
    source = _build_us1_source(build_source_tree, tmp_path)
    before = _tree_hashes(source)

    assert _run(source, source / "processed") == 2
    assert not (source / "processed").exists()
    assert _tree_hashes(source) == before


def test_structural_source_error_exits_2(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "train" / "images").mkdir(parents=True)
    (source / "train" / "images" / "a.jpg").write_bytes(b"placeholder")
    output = tmp_path / "processed"

    assert _run(source, output) == 2
    assert not (output / "images").exists()


def test_rerun_with_overwrite_is_deterministic(build_source_tree, tmp_path: Path) -> None:
    source = _build_us1_source(build_source_tree, tmp_path)
    output = tmp_path / "processed"

    assert _run(source, output) == 0
    first = _tree_hashes(output)

    assert _run(source, output, "--overwrite") == 0
    second = _tree_hashes(output)

    assert first == second
    assert len([name for name in second if name.startswith("images/train/")]) == 5
    assert len([name for name in second if name.startswith("labels/train/")]) == 5


def test_source_change_after_write_exits_3_and_discards_output(
    build_source_tree, tmp_path: Path, monkeypatch
) -> None:
    source = _build_us1_source(build_source_tree, tmp_path)
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    from detection.data import pipeline as pipeline_module

    real_fingerprint = pipeline_module.fingerprint_source

    def fingerprint_after_external_change(path: Path):
        # Simulate another process changing the source while the pipeline runs.
        target = source / "train" / "images" / "a.jpg"
        target.write_bytes(target.read_bytes() + b"\0")
        return real_fingerprint(path)

    monkeypatch.setattr(
        pipeline_module,
        "fingerprint_source",
        fingerprint_after_external_change,
    )

    assert _run(source, output) == 3
    assert not (output / "images").exists()
    assert not (output / "labels").exists()
    assert not output.exists()
    assert _tree_hashes(source) != before
