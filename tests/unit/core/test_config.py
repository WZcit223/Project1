"""Tests for industrial_ai.core.config."""

import os
from pathlib import Path

import pytest

from industrial_ai.core.config import Environment, LogLevel, Settings, load_settings
from industrial_ai.core.errors import ConfigurationError

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test without inherited IAI_* variables or a developer's .env file."""
    for name in list(os.environ):
        if name.startswith("IAI_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def test_defaults() -> None:
    settings = load_settings()
    assert settings.env is Environment.DEV
    assert settings.log_level is LogLevel.INFO
    assert settings.data_dir == Path("./data")
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    # the documented demo configuration uses the committed reference subset by default
    assert settings.reference_dirs == {"m5_subset": Path("./data/reference/m5_subset")}


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IAI_ENV", "test")
    monkeypatch.setenv("IAI_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("IAI_API_PORT", "9001")
    settings = load_settings()
    assert settings.env is Environment.TEST
    assert settings.log_level is LogLevel.DEBUG
    assert settings.api_port == 9001


def test_dotenv_file_is_read(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("IAI_ENV=demo\n", encoding="utf-8")
    assert load_settings().env is Environment.DEMO


def test_keyword_overrides_take_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IAI_ENV", "test")
    assert load_settings(env="demo").env is Environment.DEMO


@pytest.mark.parametrize(("name", "value"), [("IAI_ENV", "prod"), ("IAI_API_PORT", "0")])
def test_invalid_value_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError, match="Invalid configuration"):
        load_settings()


def test_env_example_documents_every_setting() -> None:
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    documented = {line.split("=", 1)[0] for line in lines if line and not line.startswith("#")}
    expected = {f"IAI_{name.upper()}" for name in Settings.model_fields}
    assert documented == expected
