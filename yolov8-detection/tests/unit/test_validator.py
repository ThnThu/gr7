"""Unit tests for the US2 validation orchestrator and duplicate audit (T017).

These tests exercise the sample-validation orchestrator that T020/T021 will add
to :mod:`detection.data.validator`.  They deliberately target the orchestrator
API instead of re-testing discovery, pairing, XML parsing, class mapping or
bbox validation:

* ``validate_samples(samples, source_root)`` returns a result with
  ``.samples`` (all paired samples, annotated and stateful) and ``.anomalies``.
* ``audit_duplicate_groups(samples)`` returns a result with ``.groups``
  (in-memory :class:`~detection.data.models.DuplicateGroup` objects) and
  ``.anomalies``.

At T017 time those callables are intentionally absent; tests fail with an
explicit "implementation is still missing" assertion until T020/T021 land.
All fixtures are synthetic and live under ``tmp_path``.  Pairing-specific
behaviour (``missing_xml``, ``missing_image``, ``ambiguous_pairing`` and
cross-subset pairing) stays covered by ``test_discovery.py``.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence

import pytest

import detection.data.converter as converter_module
import detection.data.validator as validator_module
from detection.data.discovery import discover_source, fingerprint_source, pair_samples
from detection.data.models import (
    AnomalyRecord,
    DuplicateGroupState,
    MatchedSample,
    SampleState,
    Severity,
)
from detection.data.validator import ImageVerification

DEFAULT_BBOX = (20.0, 20.0, 80.0, 80.0)
OBJECT_A = {"name": "crazing", "bbox": DEFAULT_BBOX}
OBJECT_B = {"name": "patches", "bbox": (120.0, 120.0, 180.0, 180.0)}


# ---------------------------------------------------------------------------
# small helpers shared by the test cases
# ---------------------------------------------------------------------------


def _required(name: str) -> Callable[..., Any]:
    fn = getattr(validator_module, name, None)
    assert callable(fn), (
        f"T020/T021 implementation is still missing: "
        f"detection.data.validator.{name} does not exist"
    )
    return fn


def _paired(root: Path) -> list[MatchedSample]:
    pairing = pair_samples(discover_source(root))
    assert pairing.anomalies == [], (
        "pairing anomalies are covered in test_discovery.py, not here"
    )
    return pairing.samples


def _validate(samples: Sequence[MatchedSample], root: Path) -> Any:
    return _required("validate_samples")(samples, root)


def _audit(samples: Sequence[MatchedSample]) -> Any:
    return _required("audit_duplicate_groups")(samples)


def _by_id(result: Any) -> dict[str, MatchedSample]:
    return {sample.sample_id: sample for sample in result.samples}


def _eligible(result: Any) -> list[MatchedSample]:
    error_ids = {
        anomaly.sample_id
        for anomaly in result.anomalies
        if anomaly.severity == Severity.ERROR and anomaly.sample_id is not None
    }
    return [
        sample
        for sample in result.samples
        if sample.state != SampleState.INVALID and sample.sample_id not in error_ids
    ]


def _codes(result: Any) -> list[str]:
    return [anomaly.code for anomaly in result.anomalies]


def _one(records: Sequence[AnomalyRecord], code: str) -> AnomalyRecord:
    found = [record for record in records if record.code == code]
    assert len(found) == 1, f"expected exactly one {code!r} anomaly, got {len(found)}"
    return found[0]


def _spy(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    name: str,
    *,
    also_module: Any | None = None,
) -> list[SimpleNamespace]:
    """Wrap a helper in place so the test can observe real calls."""
    real = getattr(module, name)
    calls: list[SimpleNamespace] = []

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        outcome = real(*args, **kwargs)
        calls.append(SimpleNamespace(args=args, kwargs=kwargs, result=outcome))
        return outcome

    monkeypatch.setattr(module, name, wrapper)
    if also_module is not None and hasattr(also_module, name):
        monkeypatch.setattr(also_module, name, wrapper)
    return calls


def _spy_verify(monkeypatch: pytest.MonkeyPatch) -> list[SimpleNamespace]:
    return _spy(monkeypatch, validator_module, "verify_image")


def _spy_convert(monkeypatch: pytest.MonkeyPatch) -> list[SimpleNamespace]:
    return _spy(
        monkeypatch,
        converter_module,
        "convert_annotation",
        also_module=validator_module,
    )


def _call_path(call: SimpleNamespace) -> Path:
    if call.args:
        return Path(call.args[0])
    for key in ("image_path", "xml_path", "path"):
        if key in call.kwargs:
            return Path(call.kwargs[key])
    raise AssertionError("orchestrator call did not pass a path argument")


def _path_endswith(path: str | Path, suffix: str) -> bool:
    return Path(path).as_posix().endswith(suffix)


def _make_identical_images(root: Path, first: str, second: str) -> None:
    """Copy synthetic image bytes (never from the real dataset)."""
    (root / second).write_bytes((root / first).read_bytes())


def _contract_sort_key(anomaly: AnomalyRecord) -> tuple[Any, ...]:
    """The anomaly ordering fixed by data-model.md section 6."""
    sample_id = anomaly.sample_id
    object_index = anomaly.details.get("object_index")
    return (
        anomaly.code,
        tuple(anomaly.paths),
        (1, "") if sample_id is None else (0, sample_id),
        (1, 0) if object_index is None else (0, int(object_index)),
        anomaly.reason,
    )


# ---------------------------------------------------------------------------
# orchestrator reuses the existing image and annotation helpers
# ---------------------------------------------------------------------------


def test_orchestrator_reuses_verify_image_and_convert_annotation(
    build_source_tree: Callable[..., Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "size": (200, 200),
                    "objects": [OBJECT_A, OBJECT_B],
                }
            ]
        },
    )
    samples = _paired(root)
    verify_calls = _spy_verify(monkeypatch)
    convert_calls = _spy_convert(monkeypatch)

    result = _validate(samples, root)

    assert len(verify_calls) == 1
    assert len(convert_calls) == 1
    assert _path_endswith(_call_path(verify_calls[0]), "train/images/a.jpg")
    assert _path_endswith(_call_path(convert_calls[0]), "train/annotations/a.xml")
    assert convert_calls[0].kwargs["image_width"] == 200
    assert convert_calls[0].kwargs["image_height"] == 200
    sample = _by_id(result)["train/a"]
    assert sample.present_classes == [0, 2]
    assert sample.label_lines == convert_calls[0].result.label_lines
    assert len(sample.label_lines) == 2


def test_normalization_uses_size_returned_by_verify_image(
    build_source_tree: Callable[..., Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {"train": [{"stem": "a", "size": (200, 200), "objects": [OBJECT_A]}]},
    )
    samples = _paired(root)

    def fake_verify(path: Path | str, **kwargs: Any) -> ImageVerification:
        return ImageVerification(
            path=Path(path), valid=True, width=100, height=100, sha256="fake-digest"
        )

    monkeypatch.setattr(validator_module, "verify_image", fake_verify)
    convert_calls = _spy_convert(monkeypatch)

    result = _validate(samples, root)

    assert len(convert_calls) == 1
    assert convert_calls[0].kwargs["image_width"] == 100
    assert convert_calls[0].kwargs["image_height"] == 100
    assert _by_id(result)["train/a"].label_lines == [
        "0 0.500000 0.500000 0.600000 0.600000"
    ]


# ---------------------------------------------------------------------------
# annotation / class / bbox / image anomalies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("issue", ["malformed", "omit_name", "omit_bndbox"])
def test_invalid_xml_is_reported_and_rejects_the_sample(
    build_source_tree: Callable[..., Path], tmp_path: Path, issue: str
) -> None:
    flags = {"xml_malformed": True} if issue == "malformed" else {issue: True}
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "objects": [OBJECT_A],
                    **flags,
                }
            ]
        },
    )
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "invalid_xml")
    assert anomaly.severity == Severity.ERROR
    assert anomaly.scope.value == "annotation"
    assert anomaly.sample_id == "train/a"
    assert anomaly.source_subset == "train"
    assert any(_path_endswith(path, "train/annotations/a.xml") for path in anomaly.paths)
    sample = _by_id(result)["train/a"]
    assert sample.state == SampleState.INVALID
    assert sample.label_lines == []


def test_unknown_class_is_reported_without_remapping(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "objects": [OBJECT_A, {"name": "Scratch", "bbox": DEFAULT_BBOX}],
                }
            ]
        },
    )
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "unknown_class")
    assert anomaly.severity == Severity.ERROR
    assert anomaly.scope.value == "sample"
    assert anomaly.details["object_index"] == 1
    assert anomaly.details["name_raw"] == "Scratch"
    assert anomaly.details["name_normalized"] == "scratch"
    sample = _by_id(result)["train/a"]
    assert sample.state == SampleState.INVALID
    assert sample.label_lines == []


@pytest.mark.parametrize(
    "bbox",
    [
        (100.0, 20.0, 100.0, 80.0),  # xmin >= xmax
        (20.0, 100.0, 80.0, 100.0),  # ymin >= ymax
        (-1.0, 20.0, 80.0, 80.0),  # negative xmin
        (20.0, -1.0, 80.0, 80.0),  # negative ymin
        (20.0, 20.0, 201.0, 80.0),  # xmax out of bounds
        (20.0, 20.0, 80.0, 201.0),  # ymax out of bounds
        ("abc", 20.0, 80.0, 80.0),  # non-numeric
    ],
)
def test_invalid_bbox_variants_reject_the_sample(
    build_source_tree: Callable[..., Path],
    tmp_path: Path,
    bbox: tuple[Any, Any, Any, Any],
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "size": (200, 200),
                    "objects": [{"name": "crazing", "bbox": bbox}],
                }
            ]
        },
    )
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "invalid_bbox")
    assert anomaly.severity == Severity.ERROR
    assert anomaly.scope.value == "sample"
    assert anomaly.sample_id == "train/a"
    assert anomaly.details["object_index"] == 0
    sample = _by_id(result)["train/a"]
    assert sample.state == SampleState.INVALID
    assert sample.label_lines == []


@pytest.mark.parametrize(
    "bbox",
    [
        (10.0, 10.0, 10.0000004, 20.0),  # width rounds to zero
        (10.0, 10.0, 20.0, 10.0000004),  # height rounds to zero
    ],
)
def test_bbox_that_rounds_to_zero_size_is_reported(
    build_source_tree: Callable[..., Path],
    tmp_path: Path,
    bbox: tuple[float, float, float, float],
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "size": (200, 200),
                    "objects": [{"name": "scratches", "bbox": bbox}],
                }
            ]
        },
    )
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "invalid_bbox")
    assert "round" in anomaly.reason.lower() or "zero" in anomaly.reason.lower()
    assert _by_id(result)["train/a"].state == SampleState.INVALID
    assert _by_id(result)["train/a"].label_lines == []


def test_out_of_bounds_box_is_neither_clipped_nor_repaired(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    bbox = (20.0, 20.0, 250.0, 80.0)
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "size": (200, 200),
                    "objects": [{"name": "crazing", "bbox": bbox}],
                }
            ]
        },
    )
    samples = _paired(root)
    before = fingerprint_source(root).tree_sha256

    result = _validate(samples, root)

    sample = _by_id(result)["train/a"]
    anomaly = _one(result.anomalies, "invalid_bbox")
    assert anomaly.details["bbox"] == list(bbox)
    assert anomaly.details["image"] == {"width": 200, "height": 200}
    assert sample.label_lines == []
    assert fingerprint_source(root).tree_sha256 == before


def test_one_invalid_object_rejects_the_whole_sample(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "size": (200, 200),
                    "objects": [
                        OBJECT_A,
                        {"name": "patches", "bbox": (120.0, 20.0, 120.0, 80.0)},
                        OBJECT_B,
                    ],
                }
            ]
        },
    )
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "invalid_bbox")
    assert anomaly.details["object_index"] == 1
    sample = _by_id(result)["train/a"]
    assert sample.state == SampleState.INVALID
    assert sample.label_lines == []


def test_corrupt_image_is_reported_and_the_sample_is_rejected(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {"train": [{"stem": "a", "objects": [OBJECT_A]}]},
    )
    (root / "train" / "images" / "a.jpg").write_bytes(b"not a decodable image")
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "corrupt_image")
    assert anomaly.severity == Severity.ERROR
    assert anomaly.scope.value == "image"
    assert anomaly.sample_id == "train/a"
    assert anomaly.source_subset == "train"
    assert any(_path_endswith(path, "train/images/a.jpg") for path in anomaly.paths)
    sample = _by_id(result)["train/a"]
    assert sample.state == SampleState.INVALID
    assert sample.label_lines == []


def test_size_mismatch_has_both_paths_and_uses_the_actual_size(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "size": (200, 200),
                    "declared_size": (400, 300),
                    "objects": [OBJECT_A],
                }
            ]
        },
    )
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "size_mismatch")
    assert anomaly.severity == Severity.WARNING
    assert anomaly.scope.value == "sample"
    assert anomaly.sample_id == "train/a"
    assert len(anomaly.paths) == 2
    assert {Path(path).as_posix() for path in anomaly.paths} == {
        "train/images/a.jpg",
        "train/annotations/a.xml",
    }
    assert anomaly.details["declared"] == {"width": 400, "height": 300}
    assert anomaly.details["actual"] == {"width": 200, "height": 200}
    sample = _by_id(result)["train/a"]
    assert sample.label_lines == ["0 0.250000 0.250000 0.300000 0.300000"]
    assert sample.state != SampleState.INVALID


@pytest.mark.parametrize(
    "declared_filename",
    ["different.jpg", "../../validation/other.jpg", "folder/other.jpg"],
)
def test_filename_mismatch_compares_basename_and_keeps_the_pair(
    build_source_tree: Callable[..., Path],
    tmp_path: Path,
    declared_filename: str,
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "objects": [OBJECT_A],
                    "xml_filename": declared_filename,
                }
            ]
        },
    )
    samples = _paired(root)
    assert [sample.sample_id for sample in samples] == ["train/a"]

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "filename_mismatch")
    assert anomaly.severity == Severity.WARNING
    assert anomaly.scope.value == "annotation"
    assert anomaly.sample_id == "train/a"
    assert len(anomaly.paths) == 2
    assert {Path(path).as_posix() for path in anomaly.paths} == {
        "train/images/a.jpg",
        "train/annotations/a.xml",
    }
    assert anomaly.details["declared_filename"] == declared_filename
    assert anomaly.details["actual_filename"] == "a.jpg"
    sample = _by_id(result)["train/a"]
    assert sample.sample_id == "train/a"
    assert sample.image.stem == sample.annotation.stem == "a"
    assert sample.state != SampleState.INVALID


def test_matching_filename_basename_does_not_emit_a_warning(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {
                    "stem": "a",
                    "objects": [OBJECT_A],
                    "xml_filename": "elsewhere/a.jpg",
                }
            ]
        },
    )
    samples = _paired(root)

    result = _validate(samples, root)

    assert "filename_mismatch" not in _codes(result)
    assert _by_id(result)["train/a"].state != SampleState.INVALID


def test_empty_annotation_is_retained_with_an_info_anomaly(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {"train": [{"stem": "a", "objects": []}]},
    )
    samples = _paired(root)

    result = _validate(samples, root)

    anomaly = _one(result.anomalies, "empty_annotation")
    assert anomaly.severity == Severity.INFO
    assert anomaly.scope.value == "sample"
    assert anomaly.sample_id == "train/a"
    sample = _by_id(result)["train/a"]
    assert sample.state != SampleState.INVALID
    assert sample.present_classes == []
    assert sample.label_lines == []


# ---------------------------------------------------------------------------
# duplicate-content audit
# ---------------------------------------------------------------------------


def test_duplicate_group_is_built_from_eligible_samples_with_orderless_labels(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {"stem": "a", "objects": [OBJECT_A, OBJECT_B]},
                {"stem": "b", "objects": [OBJECT_B, OBJECT_A]},
            ]
        },
    )
    _make_identical_images(root, "train/images/a.jpg", "train/images/b.jpg")
    samples = _paired(root)

    validated = _validate(samples, root)
    eligible = _eligible(validated)
    audit = _audit(eligible)

    assert len(audit.groups) == 1
    group = audit.groups[0]
    digest = hashlib.sha256((root / "train" / "images" / "a.jpg").read_bytes()).hexdigest()
    assert group.sha256 == f"sha256:{digest}"
    assert group.group_id == group.sha256
    assert sorted(group.members) == ["train/a", "train/b"]
    assert group.labels_consistent is True
    assert group.state == DuplicateGroupState.GROUPED
    assert sorted(_by_id(validated)["train/a"].label_lines) == sorted(
        _by_id(validated)["train/b"].label_lines
    )

    records = [record for record in audit.anomalies if record.code == "duplicate_content"]
    assert Counter(record.sample_id for record in records) == {"train/a": 1, "train/b": 1}
    for record in records:
        assert record.severity == Severity.WARNING
        assert record.scope.value == "sample"
        assert record.source_subset == "train"
        assert record.details["group_id"] == group.group_id
        assert record.details["sha256"] == group.sha256
        assert record.details["member_count"] == 2
        assert record.details["labels_consistent"] is True
        own_image = f"train/images/{Path(record.sample_id).name}.jpg"
        own_xml = f"train/annotations/{Path(record.sample_id).name}.xml"
        assert {Path(path).as_posix() for path in record.paths} == {
            own_image,
            own_xml,
        }
    for sample in eligible:
        assert sample.state != SampleState.INVALID
        assert sample.duplicate_group == group.group_id


@pytest.mark.parametrize(
    ("objects_b", "conflict_kind"),
    [
        ([{"name": "patches", "bbox": DEFAULT_BBOX}], "class"),
        ([{"name": "crazing", "bbox": (21.0, 20.0, 80.0, 80.0)}], "coordinates"),
    ],
)
def test_conflicting_duplicate_labels_are_an_error_for_every_member(
    build_source_tree: Callable[..., Path],
    tmp_path: Path,
    objects_b: list[dict[str, Any]],
    conflict_kind: str,
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {"stem": "a", "objects": [OBJECT_A]},
                {"stem": "b", "objects": objects_b},
            ]
        },
    )
    _make_identical_images(root, "train/images/a.jpg", "train/images/b.jpg")
    samples = _paired(root)

    validated = _validate(samples, root)
    audit = _audit(_eligible(validated))

    assert len(audit.groups) == 1
    group = audit.groups[0]
    assert sorted(group.members) == ["train/a", "train/b"]
    assert group.labels_consistent is False, f"expected conflict for {conflict_kind}"
    assert group.state == DuplicateGroupState.CONFLICT
    records = [record for record in audit.anomalies if record.code == "duplicate_content"]
    assert Counter(record.sample_id for record in records) == {"train/a": 1, "train/b": 1}
    assert all(record.severity == Severity.ERROR for record in records)
    assert all(record.details["labels_consistent"] is False for record in records)


def test_duplicate_audit_ignores_invalid_and_unique_samples(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    bad_box = (100.0, 20.0, 100.0, 80.0)
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {"stem": "ok_a", "color": (10, 20, 30), "objects": [OBJECT_A]},
                {"stem": "ok_b", "color": (99, 99, 99), "objects": [OBJECT_A]},
                {"stem": "bad_a", "color": (40, 50, 60), "objects": [{"name": "crazing", "bbox": bad_box}]},
                {"stem": "bad_b", "color": (99, 99, 99), "objects": [{"name": "crazing", "bbox": bad_box}]},
                {"stem": "unique", "color": (70, 80, 90), "objects": [OBJECT_A]},
            ]
        },
    )
    _make_identical_images(root, "train/images/ok_a.jpg", "train/images/ok_b.jpg")
    _make_identical_images(root, "train/images/bad_a.jpg", "train/images/bad_b.jpg")
    samples = _paired(root)

    validated = _validate(samples, root)
    eligible = _eligible(validated)
    assert {sample.sample_id for sample in eligible} == {
        "train/ok_a",
        "train/ok_b",
        "train/unique",
    }
    audit = _audit(eligible)

    assert [sorted(group.members) for group in audit.groups] == [
        ["train/ok_a", "train/ok_b"]
    ]
    duplicate_ids = {
        record.sample_id
        for record in audit.anomalies
        if record.code == "duplicate_content"
    }
    assert duplicate_ids == {"train/ok_a", "train/ok_b"}
    assert "train/unique" not in {sample.duplicate_group for sample in eligible}


def test_anomaly_ordering_is_deterministic_and_follows_the_contract(
    build_source_tree: Callable[..., Path], tmp_path: Path
) -> None:
    root = build_source_tree(
        tmp_path / "source",
        {
            "train": [
                {"stem": "c_empty", "color": (11, 11, 11), "objects": []},
                {
                    "stem": "a_bad",
                    "color": (22, 22, 22),
                    "objects": [
                        OBJECT_A,
                        {"name": "patches", "bbox": (120.0, 20.0, 120.0, 80.0)},
                    ],
                },
                {
                    "stem": "b_bad",
                    "color": (33, 33, 33),
                    "objects": [{"name": "crazing", "bbox": (100.0, 20.0, 100.0, 80.0)}],
                },
                {"stem": "d_dup1", "color": (44, 44, 44), "objects": [OBJECT_A]},
                {"stem": "e_dup2", "color": (55, 55, 55), "objects": [OBJECT_A]},
            ]
        },
    )
    _make_identical_images(
        root, "train/images/d_dup1.jpg", "train/images/e_dup2.jpg"
    )
    samples = _paired(root)

    first = _validate(samples, root)
    first_audit = _audit(_eligible(first))
    second = _validate(list(reversed(_paired(root))), root)
    second_audit = _audit(_eligible(second))

    assert first.anomalies == second.anomalies
    assert first_audit.anomalies == second_audit.anomalies
    assert first.anomalies == sorted(first.anomalies, key=_contract_sort_key)
    assert first_audit.anomalies == sorted(
        first_audit.anomalies, key=_contract_sort_key
    )
