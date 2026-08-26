import pytest


async def _create_direct_conversation(client, creator_headers, other_headers, *, include_workspace=False):
    other_me = await client.get("/api/v1/auth/me", headers=other_headers)
    other = other_me.json()
    workspace = (
        await client.post("/api/v1/workspaces", json={"name": "AI permission test"}, headers=creator_headers)
    ).json()
    member = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": other["email"], "role": "member"},
        headers=creator_headers,
    )
    assert member.status_code == 201
    conv = await client.post(
        "/api/v1/conversations",
        json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
        headers=creator_headers,
    )
    assert conv.status_code == 200
    return (conv.json()["id"], workspace["id"]) if include_workspace else conv.json()["id"]


@pytest.mark.asyncio
async def test_get_ai_permission_defaults_to_not_granted(client, auth_headers, other_auth_headers):
    conversation_id = await _create_direct_conversation(client, auth_headers, other_auth_headers)

    response = await client.get(f"/api/v1/conversations/{conversation_id}/ai-permission", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["granted"] is False
    assert data["contribution_allowed"] is False
    assert data["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_put_grants_and_get_reflects_it(client, auth_headers, other_auth_headers):
    conversation_id = await _create_direct_conversation(client, auth_headers, other_auth_headers)

    put_response = await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission", json={"granted": True}, headers=auth_headers
    )
    assert put_response.status_code == 200
    assert put_response.json()["granted"] is True

    get_response = await client.get(f"/api/v1/conversations/{conversation_id}/ai-permission", headers=auth_headers)
    assert get_response.json()["granted"] is True


@pytest.mark.asyncio
async def test_put_revokes_and_get_reflects_it(client, auth_headers, other_auth_headers):
    conversation_id = await _create_direct_conversation(client, auth_headers, other_auth_headers)

    await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission", json={"granted": True}, headers=auth_headers
    )
    revoke_response = await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission", json={"granted": False}, headers=auth_headers
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["granted"] is False

    get_response = await client.get(f"/api/v1/conversations/{conversation_id}/ai-permission", headers=auth_headers)
    assert get_response.json()["granted"] is False


@pytest.mark.asyncio
async def test_ai_permission_grant_is_per_user_not_shared(client, auth_headers, other_auth_headers):
    """One participant granting doesn't grant it on behalf of the other participant."""
    conversation_id = await _create_direct_conversation(client, auth_headers, other_auth_headers)

    await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission", json={"granted": True}, headers=auth_headers
    )

    other_get = await client.get(
        f"/api/v1/conversations/{conversation_id}/ai-permission", headers=other_auth_headers
    )
    assert other_get.json()["granted"] is False


@pytest.mark.asyncio
async def test_assistant_access_and_contribution_consent_are_independent(
    client, auth_headers, other_auth_headers
):
    conversation_id = await _create_direct_conversation(client, auth_headers, other_auth_headers)

    response = await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission",
        json={"contribution_allowed": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["granted"] is False
    assert response.json()["contribution_allowed"] is True

    response = await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission",
        json={"granted": True},
        headers=auth_headers,
    )
    assert response.json()["granted"] is True
    assert response.json()["contribution_allowed"] is True


@pytest.mark.asyncio
async def test_ai_permission_get_requires_participant(client, auth_headers, other_auth_headers):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol2@example.com", "password": "password123", "display_name": "Carol"},
    )
    third = await client.post(
        "/api/v1/auth/login", json={"email": "carol2@example.com", "password": "password123"}
    )
    third_headers = {"Authorization": f"Bearer {third.json()['access_token']}"}
    conversation_id = await _create_direct_conversation(client, auth_headers, other_auth_headers)

    response = await client.get(f"/api/v1/conversations/{conversation_id}/ai-permission", headers=third_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ai_permission_put_requires_participant(client, auth_headers, other_auth_headers):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol3@example.com", "password": "password123", "display_name": "Carol"},
    )
    third = await client.post(
        "/api/v1/auth/login", json={"email": "carol3@example.com", "password": "password123"}
    )
    third_headers = {"Authorization": f"Bearer {third.json()['access_token']}"}
    conversation_id = await _create_direct_conversation(client, auth_headers, other_auth_headers)

    response = await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission", json={"granted": True}, headers=third_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_conversation_list_reflects_ai_permission_state(client, auth_headers, other_auth_headers):
    conversation_id, workspace_id = await _create_direct_conversation(
        client, auth_headers, other_auth_headers, include_workspace=True
    )

    listed = await client.get(
        f"/api/v1/conversations?workspace_id={workspace_id}", headers=auth_headers
    )
    summary = next(item for item in listed.json()["conversations"] if item["id"] == conversation_id)
    assert summary["ai_permission_granted"] is False

    await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission",
        json={"granted": True},
        headers=auth_headers,
    )

    listed_again = await client.get(
        f"/api/v1/conversations?workspace_id={workspace_id}", headers=auth_headers
    )
    summary_again = next(
        item for item in listed_again.json()["conversations"] if item["id"] == conversation_id
    )
    assert summary_again["ai_permission_granted"] is True

    other_listed = await client.get(
        f"/api/v1/conversations?workspace_id={workspace_id}", headers=other_auth_headers
    )
    other_summary = next(
        item for item in other_listed.json()["conversations"] if item["id"] == conversation_id
    )
    assert other_summary["ai_permission_granted"] is False
