from __future__ import annotations

import json
import os
import secrets
import subprocess
from pathlib import Path

import pytest
import yaml

import src.apply_masking as pipeline
from src.apply_masking import (
    DependencyCycleError,
    MaskingPipelineError,
    apply_masking,
    calculate_load_order,
    dry_run_plan,
    validate_only,
)
from src.masking import ReviewRequiredError


@pytest.fixture(scope="module", autouse=True)
def isolated_synthetic_secret() -> None:
    original_secret = os.environ["MASKING_SECRET"]
    os.environ["MASKING_SECRET"] = secrets.token_urlsafe(48)
    try:
        yield
    finally:
        os.environ["MASKING_SECRET"] = original_secret
        apply_masking()


def test_dry_run_is_complete_and_does_not_write() -> None:
    before = validate_only()["table_checksums"]
    plan = dry_run_plan()
    after = validate_only()["table_checksums"]
    assert plan["tables"] == 20
    assert len(plan["load_order"]) == 20
    assert plan["ambiguous_strategy"] == "redact_detected_patterns"
    assert plan["writes_performed"] is False
    assert before == after


def test_ambiguous_column_blocks_without_confirmed_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = yaml.safe_load(pipeline.EXECUTION_CONFIG_PATH.read_text(encoding="utf-8"))
    config["ambiguous_columns"]["billing.pagamenti.riferimento_bancario"] = {
        "strategy": "block"
    }
    blocked_config = tmp_path / "masking_execution.yml"
    blocked_config.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(pipeline, "EXECUTION_CONFIG_PATH", blocked_config)
    with pytest.raises(ReviewRequiredError, match="blocked"):
        dry_run_plan()


def test_dependency_cycles_fail_before_loading() -> None:
    foreign_keys = [
        {"source_schema": "crm", "source_table": "a", "target_schema": "crm", "target_table": "b"},
        {"source_schema": "crm", "source_table": "b", "target_schema": "crm", "target_table": "a"},
    ]
    with pytest.raises(DependencyCycleError, match="cycle"):
        calculate_load_order(["crm.a", "crm.b"], foreign_keys)


def test_injected_failure_rolls_back_the_whole_masked_load(tmp_path: Path) -> None:
    baseline = apply_masking(manifest_path=tmp_path / "baseline.json")
    with pytest.raises(MaskingPipelineError, match="rollback"):
        apply_masking(manifest_path=tmp_path / "must-not-exist.json", fail_after_tables=3)
    assert validate_only()["table_checksums"] == baseline["table_checksums"]
    assert not (tmp_path / "must-not-exist.json").exists()


def test_same_secret_is_idempotent_and_manifest_has_no_sensitive_material(
    tmp_path: Path,
) -> None:
    first_path, second_path = tmp_path / "first.json", tmp_path / "second.json"
    first = apply_masking(manifest_path=first_path)
    second = apply_masking(manifest_path=second_path)
    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()
    serialized = first_path.read_text(encoding="utf-8")
    assert os.environ["MASKING_SECRET"] not in serialized
    assert "mapping" not in serialized.casefold()
    assert first["tables_processed"] == 20
    assert sum(first["source_rows_by_table"].values()) == 2063
    assert first["source_rows_by_table"] == first["masked_rows_by_table"]
    assert len(first["table_checksums"]) == 20


def test_different_secret_changes_outputs_and_source_remains_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_secret = os.environ["MASKING_SECRET"]
    with pipeline.get_connection() as connection, connection.cursor() as cursor:
        context = pipeline.validate_preconditions(cursor)
        columns, _, rows = pipeline._fetch_all_source_data(cursor, context["source_tables"])
        source_before = pipeline._source_checksums(context, columns, rows)
    try:
        monkeypatch.setenv("MASKING_SECRET", secrets.token_urlsafe(48))
        first = apply_masking(manifest_path=tmp_path / "secret-a.json")
        monkeypatch.setenv("MASKING_SECRET", secrets.token_urlsafe(48))
        second = apply_masking(manifest_path=tmp_path / "secret-b.json")
        assert first["global_checksum"] != second["global_checksum"]
        assert first["table_checksums"] != second["table_checksums"]
    finally:
        monkeypatch.setenv("MASKING_SECRET", original_secret)
        apply_masking()
    with pipeline.get_connection() as connection, connection.cursor() as cursor:
        context = pipeline.validate_preconditions(cursor)
        columns, _, rows = pipeline._fetch_all_source_data(cursor, context["source_tables"])
        assert pipeline._source_checksums(context, columns, rows) == source_before


def test_committed_manifest_is_valid_json_and_self_consistent() -> None:
    manifest = apply_masking()
    persisted = json.loads(pipeline.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert persisted == manifest
    assert persisted["ambiguous_column_strategy"] == {
        "column": "billing.pagamenti.riferimento_bancario",
        "residual_risk_documented": True,
        "review_status": "confirmed",
        "strategy": "redact_detected_patterns",
    }


def test_commands_are_executable_from_repository_root() -> None:
    for option, expected in (
        ("--dry-run", "Dry run valid: 20 tables"),
        ("--validate-only", "Masked database valid: 20 tables, 2063 rows"),
    ):
        result = subprocess.run(
            [".venv/bin/python", "-m", "src.apply_masking", option],
            capture_output=True, text=True, check=True, timeout=30,
        )
        assert expected in result.stdout
