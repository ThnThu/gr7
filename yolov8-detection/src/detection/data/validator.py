"""Image-level verification for the NEU-DET pipeline (T014).

Pillow opens each image, reports the actual pixel size and checks file
integrity with :meth:`PIL.Image.Image.verify`. The source file is opened
read-only; verification never rewrites the image. A file that cannot be opened
or fails verification is reported as ``corrupt_image``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .models import AnomalyRecord


@dataclass
class ImageVerification:
    """Outcome of verifying one source image."""

    path: Path
    valid: bool
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    image_format: str | None = None
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    reason: str | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _corrupt(
    path: Path,
    *,
    reason: str,
    sample_id: str | None,
    source_subset: str | None,
    label_path: str,
) -> AnomalyRecord:
    return AnomalyRecord(
        code="corrupt_image",
        severity="error",
        scope="image",
        sample_id=sample_id,
        source_subset=source_subset,
        paths=[label_path],
        reason=reason,
        details={"image": path.name},
    )


def verify_image(
    image_path: str | Path,
    *,
    sample_id: str | None = None,
    source_subset: str | None = None,
    source_path: str | None = None,
) -> ImageVerification:
    """Open, verify and hash one image without modifying it.

    Args:
        image_path: Existing image file.
        sample_id: Optional ``<subset>/<stem>`` used in anomaly records.
        source_subset: Optional source subset used in anomaly records.
        source_path: Optional path relative to the source root for anomaly
            records.

    Returns:
        An :class:`ImageVerification`. ``valid`` is ``False`` when the image
        cannot be decoded; ``width``/``height`` are the actual dimensions on
        success and the only size the converter should use.
    """
    path = Path(image_path)
    label_path = source_path or path.name

    try:
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
            image.verify()
    except (OSError, ValueError, SyntaxError) as exc:
        return ImageVerification(
            path=path,
            valid=False,
            anomalies=[
                _corrupt(
                    path,
                    reason=f"cannot open or verify image: {exc}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    label_path=label_path,
                )
            ],
            reason=str(exc),
        )

    if width <= 0 or height <= 0:
        return ImageVerification(
            path=path,
            valid=False,
            width=width,
            height=height,
            image_format=image_format,
            anomalies=[
                _corrupt(
                    path,
                    reason=f"image reports non-positive size: {width}x{height}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    label_path=label_path,
                )
            ],
            reason="non-positive image size",
        )

    try:
        digest = _sha256_file(path)
    except OSError as exc:
        return ImageVerification(
            path=path,
            valid=False,
            width=width,
            height=height,
            image_format=image_format,
            anomalies=[
                _corrupt(
                    path,
                    reason=f"cannot read image bytes for hashing: {exc}",
                    sample_id=sample_id,
                    source_subset=source_subset,
                    label_path=label_path,
                )
            ],
            reason=str(exc),
        )

    return ImageVerification(
        path=path,
        valid=True,
        width=int(width),
        height=int(height),
        sha256=digest,
        image_format=image_format,
    )

