import pytest
from starlette.requests import Request

from src.api.rate_limit import request_limiter
from src.services import usage_service


@pytest.fixture(autouse=True)
def _enable_rate_limiting(monkeypatch):
    monkeypatch.setattr(request_limiter, "enabled", True)
    request_limiter.reset()
    yield
    request_limiter.reset()


@pytest.mark.asyncio
async def test_register_is_rate_limited_per_ip(client):
    for index in range(5):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"rate-register-{index}@example.com",
                "password": "password123",
                "display_name": "Rate Test",
            },
        )
        assert response.status_code == 201
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rate-register-overflow@example.com",
            "password": "password123",
            "display_name": "Rate Test",
        },
    )
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


@pytest.mark.asyncio
async def test_chat_is_rate_limited_per_user(client, auth_headers, monkeypatch):
    async def _over_budget():
        return True

    monkeypatch.setattr(usage_service, "is_over_budget", _over_budget)
    for _ in range(15):
        response = await client.post("/api/v1/chat", json={"message": "hello"}, headers=auth_headers)
        assert response.status_code == 200
    response = await client.post("/api/v1/chat", json={"message": "hello"}, headers=auth_headers)
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_health_is_exempt(client):
    for _ in range(70):
        assert (await client.get("/health")).status_code == 200


def test_admin_auth_uses_auth_rate_limit_tier():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/admin/login",
            "query_string": b"",
            "headers": [],
            "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )
    assert request_limiter._tier(request)[0] == "auth"


def test_production_ip_bucket_uses_validated_cloudflare_client_ip(monkeypatch):
    monkeypatch.setattr("src.api.rate_limit.get_settings", lambda: type("S", (), {"app_env": "production"})())
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "query_string": b"",
            "headers": [(b"cf-connecting-ip", b"203.0.113.8"), (b"x-forwarded-for", b"1.2.3.4")],
            "server": ("test", 80),
            "client": ("10.0.0.1", 1234),
            "scheme": "https",
        }
    )
    assert request_limiter._key(request) == "ip:203.0.113.8"
