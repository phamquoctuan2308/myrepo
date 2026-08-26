import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123", "display_name": "New User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" not in body
    assert body["email"] == "new@example.com"
    assert body["display_name"] == "New User"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123", "display_name": "Dup"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client):
    payload = {"email": "login@example.com", "password": "password123", "display_name": "Login"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    payload = {"email": "wrong@example.com", "password": "password123", "display_name": "Wrong"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/login", json={"email": payload["email"], "password": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_token(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_websocket_ticket_requires_auth_and_cannot_call_rest_api(client, auth_headers):
    assert (await client.post("/api/v1/auth/ws-ticket")).status_code in (401, 403)
    response = await client.post("/api/v1/auth/ws-ticket", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["expires_in"] == 60

    ticket_headers = {"Authorization": f"Bearer {response.json()['ticket']}"}
    assert (await client.get("/api/v1/auth/me", headers=ticket_headers)).status_code == 401
