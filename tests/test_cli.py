from __future__ import annotations

import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

import src.cli as cli


@pytest.mark.parametrize(
    "arguments",
    [["--help"], ["generate", "--help"], ["mask", "--help"], ["validate", "--help"], ["all", "--help"]],
)
def test_help_is_available(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_module_is_executable_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert "{generate,inventory,profile,classify,status,mask,validate,all}" in result.stdout


def test_generate_reports_only_aggregate_counts(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "load_dataset", lambda seed: {"crm.a": 2, "hr.b": 3})
    assert cli.main(["generate", "--seed", "20260804"]) == 0
    output = capsys.readouterr().out
    assert "seed=20260804" in output and "tables=2" in output and "rows=5" in output


def test_inventory_profile_and_classify_delegate_to_existing_modules(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "generate_inventory", lambda: {
        "schemas": 3, "tables": 20, "columns": 109, "primary_keys": 20,
        "foreign_keys": 12, "unique_constraints": 10, "check_constraints": 15,
    })
    monkeypatch.setattr(cli, "generate_profiling", lambda: {"metadata": {
        "column_count": 109, "pattern_evidence_column_count": 71,
        "suspicious_column_count": 30, "redacted_sample_count": 220,
    }})
    records = [{"pii_category": "Non-PII", "masking_rule": "preserve_value", "review_status": "proposed"} for _ in range(109)]
    monkeypatch.setattr(cli, "generate_classification", lambda: records)
    assert cli.main(["inventory"]) == cli.main(["profile"]) == cli.main(["classify"]) == 0
    output = capsys.readouterr().out
    assert "columns=109" in output and "privacy_patterns=30" in output and "Classification generated" in output


def test_mask_modes_and_validate_report_aggregate_results(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "dry_run_plan", lambda: {
        "tables": 20, "batch_sets": 15, "ambiguous_strategy": "redact_detected_patterns",
        "writes_performed": False,
    })
    validation = {
        "masked_counts": {"crm.a": 2}, "table_checksums": {"masked_crm.a": "a" * 64},
        "validations": ["rows"],
    }
    monkeypatch.setattr(cli, "validate_only", lambda: validation)
    monkeypatch.setattr(cli, "_read_manifest", lambda: {
        "table_checksums": validation["table_checksums"], "global_checksum": "b" * 64,
        "final_status": "success",
    })
    assert cli.main(["mask", "--dry-run"]) == 0
    assert cli.main(["mask", "--validate-only"]) == 0
    assert cli.main(["validate"]) == 0
    output = capsys.readouterr().out
    assert "writes=0" in output and "Masked state valid" in output and "Validation successful" in output


def test_status_has_stable_readable_aggregate_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return None
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def cursor(self): return Cursor()
    monkeypatch.setattr(cli, "get_connection", lambda: Connection())
    monkeypatch.setattr(cli, "_count_tables_and_rows", lambda cursor, schemas: (20, 2063))
    monkeypatch.setattr(cli, "_git_branch", lambda: "feature/cli-ci-documentation")
    monkeypatch.setattr(cli, "_read_manifest", lambda: {"final_status": "success", "validations": ["rows"]})
    registry_path, manifest_path = tmp_path / "registry.yml", tmp_path / "manifest.json"
    registry_path.write_text("columns:\n" + "  - {}\n" * 109, encoding="utf-8")
    manifest_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(cli, "MANIFEST_PATH", manifest_path)
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "source_tables=20" in output and "masked_rows=2063" in output and "status=ready" in output


def test_all_stops_at_first_error_and_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    called = []
    def fail(_: Namespace):
        called.append("generate")
        raise RuntimeError("controlled failure")
    monkeypatch.setattr(cli, "command_generate", fail)
    monkeypatch.setattr(cli, "command_inventory", lambda args: called.append("inventory"))
    assert cli.main(["all"]) == 1
    assert called == ["generate"]
    assert "controlled failure" in capsys.readouterr().err


def test_all_runs_in_order_and_prints_concrete_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    order = []
    monkeypatch.setattr(cli, "command_generate", lambda args: order.append("generate") or {"rows": 2})
    monkeypatch.setattr(cli, "command_inventory", lambda args: order.append("inventory") or {})
    monkeypatch.setattr(cli, "command_profile", lambda args: order.append("profile") or {})
    monkeypatch.setattr(cli, "command_classify", lambda args: order.append("classify") or {"columns": 109})
    monkeypatch.setattr(cli, "command_mask", lambda args: order.append("mask") or {
        "masked_rows_by_table": {"crm.a": 2}, "tables_processed": 20,
        "validations": ["rows"], "global_checksum": "c" * 64,
    })
    monkeypatch.setattr(cli, "command_validate", lambda args: order.append("validate") or {})
    assert cli.main(["all"]) == 0
    assert order == ["generate", "inventory", "profile", "classify", "mask", "validate"]
    output = capsys.readouterr().out
    assert "rows=2" in output and "classified_columns=109" in output and "masked_tables=20" in output


def test_normal_failures_hide_secret_password_and_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret, password = "synthetic-test-secret-value", "synthetic-test-password-value"
    monkeypatch.setenv("MASKING_SECRET", secret)
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    monkeypatch.setattr(cli, "load_dataset", lambda seed: (_ for _ in ()).throw(RuntimeError(f"bad {secret} {password}")))
    assert cli.main(["generate"]) == 1
    captured = capsys.readouterr()
    assert secret not in captured.err and password not in captured.err
    assert "Traceback" not in captured.err and "[REDACTED]" in captured.err


def test_output_does_not_include_environment_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "load_dataset", lambda seed: {"crm.a": 1})
    assert cli.main(["generate"]) == 0
    output = capsys.readouterr().out
    assert os.environ["MASKING_SECRET"] not in output
    assert os.environ["POSTGRES_PASSWORD"] not in output
    assert "postgresql://" not in output
