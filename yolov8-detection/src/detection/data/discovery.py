"""Source discovery, fingerprinting and within-subset pairing.

Discovery never modifies the source tree. Pairing is intentionally restricted
to one :class:`~detection.data.models.SourceSubset`: an image and an XML file
are paired only when they share an exact stem inside the same subset. XML
``<filename>`` values are never consulted.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    IMAGE_EXTENSIONS,
    AnnotationAsset,
    AnomalyRecord,
    ImageAsset,
    ImageStatus,
    AnnotationStatus,
    MatchedSample,
    SampleState,
    SourceDataset,
    SourceFingerprint,
    SourceSubset,
)


class DiscoveryError(Exception):
    """Configuration or source-structure error (CLI exit code 2)."""

    exit_code = 2


@dataclass
class DiscoveryResult:
    dataset: SourceDataset
    subsets: list[SourceSubset]
    images: list[ImageAsset]
    annotations: list[AnnotationAsset]
    anomalies: list[AnomalyRecord] = field(default_factory=list)


@dataclass
class PairingResult:
    samples: list[MatchedSample] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    unpaired_images: list[ImageAsset] = field(default_factory=list)
    unpaired_annotations: list[AnnotationAsset] = field(default_factory=list)


def _sorted_files(root: Path, directory: Path) -> list[Path]:
    return sorted(
        (path for path in directory.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _discover_subsets(source: Path) -> list[tuple[str, Path]]:
    root_images = source / "images"
    root_annotations = source / "annotations"
    root_has_images = root_images.is_dir()
    root_has_annotations = root_annotations.is_dir()

    if root_has_images or root_has_annotations:
        if not (root_has_images and root_has_annotations):
            missing = "annotations" if root_has_images else "images"
            raise DiscoveryError(
                "source root must contain both 'images/' and 'annotations/'; "
                f"missing '{missing}/'"
            )
        return [("root", source)]

    subsets: list[tuple[str, Path]] = []
    for child in sorted(source.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        has_images = (child / "images").is_dir()
        has_annotations = (child / "annotations").is_dir()
        if has_images and has_annotations:
            subsets.append((child.name, child))
        elif has_images or has_annotations:
            missing = "annotations" if has_images else "images"
            raise DiscoveryError(
                f"subset {child.name!r} must contain both 'images/' and "
                f"'annotations/'; missing '{missing}/'"
            )

    if not subsets:
        raise DiscoveryError(
            "source contains no image or annotation files: no 'images/' + "
            "'annotations/' directory pair was found"
        )
    return subsets


def discover_source(
    source: str | Path,
    *,
    compute_fingerprint: bool = True,
) -> DiscoveryResult:
    """Discover source subsets, images and XML files in stable sorted order."""
    root = Path(source).expanduser().resolve()
    if not root.exists():
        raise DiscoveryError(f"source path does not exist: {root}")
    if not root.is_dir():
        raise DiscoveryError(f"source path is not a directory: {root}")

    subset_dirs = _discover_subsets(root)
    subsets: list[SourceSubset] = []
    images: list[ImageAsset] = []
    annotations: list[AnnotationAsset] = []
    image_paths: list[Path] = []
    annotation_paths: list[Path] = []
    anomalies: list[AnomalyRecord] = []

    for name, subset_root in subset_dirs:
        images_dir = subset_root / "images"
        annotations_dir = subset_root / "annotations"
        subsets.append(
            SourceSubset(
                name=name,
                relative_prefix=name,
                images_dir=images_dir,
                annotations_dir=annotations_dir,
            )
        )

        for path in _sorted_files(root, subset_root):
            relative_path = path.relative_to(subset_root)
            asset_id = f"{name}/{relative_path.as_posix()}"
            suffix = path.suffix.lower()
            in_images = path.is_relative_to(images_dir)
            in_annotations = path.is_relative_to(annotations_dir)

            if in_images and suffix in IMAGE_EXTENSIONS:
                images.append(
                    ImageAsset(
                        asset_id=asset_id,
                        subset=name,
                        relative_path=relative_path,
                        stem=path.stem,
                        extension=path.suffix,
                    )
                )
                image_paths.append(path)
            elif in_annotations and suffix == ".xml":
                annotations.append(
                    AnnotationAsset(
                        asset_id=asset_id,
                        subset=name,
                        relative_path=relative_path,
                        stem=path.stem,
                    )
                )
                annotation_paths.append(path)
            else:
                if in_images:
                    reason = (
                        "file extension is not a supported image format; "
                        "file ignored"
                    )
                elif in_annotations:
                    reason = "file extension is not '.xml'; file ignored"
                else:
                    reason = (
                        "file is outside the subset 'images/' and "
                        "'annotations/' directories; file ignored"
                    )
                anomalies.append(
                    AnomalyRecord(
                        code="unsupported_file",
                        severity="info",
                        scope="dataset",
                        source_subset=name,
                        paths=[asset_id],
                        reason=reason,
                        details={"extension": path.suffix},
                    )
                )

    if not images and not annotations:
        raise DiscoveryError(
            "source contains no image or annotation files to process"
        )

    subset_roots = {subset_root for _, subset_root in subset_dirs}
    for path in _sorted_files(root, root):
        if any(path.is_relative_to(subset_root) for subset_root in subset_roots):
            continue
        relative_path = path.relative_to(root)
        anomalies.append(
            AnomalyRecord(
                code="unsupported_file",
                severity="info",
                scope="dataset",
                paths=[relative_path.as_posix()],
                reason=(
                    "file is outside every recognised subset directory; "
                    "file ignored"
                ),
                details={"extension": path.suffix},
            )
        )

    subsets.sort(key=lambda subset: subset.name)
    images.sort(key=lambda image: image.asset_id)
    annotations.sort(key=lambda annotation: annotation.asset_id)
    anomalies.sort(key=lambda anomaly: (anomaly.code, tuple(anomaly.paths)))

    dataset = SourceDataset(
        root=root,
        subsets=subsets,
        image_files=sorted(image_paths),
        annotation_files=sorted(annotation_paths),
        fingerprint=(
            fingerprint_source(root) if compute_fingerprint else SourceFingerprint()
        ),
        read_only=True,
    )
    return DiscoveryResult(
        dataset=dataset,
        subsets=subsets,
        images=images,
        annotations=annotations,
        anomalies=anomalies,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_sha256(entries: list[dict[str, object]]) -> str:
    canonical = "\n".join(
        f"{entry['relative_path']}\0{entry['size']}\0{entry['sha256']}"
        for entry in entries
    )
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def fingerprint_source(source: str | Path) -> SourceFingerprint:
    """Return a deterministic SHA-256 fingerprint of every file in the tree."""
    root = Path(source).expanduser().resolve()
    if not root.exists():
        raise DiscoveryError(f"source path does not exist: {root}")
    if not root.is_dir():
        raise DiscoveryError(f"source path is not a directory: {root}")

    entries: list[dict[str, object]] = []
    for path in sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    ):
        entries.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return SourceFingerprint(
        algorithm="sha256",
        entries=entries,
        tree_sha256=_tree_sha256(entries),
        verified_after_run=False,
        changed=[],
    )


def compare_fingerprints(
    before: SourceFingerprint,
    after: SourceFingerprint,
) -> SourceFingerprint:
    """Compare two source fingerprints and report added/modified/removed files."""
    before_entries = {
        str(entry["relative_path"]): (entry["size"], entry["sha256"])
        for entry in before.entries
    }
    after_entries = {
        str(entry["relative_path"]): (entry["size"], entry["sha256"])
        for entry in after.entries
    }
    changed = sorted(
        relative_path
        for relative_path in set(before_entries) | set(after_entries)
        if before_entries.get(relative_path) != after_entries.get(relative_path)
    )
    verified = (
        not changed
        and before.algorithm == after.algorithm
        and before.tree_sha256 == after.tree_sha256
    )
    return SourceFingerprint(
        algorithm=after.algorithm,
        entries=after.entries,
        tree_sha256=after.tree_sha256,
        verified_after_run=verified,
        changed=changed,
    )


def pair_samples(discovery: DiscoveryResult) -> PairingResult:
    """Pair images and XML by exact stem within each source subset only."""
    samples: list[MatchedSample] = []
    anomalies: list[AnomalyRecord] = []
    unpaired_images: list[ImageAsset] = []
    unpaired_annotations: list[AnnotationAsset] = []

    for subset in discovery.subsets:
        images_by_stem: dict[str, list[ImageAsset]] = defaultdict(list)
        annotations_by_stem: dict[str, list[AnnotationAsset]] = defaultdict(list)
        for image in discovery.images:
            if image.subset == subset.name:
                images_by_stem[image.stem].append(image)
        for annotation in discovery.annotations:
            if annotation.subset == subset.name:
                annotations_by_stem[annotation.stem].append(annotation)

        for stem in sorted(set(images_by_stem) | set(annotations_by_stem)):
            images = images_by_stem.get(stem, [])
            annotations = annotations_by_stem.get(stem, [])

            if len(images) > 1 or len(annotations) > 1:
                involved = sorted(
                    [image.asset_id for image in images]
                    + [annotation.asset_id for annotation in annotations]
                )
                anomalies.append(
                    AnomalyRecord(
                        code="ambiguous_pairing",
                        severity="error",
                        scope="subset",
                        source_subset=subset.name,
                        paths=involved,
                        reason=(
                            "more than one image or XML shares the same stem "
                            f"in subset {subset.name!r}; no pair was created"
                        ),
                        details={
                            "stem": stem,
                            "image_count": len(images),
                            "annotation_count": len(annotations),
                        },
                    )
                )
                for image in images:
                    image.status = ImageStatus.UNPAIRED
                    unpaired_images.append(image)
                for annotation in annotations:
                    annotation.status = AnnotationStatus.UNPAIRED
                    unpaired_annotations.append(annotation)
                continue

            if images and annotations:
                image = images[0]
                annotation = annotations[0]
                samples.append(
                    MatchedSample(
                        sample_id=f"{subset.name}/{stem}",
                        source_subset=subset.name,
                        image=image,
                        annotation=annotation,
                        state=SampleState.PAIRED,
                    )
                )
                continue

            if images:
                image = images[0]
                image.status = ImageStatus.UNPAIRED
                unpaired_images.append(image)
                anomalies.append(
                    AnomalyRecord(
                        code="missing_xml",
                        severity="error",
                        scope="image",
                        sample_id=None,
                        source_subset=subset.name,
                        paths=[image.asset_id],
                        reason=(
                            "no XML with the same stem in subset "
                            f"{subset.name!r}"
                        ),
                        details={
                            "stem": stem,
                            "expected_xml": (
                                f"{subset.relative_prefix}/annotations/{stem}.xml"
                            ),
                        },
                    )
                )
                continue

            annotation = annotations[0]
            annotation.status = AnnotationStatus.UNPAIRED
            unpaired_annotations.append(annotation)
            anomalies.append(
                AnomalyRecord(
                    code="missing_image",
                    severity="error",
                    scope="annotation",
                    sample_id=None,
                    source_subset=subset.name,
                    paths=[annotation.asset_id],
                    reason=(
                        "no image with the same stem in subset "
                        f"{subset.name!r}"
                    ),
                    details={
                        "stem": stem,
                        "expected_image_stem": (
                            f"{subset.relative_prefix}/images/{stem}"
                        ),
                    },
                )
            )

    samples.sort(key=lambda sample: sample.sample_id)
    anomalies.sort(key=lambda anomaly: (anomaly.code, tuple(anomaly.paths)))
    unpaired_images.sort(key=lambda image: image.asset_id)
    unpaired_annotations.sort(key=lambda annotation: annotation.asset_id)
    return PairingResult(
        samples=samples,
        anomalies=anomalies,
        unpaired_images=unpaired_images,
        unpaired_annotations=unpaired_annotations,
    )
