"""Unit tests for the shared atomic JSON writer, config and reports (T009/T018/T026)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import detection.data.manifest as manifest_module
from detection.data.classes import CLASS_NAMES
from detection.data.manifest import build_config, write_json
from detection.data.models import (
    ANOMALY_CODES,
    ANOMALY_SCOPES,
    SPLIT_NAMES,
    AnomalyRecord,
    DuplicateGroup,
    SourceFingerprint,
    Split,
    SplitAssignment,
)


def test_build_config_defaults_match_contract() -> None:
    config = build_config()

    assert config == {
        "seed": 42,
        "ratios": {"train": 0.75, "validation": 0.15, "test": 0.10},
        "on_anomaly": "fail",
        "stratification": "multilabel_iterative",
        "duplicate_policy": "content_group_atomic",
        "class_mapping": [
            {"id": class_id, "name": name}
            for class_id, name in CLASS_NAMES.items()
        ],
    }


def test_build_config_accepts_custom_values_and_ratio_mapping() -> None:
    config = build_config(
        seed=7,
        ratios={"train": 0.6, "validation": 0.2, "test": 0.2},
        on_anomaly="quarantine",
    )

    assert config["seed"] == 7
    assert config["ratios"] == {"train": 0.6, "validation": 0.2, "test": 0.2}
    assert config["on_anomaly"] == "quarantine"
    assert [entry["id"] for entry in config["class_mapping"]] == [0, 1, 2, 3, 4, 5]


def test_write_json_is_utf8_indented_and_ends_with_newline(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "report.json"
    payload = {"message": "Tiếng Việt", "nested": {"b": 1, "a": 2}}

    result = write_json(target, payload)

    assert result == target
    raw = target.read_bytes()
    text = raw.decode("utf-8")
    assert text.endswith("\n")
    assert "\n  \"message\"" in text
    assert "Tiếng Việt" in text
    assert "\\u" not in text
    assert json.loads(text) == payload


def test_write_json_replaces_existing_file_atomically(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    write_json(target, {"version": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 1}

    write_json(target, {"version": 2})

    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 2}
    assert [path.name for path in target.parent.iterdir()] == ["report.json"]


def test_failed_replace_leaves_original_file_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "report.json"
    write_json(target, {"version": 1})
    before = target.read_bytes()

    def fail_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(manifest_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_json(target, {"version": 2})

    assert target.read_bytes() == before
    assert [path.name for path in target.parent.iterdir()] == ["report.json"]


def test_serialization_failure_leaves_original_file_untouched(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    write_json(target, {"version": 1})
    before = target.read_bytes()

    with pytest.raises(TypeError):
        write_json(target, {"version": 2, "bad": object()})

    assert target.read_bytes() == before
    assert [path.name for path in target.parent.iterdir()] == ["report.json"]


# --- T018: validation_report.json schema and writer ------------------------


def _fingerprint(
    status: str = "verified_unchanged",
    *,
    error: str | None = None,
) -> dict[str, Any]:
    before = "sha256:" + "a" * 64
    after = "sha256:" + "b" * 64
    return {
        "algorithm": "sha256",
        "tree_sha256": before,
        "after_tree_sha256": None if status == "unavailable" else (
            after if status == "changed" else before
        ),
        "status": status,
        "verified_after_run": status == "verified_unchanged",
        "changed": ["train/images/a.jpg"] if status == "changed" else [],
        "error": error or (
            "I/O error while re-reading source" if status == "unavailable" else None
        ),
    }


def _record(
    code: str,
    severity: str,
    *,
    paths: list[str] | None = None,
    sample_id: str | None = "train/a",
    object_index: int | None = None,
    reason: str | None = None,
) -> AnomalyRecord:
    details: dict[str, Any] = {}
    if object_index is not None:
        details["object_index"] = object_index
    return AnomalyRecord(
        code=code,
        severity=severity,
        scope=ANOMALY_SCOPES[code],
        sample_id=sample_id,
        source_subset="train" if sample_id else None,
        paths=paths or [],
        reason=reason or f"reason for {code}",
        details=details,
    )


def _report_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "source_root": "/mnt/datasets/NEU-DET",
        "source_subsets": ["train", "validation"],
        "fingerprint": _fingerprint(),
        "seed": 42,
        "ratios": (0.75, 0.15, 0.10),
        "on_anomaly": "fail",
        "source_images": 3,
        "source_annotations": 3,
        "matched_samples": 3,
        "unpaired_images": 0,
        "unpaired_annotations": 0,
        "eligible_samples": 3,
        "quarantined_samples": 0,
        "written_samples": 3,
        "objects_total": 4,
        "objects_by_class": {0: 3, 2: 1},
        "gate_status": "pass",
        "anomalies": [],
        "generated_at": "2026-11-19T00:00:00Z",
    }
    kwargs.update(overrides)
    return kwargs


def test_build_validation_report_has_all_required_schema_fields() -> None:
    report = manifest_module.build_validation_report(**_report_kwargs())

    assert set(report) == {
        "schema_version",
        "feature",
        "generated_at",
        "source",
        "config",
        "summary",
        "gate",
        "anomalies",
    }
    assert report["schema_version"] == "1.0"
    assert report["feature"] == "001-neu-det-data-preparation"
    assert report["generated_at"] == "2026-11-19T00:00:00Z"
    assert set(report["source"]) == {"root", "subsets", "fingerprint"}
    assert set(report["source"]["fingerprint"]) == {
        "algorithm",
        "tree_sha256",
        "status",
        "after_tree_sha256",
        "verified_after_run",
        "changed",
        "error",
    }
    assert set(report["config"]) == {
        "seed",
        "ratios",
        "on_anomaly",
        "stratification",
        "duplicate_policy",
        "class_mapping",
    }
    assert set(report["summary"]) >= {
        "source_images",
        "source_annotations",
        "matched_samples",
        "unpaired_images",
        "unpaired_annotations",
        "eligible_samples",
        "quarantined_samples",
        "unwritten_samples",
        "written_samples",
        "accounted_images",
        "accounting_ok",
        "objects_total",
        "objects_by_class",
        "anomaly_counts",
    }
    assert set(report["gate"]) == {"status", "blocking_errors", "warnings"}
    assert isinstance(report["anomalies"], list)


def test_build_validation_report_config_reflects_cli_values() -> None:
    ratios = {"train": 0.6, "validation": 0.3, "test": 0.1}

    report = manifest_module.build_validation_report(
        **_report_kwargs(seed=17, ratios=ratios, on_anomaly="quarantine")
    )

    assert report["config"] == build_config(
        seed=17, ratios=ratios, on_anomaly="quarantine"
    )
    assert report["config"]["seed"] == 17
    assert report["config"]["ratios"] == ratios
    assert report["config"]["on_anomaly"] == "quarantine"


def test_build_validation_report_anomaly_counts_include_every_known_code() -> None:
    report = manifest_module.build_validation_report(
        **_report_kwargs(
            gate_status="pass_with_quarantine",
            anomalies=[
                _record("missing_xml", "error", sample_id=None),
                _record("empty_annotation", "info"),
            ],
        )
    )

    counts = report["summary"]["anomaly_counts"]
    assert set(counts) == set(ANOMALY_CODES)
    assert counts["missing_xml"] == 1
    assert counts["empty_annotation"] == 1
    assert counts["invalid_bbox"] == 0
    assert counts["source_tree_changed"] == 0


def test_build_validation_report_accounting_first_write_and_final_update() -> None:
    first_kwargs = _report_kwargs(
        source_images=6,
        source_annotations=6,
        matched_samples=5,
        unpaired_images=1,
        unpaired_annotations=1,
        eligible_samples=5,
        written_samples=0,
    )

    first = manifest_module.build_validation_report(**first_kwargs)
    assert first["summary"]["unwritten_samples"] == 5
    assert first["summary"]["written_samples"] == 0
    assert first["summary"]["accounted_images"] == 6
    assert first["summary"]["accounting_ok"] is True

    final_kwargs = dict(first_kwargs)
    final_kwargs["written_samples"] = 5
    final = manifest_module.build_validation_report(**final_kwargs)
    assert final["summary"]["unwritten_samples"] == 0
    assert final["summary"]["written_samples"] == 5
    assert final["summary"]["quarantined_samples"] == 0
    assert final["summary"]["accounted_images"] == 6
    assert final["summary"]["accounting_ok"] is True

    explicit = manifest_module.build_validation_report(
        **{**first_kwargs, "unwritten_samples": 5}
    )
    assert explicit["summary"]["unwritten_samples"] == 5


def test_build_validation_report_accounting_ok_follows_the_equation() -> None:
    inconsistent = manifest_module.build_validation_report(
        **_report_kwargs(source_images=7, matched_samples=5, unpaired_images=1)
    )

    summary = inconsistent["summary"]
    assert summary["accounted_images"] == (
        summary["written_samples"]
        + summary["quarantined_samples"]
        + summary["unwritten_samples"]
        + summary["unpaired_images"]
    )
    assert summary["accounted_images"] == 6
    assert summary["accounting_ok"] is False


def test_build_validation_report_gate_counts_error_and_warning_records_only() -> None:
    report = manifest_module.build_validation_report(
        **_report_kwargs(
            gate_status="pass_with_quarantine",
            anomalies=[
                _record("unknown_class", "error"),
                _record("size_mismatch", "warning"),
                _record("empty_annotation", "info"),
            ],
        )
    )

    assert report["gate"] == {
        "status": "pass_with_quarantine",
        "blocking_errors": 1,
        "warnings": 1,
    }


@pytest.mark.parametrize(
    "status, anomalies",
    [
        ("pass", []),
        ("pass_with_quarantine", [_record("missing_xml", "error", sample_id=None)]),
        ("fail", [_record("invalid_bbox", "error", object_index=0)]),
    ],
)
def test_build_validation_report_gate_status_is_constrained(
    status: str, anomalies: list[AnomalyRecord]
) -> None:
    report = manifest_module.build_validation_report(
        **_report_kwargs(gate_status=status, anomalies=anomalies)
    )

    assert report["gate"]["status"] in {"pass", "pass_with_quarantine", "fail"}
    assert report["gate"]["status"] == status

    with pytest.raises(ValueError):
        manifest_module.build_validation_report(
            **_report_kwargs(gate_status="maybe")
        )


@pytest.mark.parametrize(
    "status, verified_after_run, expected_changed, has_error",
    [
        ("verified_unchanged", True, [], False),
        ("changed", False, ["train/images/a.jpg"], False),
        ("unavailable", False, [], True),
    ],
)
def test_build_validation_report_fingerprint_has_three_statuses(
    status: str,
    verified_after_run: bool,
    expected_changed: list[str],
    has_error: bool,
) -> None:
    fingerprint = _fingerprint(
        status,
        error="disk read failed" if status == "unavailable" else None,
    )
    fingerprint["verified_after_run"] = verified_after_run

    report = manifest_module.build_validation_report(
        **_report_kwargs(fingerprint=fingerprint)
    )
    payload = report["source"]["fingerprint"]

    assert payload["status"] == status
    assert payload["verified_after_run"] is verified_after_run
    assert payload["changed"] == expected_changed
    assert (payload["error"] is not None) is has_error
    assert payload["algorithm"] == "sha256"

    with pytest.raises(ValueError):
        manifest_module.build_validation_report(
            **_report_kwargs(fingerprint=_fingerprint("unknown"))
        )


def test_build_validation_report_never_reports_unperformed_check_as_changed() -> None:
    unfinished = SourceFingerprint(tree_sha256="sha256:" + "a" * 64)

    report = manifest_module.build_validation_report(
        **_report_kwargs(fingerprint=unfinished)
    )
    payload = report["source"]["fingerprint"]

    assert payload["status"] == "unavailable"
    assert payload["verified_after_run"] is False
    assert payload["changed"] == []
    assert payload["error"]


def test_build_validation_report_sorts_anomalies_deterministically() -> None:
    anomalies: list[Any] = [
        _record("size_mismatch", "warning", sample_id="train/z"),
        _record(
            "invalid_bbox", "error", sample_id="train/a", object_index=1
        ),
        _record(
            "invalid_bbox", "error", sample_id="train/a", object_index=0
        ),
        _record("missing_xml", "error", sample_id=None, paths=["train/images/m.jpg"]),
        {
            "code": "unsupported_file",
            "severity": "info",
            "scope": "dataset",
            "sample_id": None,
            "source_subset": "train",
            "paths": ["train/images/notes.txt"],
            "reason": "ignored file",
            "details": {},
        },
        _record("empty_annotation", "info", sample_id="train/b"),
    ]
    original_codes = [item.code if hasattr(item, "code") else item["code"] for item in anomalies]

    report = manifest_module.build_validation_report(
        **_report_kwargs(gate_status="pass_with_quarantine", anomalies=anomalies)
    )
    serialized = report["anomalies"]

    assert [item["code"] for item in serialized] == [
        "empty_annotation",
        "invalid_bbox",
        "invalid_bbox",
        "missing_xml",
        "size_mismatch",
        "unsupported_file",
    ]
    assert [item["details"]["object_index"] for item in serialized[1:3]] == [0, 1]
    assert original_codes == [
        item.code if hasattr(item, "code") else item["code"] for item in anomalies
    ]


def test_write_validation_report_is_atomic_for_first_write_and_final_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "validation_report.json"
    first_kwargs = _report_kwargs(written_samples=0, unwritten_samples=None)

    first = manifest_module.write_validation_report(target, **first_kwargs)
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == first
    assert first["summary"]["unwritten_samples"] == 3

    final_kwargs = dict(first_kwargs)
    final_kwargs["written_samples"] = 3
    final = manifest_module.write_validation_report(target, **final_kwargs)

    assert json.loads(target.read_text(encoding="utf-8")) == final
    assert final["summary"]["written_samples"] == 3
    assert final["summary"]["unwritten_samples"] == 0
    assert list(tmp_path.iterdir()) == [target]

    original = target.read_bytes()

    def fail_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(manifest_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        manifest_module.write_validation_report(target, **final_kwargs)

    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]

    missing_target = tmp_path / "nested" / "validation_report.json"
    with pytest.raises(OSError, match="simulated replace failure"):
        manifest_module.write_validation_report(missing_target, **first_kwargs)
    assert not missing_target.exists()
    assert list((tmp_path / "nested").iterdir()) == []


def test_write_validation_report_defaults_generated_at_to_utc_iso8601(tmp_path: Path) -> None:
    report = manifest_module.write_validation_report(
        tmp_path / "validation_report.json", **_report_kwargs(generated_at=None)
    )

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", report["generated_at"])
    datetime.strptime(report["generated_at"], "%Y-%m-%dT%H:%M:%SZ")


# --- T026: split_manifest.json schema and writer ---------------------------


def _split_manifest_entry_points() -> tuple[Any, Any]:
    builder = getattr(manifest_module, "build_split_manifest", None)
    writer = getattr(manifest_module, "write_split_manifest", None)
    if not callable(builder) or not callable(writer):
        pytest.fail(
            "US3 split manifest helpers are not implemented yet: "
            "build_split_manifest / write_split_manifest"
        )
    return builder, writer


def _assignment(index: int, split: str, *, digest: str | None = None) -> SplitAssignment:
    stem = f"s{index:03d}"
    return SplitAssignment(
        sample_id=f"train/{stem}",
        split=split,
        source_subset="train",
        source_image=f"train/images/{stem}.jpg",
        source_xml=f"train/annotations/{stem}.xml",
        output_image=f"images/{split}/{stem}.jpg",
        output_label=f"labels/{split}/{stem}.txt",
        sha256=digest or f"sha256:{index:064x}",
        present_classes=[0],
        object_count=1,
    )


def _split_manifest_kwargs(**overrides: Any) -> dict[str, Any]:
    counts = {"train": 15, "validation": 3, "test": 2}
    ratios = {"train": 0.75, "validation": 0.15, "test": 0.10}
    digest = "sha256:" + "ab" * 32
    splits: dict[str, Split] = {}
    start = 0
    for name in SPLIT_NAMES:
        assignments = [
            _assignment(index, name, digest=digest if index < 2 and name == "train" else None)
            for index in range(start, start + counts[name])
        ]
        start += counts[name]
        splits[name] = Split(
            name=name,
            target_ratio=ratios[name],
            images=counts[name],
            objects=counts[name],
            image_counts_by_class={0: counts[name]},
            object_counts_by_class={0: counts[name]},
            source_subset_counts={"train": counts[name]},
            assignments=assignments,
        )
    group = DuplicateGroup(
        sha256=digest,
        members=[assignment.sample_id for assignment in splits["train"].assignments[:2]],
        labels_consistent=True,
        assigned_split="train",
    )
    result = SimpleNamespace(
        splits=splits,
        anomalies=[],
        duplicate_groups=[group],
        invariants={
            "pairwise_disjoint_sample_id": True,
            "pairwise_disjoint_output_path": True,
            "pairwise_disjoint_sha256": True,
            "all_eligible_assigned": True,
            "duplicate_groups_atomic": True,
            "no_cross_subset_pairing": True,
            "source_unchanged": True,
            "class_mapping_fixed": True,
        },
    )
    kwargs: dict[str, Any] = {
        "dataset_name": "NEU-DET",
        "source_root": "/mnt/datasets/NEU-DET",
        "source_subsets": ["train", "validation"],
        "fingerprint": _fingerprint(),
        "seed": 42,
        "ratios": ratios,
        "on_anomaly": "fail",
        "split_result": result,
        "generated_at": "2026-11-19T00:00:00Z",
    }
    kwargs.update(overrides)
    return kwargs


def test_build_split_manifest_has_all_required_schema_fields_and_classes() -> None:
    builder, _ = _split_manifest_entry_points()

    manifest = builder(**_split_manifest_kwargs())

    assert set(manifest) == {
        "schema_version",
        "generated_at",
        "dataset",
        "config",
        "classes",
        "totals",
        "splits",
        "duplicate_groups",
        "invariants",
    }
    assert manifest["schema_version"] == "1.0"
    assert manifest["generated_at"] == "2026-11-19T00:00:00Z"
    assert set(manifest["dataset"]) == {
        "name",
        "source_root",
        "source_fingerprint",
        "source_subsets",
    }
    assert manifest["dataset"]["source_subsets"] == ["train", "validation"]
    assert manifest["config"] == build_config(
        seed=42,
        ratios={"train": 0.75, "validation": 0.15, "test": 0.10},
        on_anomaly="fail",
    )
    assert manifest["classes"] == [
        {"id": class_id, "name": CLASS_NAMES[class_id]} for class_id in range(6)
    ]
    assert set(manifest["splits"]) == set(SPLIT_NAMES)
    assert isinstance(manifest["duplicate_groups"], list)


def test_build_split_manifest_totals_and_per_split_counts() -> None:
    builder, _ = _split_manifest_entry_points()
    kwargs = _split_manifest_kwargs()

    manifest = builder(**kwargs)
    result = kwargs["split_result"]

    assert manifest["totals"]["images"] == 20
    assert manifest["totals"]["objects"] == 20
    assert manifest["totals"]["image_counts_by_class"] == {"0": 20}
    assert manifest["totals"]["object_counts_by_class"] == {"0": 20}
    assert sum(manifest["splits"][name]["images"] for name in SPLIT_NAMES) == 20
    for name in SPLIT_NAMES:
        expected = result.splits[name].images
        split = manifest["splits"][name]
        assert split["images"] == expected
        assert split["objects"] == expected
        assert split["source_subset_counts"] == {"train": expected}
        assert len(split["assignments"]) == expected


def test_build_split_manifest_actual_ratio_is_images_over_totals() -> None:
    builder, _ = _split_manifest_entry_points()

    manifest = builder(**_split_manifest_kwargs())

    for name in SPLIT_NAMES:
        split = manifest["splits"][name]
        assert split["target_ratio"] == pytest.approx(
            manifest["config"]["ratios"][name]
        )
        assert split["actual_ratio"] == pytest.approx(split["images"] / 20)
    assert sum(
        manifest["splits"][name]["actual_ratio"] for name in SPLIT_NAMES
    ) == pytest.approx(1.0)


def test_build_split_manifest_assignments_are_sorted_by_sample_id() -> None:
    builder, _ = _split_manifest_entry_points()
    kwargs = _split_manifest_kwargs()
    assignments = kwargs["split_result"].splits["train"].assignments
    assignments.reverse()

    manifest = builder(**kwargs)

    for name in SPLIT_NAMES:
        ids = [
            assignment["sample_id"]
            for assignment in manifest["splits"][name]["assignments"]
        ]
        assert ids == sorted(ids)


def test_build_split_manifest_records_duplicate_groups() -> None:
    builder, _ = _split_manifest_entry_points()

    manifest = builder(**_split_manifest_kwargs())

    assert len(manifest["duplicate_groups"]) == 1
    group = manifest["duplicate_groups"][0]
    assert group["group_id"] == "sha256:" + "ab" * 32
    assert group["sha256"] == "sha256:" + "ab" * 32
    assert group["assigned_split"] == "train"
    assert group["members"] == ["train/s000", "train/s001"]


def test_build_split_manifest_has_all_eight_invariants() -> None:
    builder, _ = _split_manifest_entry_points()

    manifest = builder(**_split_manifest_kwargs())

    assert set(manifest["invariants"]) == {
        "pairwise_disjoint_sample_id",
        "pairwise_disjoint_output_path",
        "pairwise_disjoint_sha256",
        "all_eligible_assigned",
        "duplicate_groups_atomic",
        "no_cross_subset_pairing",
        "source_unchanged",
        "class_mapping_fixed",
    }
    assert all(manifest["invariants"].values())


def test_write_split_manifest_is_atomic_and_refuses_invariant_failure(
    tmp_path: Path,
) -> None:
    _, writer = _split_manifest_entry_points()
    target = tmp_path / "split_manifest.json"
    kwargs = _split_manifest_kwargs()

    written = writer(target, **kwargs)
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == written

    original = target.read_bytes()
    broken = _split_manifest_kwargs()
    broken["split_result"].invariants["pairwise_disjoint_sha256"] = False
    with pytest.raises(ValueError, match="invariant"):
        writer(target, **broken)
    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]

    missing_target = tmp_path / "nested" / "split_manifest.json"
    with pytest.raises(ValueError, match="invariant"):
        writer(missing_target, **broken)
    assert not missing_target.exists()
