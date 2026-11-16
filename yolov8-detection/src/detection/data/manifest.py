"""Shared artifact writing and configuration serialization.

All JSON artifacts are written atomically: a temporary file is created in the
same directory, flushed, and then moved into place with :func:`os.replace`.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .classes import class_mapping
from .models import SPLIT_NAMES

ON_ANOMALY_MODES = ("fail", "quarantine")


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
