"""Integration tests for US1 (T012/T016), US2 (T019) and US3 (T027).

All sources are synthetic trees under ``tmp_path`` built by
``tests/conftest.py``. The real NEU-DET dataset is never read or written.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from detection.cli import main
from detection.data.classes import CLASS_NAMES


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _dataset_hashes(root: Path) -> dict[str, str]:
    """Dataset artifacts only; ``generated_at`` makes the report non-byte-stable."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "validation_report.json"
    }


def _read_report(output: Path) -> dict[str, Any]:
    report_path = output / "validation_report.json"
    assert report_path.is_file(), f"missing {report_path}"
    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    return payload


def _assert_report_only(output: Path) -> dict[str, Any]:
    """Failure output has a report but no dataset artifacts."""
    report = _read_report(output)
    assert not (output / "images").exists()
    assert not (output / "labels").exists()
    assert not (output / "split_manifest.json").exists()
    return report


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

    report = _read_report(output)
    assert report["feature"] == "001-neu-det-data-preparation"
    assert report["gate"]["status"] == "pass"
    assert report["summary"]["written_samples"] == 5
    assert report["summary"]["accounted_images"] == 5
    assert report["summary"]["accounting_ok"] is True
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
    first = _dataset_hashes(output)
    first_report_path = output / "validation_report.json"
    first_report = (
        json.loads(first_report_path.read_text(encoding="utf-8"))
        if first_report_path.is_file()
        else None
    )

    assert _run(source, output, "--overwrite") == 0
    second = _dataset_hashes(output)
    second_report_path = output / "validation_report.json"
    second_report = (
        json.loads(second_report_path.read_text(encoding="utf-8"))
        if second_report_path.is_file()
        else None
    )

    assert first == second
    if first_report is not None and second_report is not None:
        first_report.pop("generated_at", None)
        second_report.pop("generated_at", None)
        assert first_report == second_report
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
    report = _assert_report_only(output)
    assert report["source"]["fingerprint"]["status"] == "changed"
    assert any(
        anomaly["code"] == "source_tree_changed" for anomaly in report["anomalies"]
    )
    assert _tree_hashes(source) != before


# --- T019: US2 validation report, gate, quarantine and overwrite -----------


def _build_invalid_sample() -> dict[str, Any]:
    return {
        "stem": "bad",
        "objects": [{"name": "crazing", "bbox": (80.0, 20.0, 80.0, 80.0)}],
        "color": (200, 10, 10),
    }


def _build_valid_sample(stem: str = "good") -> dict[str, Any]:
    return {
        "stem": stem,
        "objects": [{"name": "crazing", "bbox": (20.0, 20.0, 80.0, 80.0)}],
        "color": (10, 10, 200),
    }


def test_us2_blocking_error_creates_report_only_output(
    build_source_tree, tmp_path: Path
) -> None:
    source = build_source_tree(
        tmp_path / "source", {"train": [_build_invalid_sample()]}
    )
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output) == 3
    report = _assert_report_only(output)

    assert report["gate"]["status"] == "fail"
    assert report["summary"]["anomaly_counts"]["invalid_bbox"] == 1
    assert report["summary"]["unwritten_samples"] == 1
    assert report["summary"]["quarantined_samples"] == 0
    assert report["summary"]["accounting_ok"] is True
    assert _tree_hashes(source) == before


def test_us2_quarantine_copies_only_paired_invalid_samples(
    build_source_tree, tmp_path: Path
) -> None:
    source = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                _build_valid_sample(),
                _build_invalid_sample(),
                {
                    "stem": "orphan",
                    "write_xml": False,
                    "objects": [],
                    "color": (10, 200, 10),
                },
            ]
        },
    )
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output, "--on-anomaly", "quarantine") == 0
    report = _read_report(output)

    assert report["gate"]["status"] == "pass_with_quarantine"
    assert report["gate"]["blocking_errors"] > 0
    assert report["summary"]["written_samples"] == 1
    assert report["summary"]["quarantined_samples"] == 1
    assert report["summary"]["unwritten_samples"] == 0
    assert report["summary"]["unpaired_images"] == 1
    assert report["summary"]["accounted_images"] == 3
    assert report["summary"]["accounting_ok"] is True

    rejected_image = output / "rejected" / "images" / "train" / "bad.jpg"
    rejected_xml = output / "rejected" / "annotations" / "train" / "bad.xml"
    assert rejected_image.read_bytes() == (
        source / "train" / "images" / "bad.jpg"
    ).read_bytes()
    assert rejected_xml.read_bytes() == (
        source / "train" / "annotations" / "bad.xml"
    ).read_bytes()
    assert not (output / "rejected" / "images" / "train" / "good.jpg").exists()
    assert not (output / "rejected" / "images" / "train" / "orphan.jpg").exists()
    assert not (output / "rejected" / "annotations" / "train" / "orphan.xml").exists()

    assert [path.name for path in (output / "images" / "train").iterdir()] == [
        "good.jpg"
    ]
    assert [path.name for path in (output / "labels" / "train").iterdir()] == [
        "good.txt"
    ]
    assert not (output / "split_manifest.json").exists()
    assert _tree_hashes(source) == before


