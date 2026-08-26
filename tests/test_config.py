import pytest
from pydantic import ValidationError

from src.config import Settings


def _production_settings(**overrides):
    values = {
        "app_env": "production",
        "secret_key": "x" * 32,
        "database_url": "postgresql://orbit:secret@db/orbit",
        "cors_origins": "https://app.example.com",
        "cors_origin_regex": "",
        "llm_provider": "google",
        "google_api_key": "test-api-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_settings_are_accepted():
    settings = _production_settings()
    assert settings.app_env == "production"


@pytest.mark.parametrize(
    "override",
    [
        {"secret_key": "too-short"},
        {"database_url": "sqlite:///./data/app.db"},
        {"cors_origins": "*"},
        {"google_api_key": ""},
    ],
)
def test_unsafe_production_settings_are_rejected(override):
    with pytest.raises(ValidationError):
        _production_settings(**override)
