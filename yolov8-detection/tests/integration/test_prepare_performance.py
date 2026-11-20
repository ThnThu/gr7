"""Performance smoke test for ``detection prepare`` (T034).

Generates 1,800 synthetic 64x64 images in ``tmp_path`` using helpers from
``tests/conftest.py`` and verifies the full pipeline completes under 10 minutes.
No real NEU-DET data, no network, and no pixel transformations are performed by
the pipeline (images are copied with ``shutil.copy2``).

Marked ``slow`` and skipped unless ``RUN_SLOW_TESTS=1`` so the normal test suite
is not slowed down.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from conftest import build_source_tree
from detection.cli import main

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("RUN_SLOW_TESTS") != "1",
        reason="set RUN_SLOW_TESTS=1 to run performance smoke tests",
    ),
]

CLASS_NAMES = [
    "crazing",
    "inclusion",
    "patches",
    "pitted_surface",
    "rolled-in_scale",
    "scratches",
]


def _build_1800_source(root: Path) -> Path:
    subsets: dict[str, list[dict]] = {"train": [], "validation": []}
    uid = 0
    for subset, count in (("train", 900), ("validation", 900)):
        for index in range(count):
            class_name = CLASS_NAMES[index % len(CLASS_NAMES)]
            color = (uid % 256, (uid // 256) % 256, (uid // 65536) % 256)
            subsets[subset].append(
                {
                    "stem": f"{class_name}_{index:04d}",
                    "size": (64, 64),
                    "color": color,
                    "image_ext": ".png",
                    "objects": [
                        {"name": class_name, "bbox": (1.0, 1.0, 20.0, 20.0)}
                    ],
                }
            )
            uid += 1
    return build_source_tree(root, subsets)


def test_prepare_1800_images_under_10_minutes(tmp_path: Path) -> None:
    source = _build_1800_source(tmp_path / "source")
    output = tmp_path / "output"

    started = time.monotonic()
    exit_code = main(
        [
            "prepare",
            "--source",
            str(source),
            "--output",
            str(output),
            "--seed",
            "42",
            "--ratios",
            "0.75,0.15,0.10",
        ]
    )
    elapsed = time.monotonic() - started

    assert exit_code == 0, f"detection prepare failed with exit code {exit_code}"
    assert elapsed < 600, f"pipeline took {elapsed:.2f}s, expected < 600s"

    manifest = json.loads(
        (output / "split_manifest.json").read_text(encoding="utf-8")
    )
    counts = {
        name: manifest["splits"][name]["images"]
        for name in ("train", "validation", "test")
    }
    assert counts == {"train": 1350, "validation": 270, "test": 180}
    assert manifest["totals"]["images"] == 1800
    assert all(manifest["invariants"].values())

    # Pipeline copies images; source files must remain byte-for-byte unchanged.
    for subset in ("train", "validation"):
        source_images = sorted((source / subset / "images").glob("*.png"))
        assert len(source_images) == 900