def test_us2_all_quarantined_exits_3_with_report_and_rejected(
    build_source_tree, tmp_path: Path
) -> None:
    source = build_source_tree(
        tmp_path / "source", {"train": [_build_invalid_sample()]}
    )
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output, "--on-anomaly", "quarantine") == 3
    report = _assert_report_only(output)

    assert report["gate"]["status"] == "fail"
    assert report["summary"]["written_samples"] == 0
    assert report["summary"]["quarantined_samples"] == 1
    assert report["summary"]["unwritten_samples"] == 0
    assert report["summary"]["accounting_ok"] is True
    assert (output / "rejected" / "images" / "train" / "bad.jpg").is_file()
    assert (output / "rejected" / "annotations" / "train" / "bad.xml").is_file()
    assert _tree_hashes(source) == before


def test_us2_unpaired_error_with_eligible_sample_still_exits_0(
    build_source_tree, tmp_path: Path
) -> None:
    source = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                _build_valid_sample(),
                {"stem": "orphan", "write_xml": False, "objects": []},
            ]
        },
    )
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output) == 0
    report = _read_report(output)

    assert report["gate"]["status"] == "pass_with_quarantine"
    assert report["summary"]["anomaly_counts"]["missing_xml"] == 1
    assert report["summary"]["unpaired_images"] == 1
    assert report["summary"]["written_samples"] == 1
    assert report["summary"]["accounted_images"] == 2
    assert report["summary"]["accounting_ok"] is True
    assert [path.name for path in (output / "images" / "train").iterdir()] == [
        "good.jpg"
    ]
    assert not (output / "rejected").exists()
    assert _tree_hashes(source) == before


def test_us2_report_config_reflects_cli_options(
    build_source_tree, tmp_path: Path
) -> None:
    source = build_source_tree(
        tmp_path / "source", {"train": [_build_valid_sample()]}
    )
    output = tmp_path / "processed"

    assert (
        _run(
            source,
            output,
            "--seed",
            "7",
            "--ratios",
            "0.5,0.3,0.2",
            "--on-anomaly",
            "quarantine",
        )
        == 0
    )
    config = _read_report(output)["config"]

    assert config["seed"] == 7
    assert config["ratios"] == {"train": 0.5, "validation": 0.3, "test": 0.2}
    assert config["on_anomaly"] == "quarantine"
    assert [entry["id"] for entry in config["class_mapping"]] == list(range(6))


@pytest.mark.parametrize("layout", ["equal", "inside", "parent"])
def test_us2_output_path_relations_exit_2_without_writes(
    build_source_tree, tmp_path: Path, layout: str
) -> None:
    source = build_source_tree(
        tmp_path / "source", {"train": [_build_valid_sample()]}
    )
    output = {
        "equal": source,
        "inside": source / "processed",
        "parent": tmp_path,
    }[layout]
    before = _tree_hashes(source)

    assert _run(source, output) == 2
    assert not (output / "validation_report.json").exists()
    assert not (output / "images").exists()
    assert not (output / "labels").exists()
    assert not (output / "split_manifest.json").exists()
    assert _tree_hashes(source) == before


@pytest.mark.parametrize("missing", ["images", "annotations"])
def test_us2_subset_with_only_one_side_exits_2(tmp_path: Path, missing: str) -> None:
    source = tmp_path / "source"
    present = "annotations" if missing == "images" else "images"
    (source / "train" / present).mkdir(parents=True)
    if present == "images":
        (source / "train" / "images" / "a.jpg").write_bytes(b"placeholder")
    else:
        (source / "train" / "annotations" / "a.xml").write_text(
            "<annotation/>\n", encoding="utf-8"
        )
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output) == 2
    assert not (output / "validation_report.json").exists()
    assert not (output / "images").exists()
    assert _tree_hashes(source) == before


