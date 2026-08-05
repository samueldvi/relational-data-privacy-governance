from pathlib import Path

import yaml


def test_benchmark_profiles_cover_required_cumulative_volumes() -> None:
    config = yaml.safe_load(Path("benchmarks/benchmark_config.yml").read_text(encoding="utf-8"))
    assert config["profiles"]["baseline"]["approximate_rows"] == 2063
    assert 20_000 <= config["profiles"]["cumulative_20k"]["approximate_rows"] < 25_000
    assert 100_000 <= config["profiles"]["cumulative_100k"]["approximate_rows"] < 110_000


def test_benchmark_workflow_is_manual_only() -> None:
    workflow = yaml.load(Path(".github/workflows/benchmark.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert "push" not in workflow["on"] and "pull_request" not in workflow["on"]
    assert workflow["permissions"] == {"contents": "read"}


def test_benchmark_documentation_rejects_enterprise_claims() -> None:
    text = Path("benchmarks/README.md").read_text(encoding="utf-8")
    assert "circa 20k e 100k" in text
    assert "Non usare i risultati per dichiarazioni di" in text
