from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.config.loader import RepositoryConfigLoader, load_yaml_path
from src.infrastructure.config.settings import DatabaseSettings
from src.infrastructure.security.secret_provider import EnvironmentSecretProvider
from src.infrastructure.serialization.json_manifest_repository import JsonManifestRepository
from src.shared.errors import ConfigurationError, MaskingSecretError


def test_repository_config_loader_is_the_single_yaml_entry_point(tmp_path: Path) -> None:
    (tmp_path / "sample.yml").write_text("version: 1\nitems: [a, b]\n", encoding="utf-8")
    assert RepositoryConfigLoader(tmp_path).load("sample") == {"version": 1, "items": ["a", "b"]}
    invalid = tmp_path / "invalid.yml"
    invalid.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="mapping"):
        load_yaml_path(invalid)


def test_database_settings_validate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "POSTGRES_DB": "synthetic_db",
        "POSTGRES_USER": "synthetic_user",
        "POSTGRES_PASSWORD": "synthetic_password",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    assert DatabaseSettings.from_environment().port == 5432
    monkeypatch.setenv("POSTGRES_PORT", "invalid")
    with pytest.raises(ConfigurationError, match="integer"):
        DatabaseSettings.from_environment()


def test_environment_secret_provider_does_not_expose_missing_material(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MASKING_SECRET", raising=False)
    with pytest.raises(MaskingSecretError, match="required"):
        EnvironmentSecretProvider().masking_secret()


def test_json_manifest_repository_round_trip(tmp_path: Path) -> None:
    repository = JsonManifestRepository(tmp_path / "manifest.json")
    document = {"format_version": 1, "final_status": "success", "global_checksum": "a" * 64}
    repository.save(document)
    assert repository.load() == document
