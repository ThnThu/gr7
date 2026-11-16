"""Unit tests for the fixed NEU-DET class catalogue (T004/T010)."""

from __future__ import annotations

import pytest

from detection.data.classes import (
    CLASS_IDS,
    CLASS_NAMES,
    UnknownClassError,
    class_mapping,
    get_class_id,
    get_class_name,
    normalize_class_name,
)


def test_class_names_have_exact_fixed_order() -> None:
    assert list(CLASS_NAMES.items()) == [
        (0, "crazing"),
        (1, "inclusion"),
        (2, "patches"),
        (3, "pitted_surface"),
        (4, "rolled-in_scale"),
        (5, "scratches"),
    ]
    assert CLASS_IDS == (0, 1, 2, 3, 4, 5)


def test_class_mapping_payload_is_ordered_and_complete() -> None:
    assert class_mapping() == [
        {"id": 0, "name": "crazing"},
        {"id": 1, "name": "inclusion"},
        {"id": 2, "name": "patches"},
        {"id": 3, "name": "pitted_surface"},
        {"id": 4, "name": "rolled-in_scale"},
        {"id": 5, "name": "scratches"},
    ]


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("crazing", "crazing"),
        ("  CRAZING  ", "crazing"),
        ("\tPitted_Surface\n", "pitted_surface"),
        ("  rolled-in_scale  ", "rolled-in_scale"),
        ("Scratches", "scratches"),
    ],
)
def test_normalization_uses_only_strip_and_lower(raw: str, normalized: str) -> None:
    assert normalize_class_name(raw) == normalized
    assert get_class_id(raw) == get_class_id(normalized)


def test_normalization_is_not_fuzzy_and_does_not_change_internal_characters() -> None:
    assert normalize_class_name("pitted surface") == "pitted surface"
    assert normalize_class_name("rolled_in_scale") == "rolled_in_scale"


@pytest.mark.parametrize(
    "raw",
    [
        "crazingg",
        "crazing_",
        "rolled_in_scale",
        "rolled in scale",
        "pitted surface",
        "patch",
        "inclusions",
        "scatch",
        "",
        "   ",
        "unknown",
        "crazing\ninclusion",
    ],
)
def test_unknown_aliases_and_fuzzy_names_are_rejected(raw: str) -> None:
    with pytest.raises(UnknownClassError) as excinfo:
        get_class_id(raw)
    assert excinfo.value.code == "unknown_class"
    assert excinfo.value.name == raw


def test_get_class_id_accepts_every_canonical_name() -> None:
    for class_id, name in CLASS_NAMES.items():
        assert get_class_id(name) == class_id
        assert get_class_name(class_id) == name


@pytest.mark.parametrize("class_id", [-1, 6, 99])
def test_get_class_name_rejects_ids_outside_zero_to_five(class_id: int) -> None:
    with pytest.raises(ValueError, match="0\\.\\.5"):
        get_class_name(class_id)
