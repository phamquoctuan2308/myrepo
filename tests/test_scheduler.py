from src.services.scheduler import _sync_jobstore_url


def test_sync_jobstore_url_converts_plain_postgres_url():
    assert (
        _sync_jobstore_url("postgresql://user:password@localhost/orbit")
        == "postgresql+psycopg://user:password@localhost/orbit"
    )


def test_sync_jobstore_url_converts_asyncpg_url():
    assert (
        _sync_jobstore_url("postgresql+asyncpg://user:password@localhost/orbit")
        == "postgresql+psycopg://user:password@localhost/orbit"
    )


def test_sync_jobstore_url_preserves_psycopg_url():
    url = "postgresql+psycopg://user:password@localhost/orbit"
    assert _sync_jobstore_url(url) == url
