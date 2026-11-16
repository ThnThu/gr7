"""Fixed NEU-DET class catalogue.

The catalogue is intentionally frozen: the six class IDs, their order and their
canonical names are part of the Feature 001 data contract and are consumed by
Feature 002. There are no aliases, no fuzzy matching and no remapping.
"""

from __future__ import annotations

CLASS_NAMES: dict[int, str] = {
    0: "crazing",
    1: "inclusion",
    2: "patches",
    3: "pitted_surface",
    4: "rolled-in_scale",
    5: "scratches",
}

CLASS_IDS: tuple[int, ...] = (0, 1, 2, 3, 4, 5)

UNKNOWN_CLASS_CODE = "unknown_class"

_BY_NAME: dict[str, int] = {name: class_id for class_id, name in CLASS_NAMES.items()}


class UnknownClassError(ValueError):
    """Raised when a source class name is not one of the six fixed classes."""

    code = UNKNOWN_CLASS_CODE

    def __init__(self, name: str) -> None:
        self.name = name
        normalized = normalize_class_name(name)
        super().__init__(
            f"unknown_class: {name!r} (normalized {normalized!r}) is not one of "
            f"the six fixed NEU-DET classes"
        )


def normalize_class_name(name: str) -> str:
    """Return ``name`` normalized with ``strip()`` then ``lower()`` only."""
    return str(name).strip().lower()


def get_class_id(name: str) -> int:
    """Map a source class name to its fixed class ID.

    Raises:
        UnknownClassError: if the normalized name is not an exact class name.
    """
    normalized = normalize_class_name(name)
    try:
        return _BY_NAME[normalized]
    except KeyError as exc:
        raise UnknownClassError(name) from exc


def get_class_name(class_id: int) -> str:
    """Return the canonical name for ``class_id`` in ``0..5``."""
    if class_id not in CLASS_NAMES:
        raise ValueError(f"class_id must be in 0..5, got {class_id!r}")
    return CLASS_NAMES[class_id]


def class_mapping() -> list[dict[str, object]]:
    """Return the ordered ``class_mapping`` payload used by report/manifest."""
    return [{"id": class_id, "name": name} for class_id, name in CLASS_NAMES.items()]