def test_us2_unsupported_extension_is_ignored_and_recorded(
    build_source_tree, tmp_path: Path
) -> None:
    source = build_source_tree(
        tmp_path / "source", {"train": [_build_valid_sample()]}
    )
    (source / "train" / "images" / "notes.txt").write_text(
        "not an image", encoding="utf-8"
    )
    output = tmp_path / "processed"
    before = _tree_hashes(source)

    assert _run(source, output) == 0
    report = _read_report(output)

    assert report["summary"]["anomaly_counts"]["unsupported_file"] == 1
    assert any(
        anomaly["code"] == "unsupported_file" for anomaly in report["anomalies"]
    )
    assert len(list((output / "images" / "train").iterdir())) == 1
    assert _tree_hashes(source) == before


def test_us2_overwrite_with_failing_input_preserves_previous_dataset(
    build_source_tree, tmp_path: Path
) -> None:
    valid_source = build_source_tree(
        tmp_path / "source", {"train": [_build_valid_sample()]}
    )
    failing_source = build_source_tree(
        tmp_path / "failing_source", {"train": [_build_invalid_sample()]}
    )
    output = tmp_path / "processed"
    before_valid = _tree_hashes(valid_source)
    before_failing = _tree_hashes(failing_source)

    assert _run(valid_source, output) == 0
    previous_report = _read_report(output)
    previous_hashes = _tree_hashes(output)

    assert _run(failing_source, output, "--overwrite") == 3
    failed_report = _assert_report_only(output)
    backup = tmp_path / "processed.previous"
    assert (backup / "images" / "train" / "good.jpg").is_file()
    assert (backup / "labels" / "train" / "good.txt").is_file()
    assert _tree_hashes(backup)["validation_report.json"] == previous_hashes[
        "validation_report.json"
    ]
    assert (
        failed_report["source"]["fingerprint"]["tree_sha256"]
        != previous_report["source"]["fingerprint"]["tree_sha256"]
    )

    assert _run(failing_source, output) == 4
    assert _read_report(output) == failed_report

    assert _run(valid_source, output, "--overwrite") == 0
    final_report = _read_report(output)
    assert final_report["gate"]["status"] == "pass"
    assert final_report["source"]["fingerprint"]["tree_sha256"] == (
        previous_report["source"]["fingerprint"]["tree_sha256"]
    )
    assert (output / "images" / "train" / "good.jpg").is_file()
    assert _tree_hashes(valid_source) == before_valid
    assert _tree_hashes(failing_source) == before_failing


# --- T027: US3 end-to-end split journey ------------------------------------


def _build_us3_source(build_source_tree, tmp_path: Path) -> Path:
    """Twenty valid samples spread over two source subsets."""

    def specs(
        prefix: str, count: int, class_offset: int, color_offset: int
    ) -> list[dict[str, Any]]:
        return [
            {
                "stem": f"{prefix}{index:02d}",
                "objects": [
                    {
                        "name": CLASS_NAMES[(class_offset + index) % len(CLASS_NAMES)],
                        "bbox": (20.0, 20.0, 80.0, 80.0),
                    }
                ],
                "color": (
                    color_offset + index,
                    color_offset + 10 + index,
                    color_offset + 20 + index,
                ),
            }
            for index in range(count)
        ]

    return build_source_tree(
        tmp_path / "source",
        {
            "train": specs("t", 15, 0, 10),
            "validation": specs("v", 5, 3, 60),
        },
    )


def _read_manifest(output: Path) -> dict[str, Any]:
    manifest_path = output / "split_manifest.json"
    assert manifest_path.is_file(), f"missing {manifest_path} (US3 not implemented yet)"
    payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return payload


def _split_ids(manifest: dict[str, Any], split: str) -> list[str]:
    return [
        str(assignment["sample_id"])
        for assignment in manifest["splits"][split]["assignments"]
    ]


def _require_splitter() -> Any:
    try:
        module = importlib.import_module("detection.data.splitter")
    except ModuleNotFoundError as exc:
        pytest.fail(f"US3 splitter is not implemented yet: {exc}")
    entry = getattr(module, "split_samples", None)
    if not callable(entry):
        pytest.fail("detection.data.splitter has no split_samples entry point yet")
    return entry


