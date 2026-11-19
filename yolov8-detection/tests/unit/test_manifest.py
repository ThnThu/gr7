"""Unit tests for the shared atomic JSON writer, config and report (T009/T018)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

import detection.data.manifest as manifest_module
from detection.data.classes import CLASS_NAMES
from detection.data.manifest import build_config, write_json
from detection.data.models import (
    ANOMALY_CODES,
    ANOMALY_SCOPES,
    AnomalyRecord,
    SourceFingerprint,
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
