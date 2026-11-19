"""Command-line entry point for Feature 001 (T024).

The CLI parses ``detection prepare``, runs the source/output safety checks and
delegates to the conversion pipeline with the parsed ``seed``, ``ratios`` and
``on_anomaly`` values so the report config reflects the actual invocation.
Detailed errors go to stderr; every documented failure maps to a stable exit
code and structured results live in the JSON artifacts, not stdout.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .data.discovery import DiscoveryError
from .data.models import SPLIT_NAMES, Severity
from .data.pipeline import ConversionOptions, PipelineError, run_conversion

EXIT_SUCCESS = 0
EXIT_CONFIG = 2
EXIT_BLOCKING_DATA = 3
EXIT_OUTPUT_EXISTS = 4
EXIT_IO = 5

DEFAULT_OUTPUT = "data/processed/neu-det"
DEFAULT_SEED = 42
DEFAULT_RATIOS_TEXT = "0.75,0.15,0.10"
DEFAULT_ON_ANOMALY = "fail"
ON_ANOMALY_CHOICES = ("fail", "quarantine")
RATIO_TOLERANCE = 1e-9


class CliError(Exception):
    """Base class for errors that map to a documented CLI exit code."""

    exit_code = EXIT_CONFIG


class ConfigurationError(CliError):
    """Invalid usage, configuration, path or source structure (exit 2)."""

    exit_code = EXIT_CONFIG


class BlockingDataError(CliError):
    """Blocking data error, changed source or broken split invariant (exit 3)."""

    exit_code = EXIT_BLOCKING_DATA


class OutputExistsError(CliError):
    """Output exists without ``--overwrite`` (exit 4)."""

    exit_code = EXIT_OUTPUT_EXISTS


class IoError(CliError):
    """Unexpected I/O failure (exit 5)."""

    exit_code = EXIT_IO


@dataclass(frozen=True)
class PrepareConfig:
    source: Path
    output: Path
    seed: int
    ratios: tuple[float, float, float]
    on_anomaly: str
    overwrite: bool

    def ratios_map(self) -> dict[str, float]:
        return {
            split_name: ratio
            for split_name, ratio in zip(SPLIT_NAMES, self.ratios, strict=True)
        }


def parse_ratios(raw: str) -> tuple[float, float, float]:
    """Parse and validate a ``train,validation,test`` ratio triple."""
    parts = [part.strip() for part in str(raw).split(",")]
    if len(parts) != 3:
        raise ConfigurationError(
            "--ratios must contain exactly three comma-separated values: "
            "train,validation,test"
        )

    try:
        values = tuple(float(part) for part in parts)
    except ValueError as exc:
        raise ConfigurationError(
            "--ratios values must be finite numbers"
        ) from exc

    if len(values) != 3:
        raise ConfigurationError("--ratios must contain exactly three values")

    for value in values:
        if not math.isfinite(value):
            raise ConfigurationError("--ratios values must be finite numbers")
        if value <= 0:
            raise ConfigurationError("--ratios values must all be positive")

    if abs(sum(values) - 1.0) > RATIO_TOLERANCE:
        raise ConfigurationError(
            "--ratios values must sum to 1.0 within 1e-9"
        )
    return values  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detection",
        description=(
            "NEU-DET data preparation pipeline for YOLOv8 object detection"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare",
        help="convert a NEU-DET source tree into YOLO-format data",
        description=(
            "Discover, pair, validate and convert a NEU-DET source tree "
            "without modifying it."
        ),
    )
    prepare.add_argument(
        "--source",
        required=True,
        metavar="PATH",
        help="source dataset directory (may be outside the repository)",
    )
    prepare.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        metavar="PATH",
        help=f"output directory (default: {DEFAULT_OUTPUT})",
    )
    prepare.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        metavar="INT",
        help=f"split seed (default: {DEFAULT_SEED})",
    )
    prepare.add_argument(
        "--ratios",
        default=DEFAULT_RATIOS_TEXT,
        metavar="T,V,TE",
        help=(
            "train,validation,test ratios (default: "
            f"{DEFAULT_RATIOS_TEXT})"
        ),
    )
    prepare.add_argument(
        "--on-anomaly",
        choices=ON_ANOMALY_CHOICES,
        default=DEFAULT_ON_ANOMALY,
        metavar="{fail,quarantine}",
        help=f"error handling mode (default: {DEFAULT_ON_ANOMALY})",
    )
    prepare.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the contents of an existing output directory",
    )
    return parser


def parse_prepare_args(argv: Sequence[str] | None = None) -> PrepareConfig:
    """Parse ``detection prepare`` arguments and validate ratio values."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "prepare":
        raise ConfigurationError(f"unsupported command: {args.command!r}")

    source = Path(args.source).expanduser().resolve(strict=False)
    output = Path(args.output).expanduser().resolve(strict=False)
    ratios = parse_ratios(args.ratios)

    return PrepareConfig(
        source=source,
        output=output,
        seed=args.seed,
        ratios=ratios,
        on_anomaly=args.on_anomaly,
        overwrite=bool(args.overwrite),
    )


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


