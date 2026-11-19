"""Shared artifact writing and configuration serialization.

All JSON artifacts are written atomically: a temporary file is created in the
same directory, flushed, and then moved into place with :func:`os.replace`.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .classes import class_mapping
from .models import ANOMALY_CODES, SPLIT_NAMES, AnomalyRecord, SourceFingerprint

ON_ANOMALY_MODES = ("fail", "quarantine")
FEATURE_NAME = "001-neu-det-data-preparation"
REPORT_SCHEMA_VERSION = "1.0"
GATE_STATUSES = ("pass", "pass_with_quarantine", "fail")
FINGERPRINT_STATUSES = ("verified_unchanged", "changed", "unavailable")
SEVERITY_NAMES = ("error", "warning", "info")


def _ratios_mapping(
    ratios: Mapping[str, float] | Sequence[float],
) -> dict[str, float]:
    if isinstance(ratios, Mapping):
        missing = [name for name in SPLIT_NAMES if name not in ratios]
        if missing:
            raise ValueError(
                f"ratios mapping is missing keys: {', '.join(missing)}"
            )
        return {name: float(ratios[name]) for name in SPLIT_NAMES}

    values = tuple(float(value) for value in ratios)
    if len(values) != 3:
        raise ValueError("ratios must contain exactly three values")
    return dict(zip(SPLIT_NAMES, values, strict=True))


def build_config(
    seed: int = 42,
    ratios: Mapping[str, float] | Sequence[float] = (0.75, 0.15, 0.10),
    on_anomaly: str = "fail",
) -> dict[str, Any]:
    """Build the shared ``config`` object used by report and manifest."""
    if on_anomaly not in ON_ANOMALY_MODES:
        raise ValueError(
            f"on_anomaly must be one of {ON_ANOMALY_MODES}, got {on_anomaly!r}"
        )
    return {
        "seed": int(seed),
        "ratios": _ratios_mapping(ratios),
        "on_anomaly": on_anomaly,
        "stratification": "multilabel_iterative",
        "duplicate_policy": "content_group_atomic",
        "class_mapping": class_mapping(),
    }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Write ``payload`` as UTF-8 JSON atomically and return the final path."""
    target = Path(path)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return target


# --- validation_report.json (T022) -----------------------------------------


