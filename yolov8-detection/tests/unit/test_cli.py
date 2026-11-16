"""Unit tests for CLI parsing and pre-flight safety checks (T008)."""

from __future__ import annotations

from pathlib import Path

import pytest

from detection.cli import (
    EXIT_BLOCKING_DATA,
    EXIT_CONFIG,
    EXIT_IO,
    EXIT_OUTPUT_EXISTS,
    EXIT_SUCCESS,
    ConfigurationError,
    OutputExistsError,
    PrepareConfig,
    main,
    parse_prepare_args,
    parse_ratios,
    validate_prepare_config,
)


def _config_for(source: Path, **overrides: object) -> PrepareConfig:
    values: dict[str, object] = {
        "source": source,
        "output": source.parent / "processed",
        "seed": 42,
        "ratios": (0.75, 0.15, 0.10),
        "on_anomaly": "fail",
        "overwrite": False,
    }
    values.update(overrides)
    return PrepareConfig(**values)  # type: ignore[arg-type]


def test_exit_codes_match_cli_contract() -> None:
    assert EXIT_SUCCESS == 0
    assert EXIT_CONFIG == 2
    assert EXIT_BLOCKING_DATA == 3
    assert EXIT_OUTPUT_EXISTS == 4
    assert EXIT_IO == 5


def test_parser_defaults(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()

    config = parse_prepare_args(["prepare", "--source", str(source)])

    assert config.source == source.resolve()
    assert config.output == Path("data/processed/neu-det").resolve()
    assert config.seed == 42
    assert config.ratios == (0.75, 0.15, 0.10)
    assert config.on_anomaly == "fail"
    assert config.overwrite is False


def test_parser_accepts_all_options(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "processed"

    config = parse_prepare_args(
        [
            "prepare",
            "--source",
            str(source),
            "--output",
            str(output),
            "--seed",
            "7",
            "--ratios",
            "0.6,0.2,0.2",
            "--on-anomaly",
            "quarantine",
            "--overwrite",
        ]
    )

    assert config.source == source.resolve()
    assert config.output == output.resolve()
    assert config.seed == 7
    assert config.ratios == (0.6, 0.2, 0.2)
    assert config.on_anomaly == "quarantine"
    assert config.overwrite is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0.75,0.15,0.10", (0.75, 0.15, 0.10)),
        ("0.8,0.1,0.1", (0.8, 0.1, 0.1)),
        (" 0.6 , 0.2 , 0.2 ", (0.6, 0.2, 0.2)),
    ],
)
def test_parse_ratios_accepts_valid_triples(raw: str, expected: tuple[float, ...]) -> None:
    assert parse_ratios(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "0.75,0.15",
        "0.75,0.15,0.10,0",
        "0.75;0.15;0.10",
        "0.75,0.15,abc",
        "nan,0.5,0.5",
        "inf,0.5,0.5",
        "0.5,0.5,0.0",
        "0.5,0.5,-0.1",
        "0.5,0.5,0.1",
    ],
)
def test_parse_ratios_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ConfigurationError):
        parse_ratios(raw)


def test_parser_rejects_missing_source() -> None:
    with pytest.raises(SystemExit) as excinfo:
        parse_prepare_args(["prepare"])
    assert excinfo.value.code == 2


def test_parser_rejects_invalid_on_anomaly(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(SystemExit) as excinfo:
        parse_prepare_args(["prepare", "--source", str(source), "--on-anomaly", "skip"])
    assert excinfo.value.code == 2


def test_missing_source_is_configuration_error(tmp_path: Path) -> None:
    config = _config_for(tmp_path / "missing")
    with pytest.raises(ConfigurationError, match="does not exist"):
        validate_prepare_config(config)


def test_source_must_be_a_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_text("not a directory", encoding="utf-8")
    config = _config_for(source)
    with pytest.raises(ConfigurationError, match="not a directory"):
        validate_prepare_config(config)


def test_output_equal_to_source_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    config = _config_for(source, output=source)
    with pytest.raises(ConfigurationError, match="inside, equal to, or a parent"):
        validate_prepare_config(config)


def test_output_inside_source_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    config = _config_for(source, output=source / "processed")
    with pytest.raises(ConfigurationError, match="inside, equal to, or a parent"):
        validate_prepare_config(config)


def test_output_parent_of_source_is_rejected(tmp_path: Path) -> None:
    parent = tmp_path / "sandbox"
    source = parent / "dataset"
    source.mkdir(parents=True)
    config = _config_for(source, output=parent)
    with pytest.raises(ConfigurationError, match="inside, equal to, or a parent"):
        validate_prepare_config(config)


def test_existing_non_empty_output_requires_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "processed"
    output.mkdir()
    (output / "old.txt").write_text("old", encoding="utf-8")

    with pytest.raises(OutputExistsError, match="--overwrite"):
        validate_prepare_config(_config_for(source, output=output))

    validate_prepare_config(_config_for(source, output=output, overwrite=True))


def test_existing_empty_output_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "processed"
    output.mkdir()

    validate_prepare_config(_config_for(source, output=output))


def test_main_returns_contract_exit_codes(tmp_path: Path, build_source_tree) -> None:
    source = build_source_tree(
        tmp_path / "source",
        {"train": [{"stem": "a"}]},
    )
    output = tmp_path / "processed"

    assert (
        main(["prepare", "--source", str(source), "--output", str(output)])
        == EXIT_SUCCESS
    )

    assert (
        main(
            [
                "prepare",
                "--source",
                str(source),
                "--output",
                str(source / "processed"),
            ]
        )
        == EXIT_CONFIG
    )

    assert (
        main(
            [
                "prepare",
                "--source",
                str(source),
                "--output",
                str(output),
                "--ratios",
                "0.5,0.5,0.1",
            ]
        )
        == EXIT_CONFIG
    )

    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "old.txt").write_text("old", encoding="utf-8")
    assert (
        main(
            [
                "prepare",
                "--source",
                str(source),
                "--output",
                str(existing),
            ]
        )
        == EXIT_OUTPUT_EXISTS
    )

    assert main(["prepare", "--source", str(tmp_path / "missing")]) == EXIT_CONFIG
