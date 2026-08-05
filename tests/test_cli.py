from __future__ import annotations

import importlib
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import src.cli as cli
from src.application.dto import PhaseResult, PipelineResult

cli_main = importlib.import_module("src.cli.main")


def _context(**services: object) -> SimpleNamespace:
    defaults = {
        "generation": Mock(),
        "inventory": Mock(),
        "profiling": Mock(),
        "classification": Mock(),
        "masking": Mock(),
        "validation": Mock(),
        "status": Mock(),
        "drift": Mock(),
    }
    defaults.update(services)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--help"],
        ["generate", "--help"],
        ["mask", "--help"],
        ["validate", "--help"],
        ["drift", "--help"],
        ["all", "--help"],
    ],
)
def test_help_is_available(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_module_is_executable_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert "{generate,inventory,profile,classify,status,drift,mask,validate,all}" in result.stdout


def test_drift_modes_are_read_only_unless_write_is_explicit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    drift = Mock()
    drift.report.return_value = SimpleNamespace(has_drift=False, items=(), count=lambda _kind: 0)
    drift.write_baseline.return_value = {
        "schemas": 3,
        "tables": 20,
        "columns": 109,
        "constraints": 57,
        "logical_relationships": 2,
    }
    monkeypatch.setattr(cli_main, "build_application", lambda: _context(drift=drift))
    assert cli.main(["drift"]) == 0
    assert cli.main(["drift", "--check"]) == 0
    drift.write_baseline.assert_not_called()
    assert cli.main(["drift", "--write-baseline"]) == 0
    drift.write_baseline.assert_called_once_with()
    assert "columns=109" in capsys.readouterr().out


def test_generate_reports_only_aggregate_counts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    generation = Mock()
    generation.run.return_value = {"seed": 20260804, "tables": 2, "rows": 5}
    monkeypatch.setattr(cli_main, "build_application", lambda: _context(generation=generation))
    assert cli.main(["generate", "--seed", "20260804"]) == 0
    generation.run.assert_called_once_with(20260804)
    output = capsys.readouterr().out
    assert "seed=20260804" in output and "tables=2" in output and "rows=5" in output


def test_inventory_profile_and_classify_use_application_services(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    inventory, profiling, classification = Mock(), Mock(), Mock()
    inventory.run.return_value = {
        "schemas": 3,
        "tables": 20,
        "columns": 109,
        "primary_keys": 20,
        "foreign_keys": 12,
        "unique_constraints": 10,
        "check_constraints": 15,
    }
    profiling.run.return_value = {
        "column_count": 109,
        "pattern_evidence_column_count": 71,
        "suspicious_column_count": 30,
        "redacted_sample_count": 220,
    }
    classification.run.return_value = {
        "columns": 109,
        "categories": {"Non-PII": 50, "PII": 59},
        "statuses": {"confirmed": 109},
    }
    context = _context(inventory=inventory, profiling=profiling, classification=classification)
    monkeypatch.setattr(cli_main, "build_application", lambda: context)
    assert cli.main(["inventory"]) == cli.main(["profile"]) == cli.main(["classify"]) == 0
    inventory.run.assert_called_once_with()
    profiling.run.assert_called_once_with()
    classification.run.assert_called_once_with()
    output = capsys.readouterr().out
    assert "columns=109" in output and "privacy_patterns=30" in output and "Classification generated" in output


def test_mask_modes_and_validate_report_aggregate_results(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    masking, validation = Mock(), Mock()
    masking.run.side_effect = [
        {"tables": 20, "batch_sets": 15, "ambiguous_strategy": "redact_detected_patterns"},
        {"tables": 20, "rows": 2063, "validations": 9},
    ]
    validation.run.return_value = {
        "tables": 20,
        "rows": 2063,
        "validations": 9,
        "checksum": "b" * 64,
        "idempotent": None,
    }
    monkeypatch.setattr(cli_main, "build_application", lambda: _context(masking=masking, validation=validation))
    assert cli.main(["mask", "--dry-run"]) == 0
    assert cli.main(["mask", "--validate-only"]) == 0
    assert cli.main(["validate"]) == 0
    assert masking.run.call_args_list[0].kwargs == {"dry_run": True, "validate_only": False}
    assert masking.run.call_args_list[1].kwargs == {"dry_run": False, "validate_only": True}
    validation.run.assert_called_once_with(check_idempotence=False)
    output = capsys.readouterr().out
    assert "writes=0" in output and "Masked state valid" in output and "Validation successful" in output


def test_status_has_stable_readable_aggregate_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    status = Mock()
    status.run.return_value = {
        "postgresql": "reachable",
        "source_schemas": 3,
        "source_tables": 20,
        "source_rows": 2063,
        "masked_tables": 20,
        "masked_rows": 2063,
        "registry": "available",
        "registry_columns": 109,
        "manifest": "available",
        "last_validation": "available",
        "branch": "refactor/modular-architecture",
        "status": "ready",
    }
    monkeypatch.setattr(cli_main, "build_application", lambda: _context(status=status))
    assert cli.main(["status"]) == 0
    status.run.assert_called_once_with()
    output = capsys.readouterr().out
    assert "source_tables=20" in output and "masked_rows=2063" in output and "status=ready" in output


def test_all_stops_at_first_error_and_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pipeline = Mock()
    pipeline.run.side_effect = RuntimeError("controlled failure")
    context = _context()
    monkeypatch.setattr(cli_main, "build_application", lambda: context)
    monkeypatch.setattr(cli_main, "build_pipeline", lambda received: pipeline)
    assert cli.main(["all"]) == 1
    pipeline.run.assert_called_once_with(seed=20260804, check_idempotence=False)
    captured = capsys.readouterr()
    assert "Unexpected RuntimeError." in captured.err
    assert "controlled failure" not in captured.err


def test_all_uses_pipeline_and_prints_concrete_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pipeline = Mock()
    pipeline.run.return_value = PipelineResult(
        phases=tuple(
            PhaseResult(name, 0.001, {})
            for name in ("generate", "inventory", "profile", "classify", "mask", "validate")
        ),
        rows=2063,
        classified_columns=109,
        masked_tables=20,
        validations=9,
        checksum="c" * 64,
    )
    context = _context()
    monkeypatch.setattr(cli_main, "build_application", lambda: context)
    monkeypatch.setattr(cli_main, "build_pipeline", lambda received: pipeline)
    assert cli.main(["all", "--check-idempotence"]) == 0
    pipeline.run.assert_called_once_with(seed=20260804, check_idempotence=True)
    output = capsys.readouterr().out
    assert "rows=2063" in output and "classified_columns=109" in output and "masked_tables=20" in output


def test_normal_failures_hide_secret_password_and_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret, password = "synthetic-test-secret-value", "synthetic-test-password-value"
    monkeypatch.setenv("MASKING_SECRET", secret)
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    generation = Mock()
    generation.run.side_effect = RuntimeError(f"bad {secret} {password}")
    monkeypatch.setattr(cli_main, "build_application", lambda: _context(generation=generation))
    assert cli.main(["generate"]) == 1
    captured = capsys.readouterr()
    assert secret not in captured.err and password not in captured.err
    assert "Traceback" not in captured.err
    assert "Unexpected RuntimeError." in captured.err


def test_output_does_not_include_environment_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    generation = Mock()
    generation.run.return_value = {"seed": 20260804, "tables": 1, "rows": 1}
    monkeypatch.setattr(cli_main, "build_application", lambda: _context(generation=generation))
    assert cli.main(["generate"]) == 0
    output = capsys.readouterr().out
    assert os.environ["MASKING_SECRET"] not in output
    assert os.environ["POSTGRES_PASSWORD"] not in output
    assert "postgresql://" not in output