def validate_prepare_config(config: PrepareConfig) -> None:
    """Run all source/output safety checks before any write.

    Raises:
        ConfigurationError: invalid source or unsafe output path (exit 2).
        OutputExistsError: non-empty output without ``--overwrite`` (exit 4).
    """
    source = config.source.expanduser().resolve(strict=False)
    output = config.output.expanduser().resolve(strict=False)

    if not source.exists():
        raise ConfigurationError(f"source path does not exist: {source}")
    if not source.is_dir():
        raise ConfigurationError(f"source path is not a directory: {source}")
    if not os.access(source, os.R_OK | os.X_OK):
        raise ConfigurationError(f"source path is not readable: {source}")

    if (
        output == source
        or _is_relative_to(output, source)
        or _is_relative_to(source, output)
    ):
        raise ConfigurationError(
            "output must not be inside, equal to, or a parent of the source "
            f"directory (source={source}, output={output})"
        )

    if output.exists() or output.is_symlink():
        if not output.is_dir():
            if not config.overwrite:
                raise OutputExistsError(
                    f"output already exists: {output}; use --overwrite"
                )
            raise ConfigurationError(
                f"output path exists and is not a directory: {output}"
            )
        if any(output.iterdir()) and not config.overwrite:
            raise OutputExistsError(
                f"output directory is not empty: {output}; use --overwrite"
            )


def _print_anomalies(anomalies: Sequence[object]) -> None:
    """Print blocking anomaly details to stderr."""
    for anomaly in anomalies:
        severity = getattr(anomaly, "severity", None)
        if severity != Severity.ERROR:
            continue
        code = getattr(anomaly, "code", "error")
        reason = getattr(anomaly, "reason", "")
        paths = getattr(anomaly, "paths", [])
        location = f" [{', '.join(paths)}]" if paths else ""
        print(
            f"detection prepare: {code}: {reason}{location}",
            file=sys.stderr,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by the ``detection`` console script."""
    try:
        config = parse_prepare_args(argv)
        validate_prepare_config(config)
        result = run_conversion(
            ConversionOptions(
                source=config.source,
                output=config.output,
                overwrite=config.overwrite,
                on_anomaly=config.on_anomaly,
                seed=config.seed,
                ratios=config.ratios,
            )
        )
    except CliError as exc:
        print(f"detection prepare: {exc}", file=sys.stderr)
        return exc.exit_code
    except DiscoveryError as exc:
        print(f"detection prepare: {exc}", file=sys.stderr)
        return exc.exit_code
    except PipelineError as exc:
        _print_anomalies(exc.anomalies)
        print(f"detection prepare: {exc}", file=sys.stderr)
        return exc.exit_code
    except OSError as exc:
        print(f"detection prepare: I/O error: {exc}", file=sys.stderr)
        return EXIT_IO

    warnings = sum(
        1
        for anomaly in result.anomalies
        if anomaly.severity == Severity.WARNING
    )
    infos = sum(
        1 for anomaly in result.anomalies if anomaly.severity == Severity.INFO
    )
    print(
        "detection prepare: "
        f"wrote {result.samples_written} image(s) and {result.labels_written} "
        f"label(s) to {result.output}/images/{result.split} and "
        f"{result.output}/labels/{result.split}; "
        f"objects={result.objects_written} classes={result.present_classes} "
        f"warnings={warnings} info={infos}; source unchanged"
    )
    return EXIT_SUCCESS
