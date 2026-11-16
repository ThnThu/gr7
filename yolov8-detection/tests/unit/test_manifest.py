"""Unit tests for the shared atomic JSON writer and config serialization (T009)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import detection.data.manifest as manifest_module
from detection.data.classes import CLASS_NAMES
from detection.data.manifest import build_config, write_json


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
