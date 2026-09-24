"""Config tests: .env loading and NCBI credential plumbing."""

import os

from synlethality import config


def test_dotenv_loader_sets_missing_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n\nDOTENV_TEST_KEY=from-file\nDOTENV_TEST_QUOTED=\"quoted value\"\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DOTENV_TEST_KEY", raising=False)
    monkeypatch.delenv("DOTENV_TEST_QUOTED", raising=False)
    config._load_dotenv(str(env_file))
    assert os.environ["DOTENV_TEST_KEY"] == "from-file"
    assert os.environ["DOTENV_TEST_QUOTED"] == "quoted value"


def test_dotenv_loader_never_overrides_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DOTENV_TEST_PRIORITY=file\n", encoding="utf-8")
    monkeypatch.setenv("DOTENV_TEST_PRIORITY", "env")
    config._load_dotenv(str(env_file))
    assert os.environ["DOTENV_TEST_PRIORITY"] == "env"


def test_dotenv_loader_tolerates_missing_file(tmp_path):
    config._load_dotenv(str(tmp_path / "does-not-exist.env"))  # no exception


def test_ncbi_key_plumbed_from_dotenv():
    """The project's .env (gitignored) should make the NCBI key available."""
    assert config.NCBI_API_KEY, (
        "NCBI_API_KEY not set — add it to Cancer Resource/.env or the environment"
    )
    assert isinstance(config.NCBI_EMAIL, str)  # may be empty; key is the essential one
