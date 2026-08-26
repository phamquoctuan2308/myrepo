import pytest


async def _other_user(client, other_auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=other_auth_headers)
    return resp.json()


async def _team_workspace(client, auth_headers, other_auth_headers):
    other = await _other_user(client, other_auth_headers)
    workspace = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Chat Team"},
            headers=auth_headers,
        )
    ).json()
    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": other["email"], "role": "member"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return workspace, other


@pytest.mark.asyncio
async def test_create_and_dedupe_direct_conversation(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    payload = {"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]}

    resp1 = await client.post("/api/v1/conversations", json=payload, headers=auth_headers)
    assert resp1.status_code == 200
    conv1 = resp1.json()
    assert conv1["type"] == "direct"
    assert conv1["name"] == "Bob"

    resp2 = await client.post("/api/v1/conversations", json=payload, headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["id"] == conv1["id"]


@pytest.mark.asyncio
async def test_group_conversation_requires_name(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    resp = await client.post(
        "/api/v1/conversations",
        json={"type": "group", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_group_conversation_with_name(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    resp = await client.post(
        "/api/v1/conversations",
        json={
            "type": "group",
            "participant_ids": [other["id"]],
            "name": "Team",
            "workspace_id": workspace["id"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "group"
    assert body["name"] == "Team"
    assert len(body["participants"]) == 2


@pytest.mark.asyncio
async def test_send_and_list_messages(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conv = (
        await client.post(
            "/api/v1/conversations",
            json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
            headers=auth_headers,
        )
    ).json()

    send_resp = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages", json={"content": "hello"}, headers=auth_headers
    )
    assert send_resp.status_code == 200
    assert send_resp.json()["content"] == "hello"

    history = await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=auth_headers)
    assert history.status_code == 200
    body = history.json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "hello"
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_unread_count_and_mark_read(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conv = (
        await client.post(
            "/api/v1/conversations",
            json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
            headers=auth_headers,
        )
    ).json()
    await client.post(f"/api/v1/conversations/{conv['id']}/messages", json={"content": "hi bob"}, headers=auth_headers)

    listed = await client.get(
        f"/api/v1/conversations?workspace_id={workspace['id']}",
        headers=other_auth_headers,
    )
    summary = next(c for c in listed.json()["conversations"] if c["id"] == conv["id"])
    assert summary["unread_count"] == 1

    await client.post(f"/api/v1/conversations/{conv['id']}/read", headers=other_auth_headers)
    listed_again = await client.get(
        f"/api/v1/conversations?workspace_id={workspace['id']}",
        headers=other_auth_headers,
    )
    summary_again = next(c for c in listed_again.json()["conversations"] if c["id"] == conv["id"])
    assert summary_again["unread_count"] == 0


@pytest.mark.asyncio
async def test_first_unread_message_id_in_message_list(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conv = (
        await client.post(
            "/api/v1/conversations",
            json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
            headers=auth_headers,
        )
    ).json()

    # Alice sends two messages; Bob hasn't read anything yet - the first one is his first unread.
    first = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages", json={"content": "hi bob"}, headers=auth_headers
    )
    await client.post(
        f"/api/v1/conversations/{conv['id']}/messages", json={"content": "still there?"}, headers=auth_headers
    )

    history = await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=other_auth_headers)
    assert history.json()["first_unread_message_id"] == first.json()["id"]

    # Paginating into older history (`before` set) doesn't recompute it - not the "just opened" moment.
    paged = await client.get(
        f"/api/v1/conversations/{conv['id']}/messages",
        params={"before": first.json()["id"]},
        headers=other_auth_headers,
    )
    assert paged.json()["first_unread_message_id"] is None


@pytest.mark.asyncio
async def test_first_unread_message_id_none_after_marking_read(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conv = (
        await client.post(
            "/api/v1/conversations",
            json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
            headers=auth_headers,
        )
    ).json()
    await client.post(f"/api/v1/conversations/{conv['id']}/messages", json={"content": "hi bob"}, headers=auth_headers)

    await client.post(f"/api/v1/conversations/{conv['id']}/read", headers=other_auth_headers)

    history = await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=other_auth_headers)
    assert history.json()["first_unread_message_id"] is None


@pytest.mark.asyncio
async def test_first_unread_message_id_none_for_own_messages(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conv = (
        await client.post(
            "/api/v1/conversations",
            json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
            headers=auth_headers,
        )
    ).json()
    await client.post(f"/api/v1/conversations/{conv['id']}/messages", json={"content": "hi bob"}, headers=auth_headers)

    history = await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=auth_headers)
    assert history.json()["first_unread_message_id"] is None


@pytest.mark.asyncio
async def test_non_participant_forbidden(client, auth_headers, other_auth_headers):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conv = (
        await client.post(
            "/api/v1/conversations",
            json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
            headers=auth_headers,
        )
    ).json()

    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "password": "password123", "display_name": "Carol"},
    )
    third = await client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "password123"},
    )
    carol_headers = {"Authorization": f"Bearer {third.json()['access_token']}"}

    resp = await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=carol_headers)
    assert resp.status_code == 404

    resp2 = await client.post(
        f"/api/v1/conversations/{conv['id']}/messages", json={"content": "hey"}, headers=carol_headers
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_list_users_excludes_self(client, auth_headers, other_auth_headers):
    workspace, _ = await _team_workspace(client, auth_headers, other_auth_headers)
    resp = await client.get(f"/api/v1/users?workspace_id={workspace['id']}", headers=auth_headers)
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert "bob@example.com" in emails
    assert "alice@example.com" not in emails


@pytest.mark.asyncio
async def test_personal_user_directory_requires_search(client, auth_headers, other_auth_headers):
    workspaces = (await client.get("/api/v1/workspaces", headers=auth_headers)).json()
    personal = next(item for item in workspaces if item["type"] == "personal")
    response = await client.get(f"/api/v1/users?workspace_id={personal['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []

    found = await client.get(
        f"/api/v1/users?workspace_id={personal['id']}&search=bob", headers=auth_headers
    )
    assert found.status_code == 200
    assert [user["email"] for user in found.json()] == ["bob@example.com"]

    wildcard = await client.get(
        f"/api/v1/users?workspace_id={personal['id']}&search=%25%25", headers=auth_headers
    )
    assert wildcard.status_code == 200
    assert wildcard.json() == []


@pytest.mark.asyncio
async def test_hide_conversation_is_per_user_and_new_message_restores_it(
    client, auth_headers, other_auth_headers
):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conversation = (
        await client.post(
            "/api/v1/conversations",
            json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
            headers=auth_headers,
        )
    ).json()

    hidden = await client.delete(f"/api/v1/conversations/{conversation['id']}", headers=auth_headers)
    assert hidden.status_code == 204
    mine = await client.get(f"/api/v1/conversations?workspace_id={workspace['id']}", headers=auth_headers)
    theirs = await client.get(
        f"/api/v1/conversations?workspace_id={workspace['id']}", headers=other_auth_headers
    )
    assert conversation["id"] not in {item["id"] for item in mine.json()["conversations"]}
    assert conversation["id"] in {item["id"] for item in theirs.json()["conversations"]}

    sent = await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "This should restore the hidden conversation"},
        headers=other_auth_headers,
    )
    assert sent.status_code == 200
    restored = await client.get(
        f"/api/v1/conversations?workspace_id={workspace['id']}", headers=auth_headers
    )
    assert conversation["id"] in {item["id"] for item in restored.json()["conversations"]}


@pytest.mark.asyncio
async def test_leave_group_revokes_access_and_keeps_remaining_member(
    client, auth_headers, other_auth_headers
):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conversation = (
        await client.post(
            "/api/v1/conversations",
            json={
                "type": "group",
                "participant_ids": [other["id"]],
                "name": "Lifecycle group",
                "workspace_id": workspace["id"],
            },
            headers=auth_headers,
        )
    ).json()

    left = await client.post(
        f"/api/v1/conversations/{conversation['id']}/leave", headers=other_auth_headers
    )
    assert left.status_code == 200
    assert left.json()["conversation_deleted"] is False
    denied = await client.get(
        f"/api/v1/conversations/{conversation['id']}/messages", headers=other_auth_headers
    )
    assert denied.status_code == 404
    remaining = await client.get(
        f"/api/v1/conversations/{conversation['id']}/messages", headers=auth_headers
    )
    assert remaining.status_code == 200


@pytest.mark.asyncio
async def test_last_group_member_can_leave_without_deleting_linked_user_data(
    client, auth_headers, other_auth_headers
):
    workspace, other = await _team_workspace(client, auth_headers, other_auth_headers)
    conversation = (
        await client.post(
            "/api/v1/conversations",
            json={
                "type": "group",
                "participant_ids": [other["id"]],
                "name": "Disposable group",
                "workspace_id": workspace["id"],
            },
            headers=auth_headers,
        )
    ).json()
    task = (
        await client.post(
            "/api/v1/tasks",
            json={"title": "Keep me", "workspace_id": workspace["id"], "conversation_id": conversation["id"]},
            headers=auth_headers,
        )
    ).json()

    first = await client.post(f"/api/v1/conversations/{conversation['id']}/leave", headers=other_auth_headers)
    assert first.json()["conversation_deleted"] is False
    last = await client.post(f"/api/v1/conversations/{conversation['id']}/leave", headers=auth_headers)
    assert last.status_code == 200
    assert last.json()["conversation_deleted"] is True

    tasks = (await client.get(f"/api/v1/tasks?workspace_id={workspace['id']}", headers=auth_headers)).json()
    preserved = next(item for item in tasks if item["id"] == task["id"])
    assert preserved["conversation_id"] is None
