import pytest
from pydantic import ValidationError

from app.core.config import Settings

URL = "mysql+pymysql://u:p@127.0.0.1:3306/db"


def make(**kwargs) -> Settings:
    return Settings(_env_file=None, database_url=URL, **kwargs)


def test_defaults():
    s = make()
    assert s.barista_token_ttl_hours == 12
    assert s.migrate_on_start is False
    assert s.seed_on_start is False
    assert s.serve_media is False
    assert s.log_level == "INFO"
    assert s.media_dir.name == "media"


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("INFO", "INFO"),
        ("info", "INFO"),
        ("Debug", "DEBUG"),
        (" warning ", "WARNING"),
        ("ErRoR", "ERROR"),
    ],
)
def test_log_level_is_case_insensitive_and_normalized(raw, expected):
    assert make(log_level=raw).log_level == expected


def test_log_level_from_environment_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("LOG_LEVEL", "info")
    assert Settings(_env_file=None).log_level == "INFO"


def test_unknown_log_level_is_rejected():
    with pytest.raises(ValidationError):
        make(log_level="verbose")


def test_token_ttl_bounds():
    with pytest.raises(ValidationError):
        make(barista_token_ttl_hours=0)


def test_short_token_secret_is_rejected_when_password_set():
    with pytest.raises(ValidationError):
        make(barista_password="pw", barista_token_secret="short")
    ok = make(barista_password="pw", barista_token_secret="x" * 32)
    assert ok.barista_password.get_secret_value() == "pw"


def test_bool_flags_parse_from_strings():
    s = make(migrate_on_start="true", seed_on_start="1", serve_media="false")
    assert (s.migrate_on_start, s.seed_on_start, s.serve_media) == (True, True, False)


def test_empty_values_fall_back_to_defaults(monkeypatch):
    for key in ("MIGRATE_ON_START", "BARISTA_TOKEN_TTL_HOURS", "LOG_LEVEL", "MEDIA_DIR"):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("DATABASE_URL", URL)
    s = Settings(_env_file=None)
    assert s.migrate_on_start is False
    assert s.barista_token_ttl_hours == 12
    assert s.log_level == "INFO"
    assert s.media_dir.name == "media"