def test_us3_two_runs_with_same_seed_produce_identical_split_lists(
    build_source_tree, tmp_path: Path
) -> None:
    source = _build_us3_source(build_source_tree, tmp_path)
    before = _tree_hashes(source)
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    args = ("--seed", "42", "--ratios", "0.75,0.15,0.10")

    assert _run(source, first_output, *args) == 0
    assert _run(source, second_output, *args) == 0
    first = _read_manifest(first_output)
    second = _read_manifest(second_output)

    first.pop("generated_at", None)
    second.pop("generated_at", None)
    assert first == second
    for split in ("train", "validation", "test"):
        assert _split_ids(first, split) == _split_ids(second, split)
    assert _tree_hashes(source) == before


def test_us3_manifest_splits_are_disjoint_and_files_match_counts(
    build_source_tree, tmp_path: Path
) -> None:
    source = _build_us3_source(build_source_tree, tmp_path)
    output = tmp_path / "processed"

    assert _run(source, output) == 0
    manifest = _read_manifest(output)

    id_sets = {split: set(_split_ids(manifest, split)) for split in ("train", "validation", "test")}
    assert not (id_sets["train"] & id_sets["validation"])
    assert not (id_sets["train"] & id_sets["test"])
    assert not (id_sets["validation"] & id_sets["test"])
    assert len(id_sets["train"] | id_sets["validation"] | id_sets["test"]) == 20
    assert sum(len(ids) for ids in id_sets.values()) == 20

    for split in ("train", "validation", "test"):
        assignments = manifest["splits"][split]["assignments"]
        assert manifest["splits"][split]["images"] == len(assignments)
        images = sorted((output / "images" / split).iterdir())
        labels = sorted((output / "labels" / split).iterdir())
        assert len(images) == len(assignments)
        assert len(labels) == len(assignments)
        assert {path.stem for path in images} == {path.stem for path in labels}


def test_us3_invalid_ratios_exit_2_and_leave_no_manifest(
    build_source_tree, tmp_path: Path
) -> None:
    source = _build_us3_source(build_source_tree, tmp_path)
    good_output = tmp_path / "good"
    before = _tree_hashes(source)

    assert _run(source, good_output) == 0
    good_manifest = _read_manifest(good_output)

    invalid = [
        "0.75,0.15,0",
        "0.5,0.3",
        "0.5,0.3,0.3",
    ]
    for index, ratios in enumerate(invalid):
        output = tmp_path / f"bad_{index}"
        assert _run(source, output, "--ratios", ratios) == 2
        assert not (output / "split_manifest.json").exists()
        assert not (output / "images").exists()
        assert not (output / "labels").exists()

    assert _read_manifest(good_output) == good_manifest
    assert _tree_hashes(source) == before


def test_us3_source_change_after_write_exits_3_without_manifest(
    build_source_tree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _build_us3_source(build_source_tree, tmp_path)
    good_output = tmp_path / "good"
    assert _run(source, good_output) == 0
    _read_manifest(good_output)

    from detection.data import pipeline as pipeline_module

    real_fingerprint = pipeline_module.fingerprint_source

    def fingerprint_after_external_change(path: Path):
        target = source / "train" / "images" / "t00.jpg"
        target.write_bytes(target.read_bytes() + b"\0")
        return real_fingerprint(path)

    monkeypatch.setattr(
        pipeline_module,
        "fingerprint_source",
        fingerprint_after_external_change,
    )

    output = tmp_path / "changed"
    assert _run(source, output) == 3
    report = _assert_report_only(output)
    assert report["source"]["fingerprint"]["status"] == "changed"
    assert not (output / "split_manifest.json").exists()
    assert _read_manifest(good_output)


def test_us3_split_invariant_failure_exits_3_without_manifest(
    build_source_tree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _build_us3_source(build_source_tree, tmp_path)
    original_split_samples = _require_splitter()

    def broken_split_samples(*args: Any, **kwargs: Any) -> Any:
        result = original_split_samples(*args, **kwargs)
        result.invariants["pairwise_disjoint_sha256"] = False
        return result

    monkeypatch.setattr(
        importlib.import_module("detection.data.splitter"),
        "split_samples",
        broken_split_samples,
    )
    pipeline = importlib.import_module("detection.data.pipeline")
    if hasattr(pipeline, "split_samples"):
        monkeypatch.setattr(pipeline, "split_samples", broken_split_samples)

    output = tmp_path / "processed"
    assert _run(source, output) == 3
    _read_report(output)
    assert not (output / "split_manifest.json").exists()