def _count(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer count")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _anomaly_mapping(anomaly: AnomalyRecord | Mapping[str, Any]) -> dict[str, Any]:
    """Serialize one anomaly record using the contract field names."""
    if isinstance(anomaly, Mapping):
        source: dict[str, Any] = dict(anomaly)
    else:
        source = {
            "code": anomaly.code,
            "severity": anomaly.severity,
            "scope": anomaly.scope,
            "sample_id": anomaly.sample_id,
            "source_subset": anomaly.source_subset,
            "paths": list(anomaly.paths),
            "reason": anomaly.reason,
            "details": dict(anomaly.details),
        }

    code = str(source.get("code", ""))
    if code not in ANOMALY_CODES:
        raise ValueError(f"unknown anomaly code in report: {code!r}")
    severity = getattr(source.get("severity"), "value", source.get("severity"))
    severity = str(severity)
    if severity not in SEVERITY_NAMES:
        raise ValueError(f"unknown anomaly severity in report: {severity!r}")
    scope = getattr(source.get("scope"), "value", source.get("scope"))
    reason = str(source.get("reason", ""))
    if not reason:
        raise ValueError(f"anomaly {code!r} must have a reason")
    sample_id = source.get("sample_id")
    details = dict(source.get("details") or {})

    return {
        "code": code,
        "severity": severity,
        "scope": str(scope),
        "sample_id": None if sample_id is None else str(sample_id),
        "source_subset": source.get("source_subset"),
        "paths": [str(path) for path in (source.get("paths") or [])],
        "reason": reason,
        "details": details,
    }


def _anomaly_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    """Stable ordering from data-model.md §6: code, paths, sample, index, reason."""
    sample_id = item["sample_id"]
    object_index = item["details"].get("object_index")
    try:
        index_key: tuple[int, int] = (0, int(object_index))
    except (TypeError, ValueError):
        index_key = (1, 0)
    return (
        item["code"],
        tuple(item["paths"]),
        (1, "") if sample_id is None else (0, str(sample_id)),
        index_key,
        item["reason"],
    )


def _fingerprint_mapping(
    fingerprint: Mapping[str, Any] | SourceFingerprint | None,
) -> dict[str, Any]:
    """Normalize a fingerprint to the three documented verification statuses."""
    if fingerprint is None:
        data: dict[str, Any] = {}
    elif isinstance(fingerprint, Mapping):
        data = dict(fingerprint)
    else:
        data = {
            "algorithm": getattr(fingerprint, "algorithm", "sha256"),
            "tree_sha256": getattr(fingerprint, "tree_sha256", ""),
            "after_tree_sha256": getattr(fingerprint, "after_tree_sha256", None),
            "verified_after_run": bool(
                getattr(fingerprint, "verified_after_run", False)
            ),
            "changed": list(getattr(fingerprint, "changed", []) or []),
            "error": getattr(fingerprint, "error", None),
        }

    status = data.get("status")
    changed = [str(path) for path in (data.get("changed") or [])]
    error = data.get("error")
    verified = bool(data.get("verified_after_run", False))
    tree_sha256 = str(data.get("tree_sha256") or "")
    after = data.get("after_tree_sha256")

    if status is None:
        # An unfinished check must never become "changed" or "verified_unchanged".
        if error:
            status = "unavailable"
        elif changed:
            status = "changed"
        elif verified:
            status = "verified_unchanged"
        else:
            status = "unavailable"
            error = error or "fingerprint verification was not performed"
    if status not in FINGERPRINT_STATUSES:
        raise ValueError(f"unknown fingerprint status: {status!r}")

    if status == "unavailable":
        verified = False
        changed = []
        after = None
        error = error or "source fingerprint verification was unavailable"
    elif status == "changed":
        verified = False
        error = None
        if after is None:
            after = tree_sha256
    else:
        verified = True
        changed = []
        error = None
        if after is None:
            after = tree_sha256

    return {
        "algorithm": str(data.get("algorithm") or "sha256"),
        "tree_sha256": tree_sha256,
        "status": status,
        "after_tree_sha256": after,
        "verified_after_run": verified,
        "changed": changed,
        "error": error,
    }


def build_validation_report(
    *,
    source_root: str | Path,
    fingerprint: Mapping[str, Any] | SourceFingerprint | None = None,
    source_subsets: Sequence[str] = (),
    seed: int = 42,
    ratios: Mapping[str, float] | Sequence[float] = (0.75, 0.15, 0.10),
    on_anomaly: str = "fail",
    source_images: int = 0,
    source_annotations: int = 0,
    matched_samples: int = 0,
    unpaired_images: int = 0,
    unpaired_annotations: int = 0,
    eligible_samples: int = 0,
    quarantined_samples: int = 0,
    written_samples: int = 0,
    unwritten_samples: int | None = None,
    objects_total: int = 0,
    objects_by_class: Mapping[int | str, int] | None = None,
    anomalies: Sequence[AnomalyRecord | Mapping[str, Any]] = (),
    gate_status: str = "pass",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the ``validation_report.json`` payload without touching the disk.

    ``unwritten_samples`` is derived from the paired samples that were neither
    written nor quarantined, so the accounting equation balances at the first
    write (nothing written yet) as well as at the final update. Callers may
    override it for snapshots taken between those two points.
    """
    if gate_status not in GATE_STATUSES:
        raise ValueError(f"gate status must be one of {GATE_STATUSES}")

    written = _count("written_samples", written_samples)
    quarantined = _count("quarantined_samples", quarantined_samples)
    matched = _count("matched_samples", matched_samples)
    unpaired = _count("unpaired_images", unpaired_images)
    if unwritten_samples is None:
        unwritten = max(0, matched - written - quarantined)
    else:
        unwritten = _count("unwritten_samples", unwritten_samples)
    accounted = written + quarantined + unwritten + unpaired

    serialized = sorted(
        (_anomaly_mapping(anomaly) for anomaly in anomalies),
        key=_anomaly_sort_key,
    )
    anomaly_counts = {code: 0 for code in ANOMALY_CODES}
    blocking_errors = 0
    warnings = 0
    for item in serialized:
        anomaly_counts[item["code"]] += 1
        if item["severity"] == "error":
            blocking_errors += 1
        elif item["severity"] == "warning":
            warnings += 1
    if gate_status == "pass" and blocking_errors:
        raise ValueError("gate status 'pass' requires zero blocking errors")

    by_class = {str(class_id): 0 for class_id in range(6)}
    for class_id, count in (objects_by_class or {}).items():
        key = str(int(class_id))
        if key not in by_class:
            raise ValueError(f"unknown class id in objects_by_class: {class_id!r}")
        by_class[key] = _count(f"objects_by_class[{key}]", count)

    if generated_at is None:
        generated_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "feature": FEATURE_NAME,
        "generated_at": generated_at,
        "source": {
            "root": str(source_root),
            "subsets": sorted(str(name) for name in source_subsets),
            "fingerprint": _fingerprint_mapping(fingerprint),
        },
        "config": build_config(seed=seed, ratios=ratios, on_anomaly=on_anomaly),
        "summary": {
            "source_images": _count("source_images", source_images),
            "source_annotations": _count("source_annotations", source_annotations),
            "matched_samples": matched,
            "unpaired_images": unpaired,
            "unpaired_annotations": _count(
                "unpaired_annotations", unpaired_annotations
            ),
            "eligible_samples": _count("eligible_samples", eligible_samples),
            "quarantined_samples": quarantined,
            "unwritten_samples": unwritten,
            "written_samples": written,
            "accounted_images": accounted,
            "accounting_ok": accounted == _count("source_images", source_images),
            "objects_total": _count("objects_total", objects_total),
            "objects_by_class": by_class,
            "anomaly_counts": anomaly_counts,
        },
        "gate": {
            "status": gate_status,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
        },
        "anomalies": serialized,
    }


def write_validation_report(path: str | Path, **payload: Any) -> dict[str, Any]:
    """Write a validation report atomically and return the written payload.

    Calling this again with updated counts performs the final (or failure)
    update of the same report. Report-write failures propagate as ``OSError``
    so the caller can map them to the CLI's I/O exit code.
    """
    report = build_validation_report(**payload)
    write_json(path, report)
    return report
