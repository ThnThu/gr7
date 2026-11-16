"""Unit tests for source discovery, fingerprinting and same-subset pairing (T006/T007)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from detection.data.discovery import (
    DiscoveryError,
    compare_fingerprints,
    discover_source,
    fingerprint_source,
    pair_samples,
)


def _tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_discover_multiple_subsets_lists_sorted_assets(build_source_tree, tmp_path: Path) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [{"stem": "b"}, {"stem": "a"}],
            "validation": [{"stem": "c"}],
        },
    )

    result = discover_source(root)

    assert [subset.name for subset in result.subsets] == ["train", "validation"]
    assert [subset.relative_prefix for subset in result.subsets] == ["train", "validation"]
    assert [image.asset_id for image in result.images] == [
        "train/images/a.jpg",
        "train/images/b.jpg",
        "validation/images/c.jpg",
    ]
    assert [annotation.asset_id for annotation in result.annotations] == [
        "train/annotations/a.xml",
        "train/annotations/b.xml",
        "validation/annotations/c.xml",
    ]
    assert result.anomalies == []
    assert result.dataset.read_only is True
    assert result.dataset.fingerprint.algorithm == "sha256"
    assert result.dataset.fingerprint.tree_sha256.startswith("sha256:")
    assert result.dataset.fingerprint.verified_after_run is False


def test_discover_single_root_subset(build_source_tree, tmp_path: Path) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {None: [{"stem": "a"}]},
    )

    result = discover_source(root)

    assert [subset.name for subset in result.subsets] == ["root"]
    assert [subset.relative_prefix for subset in result.subsets] == ["root"]
    assert [image.asset_id for image in result.images] == ["root/images/a.jpg"]
    pairing = pair_samples(result)
    assert [sample.sample_id for sample in pairing.samples] == ["root/a"]


@pytest.mark.parametrize("filename", ["notes.txt", "preview.webp", "data.json"])
def test_unsupported_files_are_ignored_with_info(
    build_source_tree,
    tmp_path: Path,
    filename: str,
) -> None:
    root = build_source_tree(tmp_path / "source", {"train": [{"stem": "a"}]})
    (root / "train" / "images" / filename).write_text("not an image", encoding="utf-8")

    result = discover_source(root)

    assert len(result.anomalies) == 1
    anomaly = result.anomalies[0]
    assert anomaly.code == "unsupported_file"
    assert anomaly.severity.value == "info"
    assert anomaly.scope.value == "dataset"
    assert anomaly.paths == [f"train/images/{filename}"]


def test_unsupported_file_outside_known_directories_is_reported(
    build_source_tree, tmp_path: Path
) -> None:
    root = build_source_tree(tmp_path / "source", {"train": [{"stem": "a"}]})
    (root / "train" / "README.txt").write_text("metadata", encoding="utf-8")

    result = discover_source(root)

    assert [anomaly.paths for anomaly in result.anomalies] == [
        ["train/README.txt"]
    ]
    assert result.anomalies[0].code == "unsupported_file"
    assert result.anomalies[0].severity.value == "info"


def test_unsupported_file_at_source_root_is_reported(build_source_tree, tmp_path: Path) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {"train": [{"stem": "a"}], "validation": [{"stem": "b"}]},
    )
    (root / "README.md").write_text("dataset notes", encoding="utf-8")

    result = discover_source(root)

    assert [anomaly.paths for anomaly in result.anomalies] == [["README.md"]]
    assert result.anomalies[0].code == "unsupported_file"


def test_missing_source_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError, match="does not exist"):
        discover_source(tmp_path / "missing")


def test_subset_with_only_images_is_a_structural_error(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "train" / "images").mkdir(parents=True)
    (source / "train" / "images" / "a.jpg").write_bytes(b"placeholder")

    with pytest.raises(DiscoveryError, match="images.*annotations"):
        discover_source(source)


def test_root_layout_with_only_images_is_a_structural_error(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "images").mkdir(parents=True)

    with pytest.raises(DiscoveryError, match="images.*annotations"):
        discover_source(source)


def test_source_with_no_images_or_annotations_is_a_configuration_error(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "train" / "images").mkdir(parents=True)
    (source / "train" / "annotations").mkdir(parents=True)

    with pytest.raises(DiscoveryError, match="no image or annotation"):
        discover_source(source)


def test_fingerprint_is_deterministic_and_tracks_changes(
    build_source_tree, tmp_path: Path
) -> None:
    root = build_source_tree(tmp_path / "source", {"train": [{"stem": "a"}, {"stem": "b"}]})

    before = fingerprint_source(root)
    before_again = fingerprint_source(root)

    assert before.entries == before_again.entries
    assert before.tree_sha256 == before_again.tree_sha256
    assert [entry["relative_path"] for entry in before.entries] == [
        "train/annotations/a.xml",
        "train/annotations/b.xml",
        "train/images/a.jpg",
        "train/images/b.jpg",
    ]

    (root / "train" / "annotations" / "a.xml").write_text("<changed/>\n", encoding="utf-8")
    (root / "train" / "images" / "c.jpg").write_bytes(b"new")

    after = fingerprint_source(root)
    comparison = compare_fingerprints(before, after)

    assert comparison.verified_after_run is False
    assert comparison.changed == [
        "train/annotations/a.xml",
        "train/images/c.jpg",
    ]
    assert comparison.tree_sha256 == after.tree_sha256

    unchanged = compare_fingerprints(before, before)
    assert unchanged.verified_after_run is True
    assert unchanged.changed == []


def test_pairing_merges_complete_samples_in_each_subset(
    build_source_tree, tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [{"stem": "shared"}],
            "validation": [{"stem": "shared"}],
        },
    )

    result = pair_samples(discover_source(root))

    assert [sample.sample_id for sample in result.samples] == [
        "train/shared",
        "validation/shared",
    ]
    assert result.anomalies == []
    assert result.unpaired_images == []
    assert result.unpaired_annotations == []
    for sample in result.samples:
        assert sample.image.subset == sample.source_subset
        assert sample.annotation.subset == sample.source_subset
        assert sample.image.stem == sample.annotation.stem == "shared"


def test_cross_subset_stem_is_never_paired(build_source_tree, tmp_path: Path) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [{"stem": "a", "write_xml": False}],
            "validation": [{"stem": "a", "write_image": False}],
        },
    )

    pairing = pair_samples(discover_source(root))

    assert pairing.samples == []
    assert [anomaly.code for anomaly in pairing.anomalies] == [
        "missing_image",
        "missing_xml",
    ]
    assert {anomaly.source_subset for anomaly in pairing.anomalies} == {"train", "validation"}
    assert [image.asset_id for image in pairing.unpaired_images] == ["train/images/a.jpg"]
    assert [annotation.asset_id for annotation in pairing.unpaired_annotations] == [
        "validation/annotations/a.xml"
    ]


def test_xml_filename_field_does_not_change_pairing(
    build_source_tree, tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "xml_filename": "../../validation/other.jpg",
                }
            ],
            "validation": [{"stem": "b"}],
        },
    )

    pairing = pair_samples(discover_source(root))

    assert [sample.sample_id for sample in pairing.samples] == [
        "train/a",
        "validation/b",
    ]
    assert pairing.anomalies == []


def test_missing_xml_and_missing_image_are_reported(
    build_source_tree, tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {"stem": "paired"},
                {"stem": "image_only", "write_xml": False},
            ],
            "validation": [
                {"stem": "xml_only", "write_image": False},
            ],
        },
    )

    pairing = pair_samples(discover_source(root))

    assert [sample.sample_id for sample in pairing.samples] == ["train/paired"]
    by_code = {anomaly.code: anomaly for anomaly in pairing.anomalies}
    assert set(by_code) == {"missing_xml", "missing_image"}

    missing_xml = by_code["missing_xml"]
    assert missing_xml.severity.value == "error"
    assert missing_xml.scope.value == "image"
    assert missing_xml.paths == ["train/images/image_only.jpg"]
    assert missing_xml.details["expected_xml"] == "train/annotations/image_only.xml"

    missing_image = by_code["missing_image"]
    assert missing_image.severity.value == "error"
    assert missing_image.scope.value == "annotation"
    assert missing_image.paths == ["validation/annotations/xml_only.xml"]
    assert missing_image.details["expected_image_stem"] == "validation/images/xml_only"


def test_ambiguous_pairing_never_creates_a_sample(
    build_source_tree, tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {"stem": "normal"},
                {"stem": "amb", "image_ext": ".jpg"},
                {"stem": "amb", "image_ext": ".png"},
            ]
        },
    )

    pairing = pair_samples(discover_source(root))

    assert [sample.sample_id for sample in pairing.samples] == ["train/normal"]
    ambiguous = [anomaly for anomaly in pairing.anomalies if anomaly.code == "ambiguous_pairing"]
    assert len(ambiguous) == 1
    assert ambiguous[0].severity.value == "error"
    assert ambiguous[0].scope.value == "subset"
    assert ambiguous[0].source_subset == "train"
    assert ambiguous[0].paths == [
        "train/annotations/amb.xml",
        "train/images/amb.jpg",
        "train/images/amb.png",
    ]
    assert [image.asset_id for image in pairing.unpaired_images] == [
        "train/images/amb.jpg",
        "train/images/amb.png",
    ]
    assert [annotation.asset_id for annotation in pairing.unpaired_annotations] == [
        "train/annotations/amb.xml"
    ]


def test_pairing_does_not_change_source_tree(build_source_tree, tmp_path: Path) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [{"stem": "a"}, {"stem": "image_only", "write_xml": False}],
            "validation": [{"stem": "b"}],
        },
    )
    before = _tree_snapshot(root)

    result = discover_source(root)
    pair_samples(result)

    assert _tree_snapshot(root) == before
