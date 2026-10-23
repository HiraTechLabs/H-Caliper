import pytest

from caliper.adapters.postgres.connection import database_url_from_environment
from caliper.domain.project import ProjectNameRequired, normalize_project_name


def test_project_name_is_trimmed():
    assert normalize_project_name("  Caliper ") == "Caliper"


@pytest.mark.parametrize("name", ["", "   ", "x" * 121])
def test_invalid_project_name_is_rejected(name: str):
    with pytest.raises(ProjectNameRequired):
        normalize_project_name(name)


def test_database_url_encodes_password_characters(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CALIPER_DATABASE_URL", raising=False)
    monkeypatch.setenv("CALIPER_DB_USER", "caliper")
    monkeypatch.setenv("CALIPER_DB_PASSWORD", "p@ss:/#word")
    monkeypatch.setenv("CALIPER_DB_HOST", "localhost")
    monkeypatch.setenv("CALIPER_DB_NAME", "caliper_test")

    url = database_url_from_environment()

    assert url.password == "p@ss:/#word"
    assert "%40" in url.render_as_string(hide_password=False)
