import pytest

from src.agents.tools import memory_tool


@pytest.mark.asyncio
async def test_list_memories_formats_saved_memories(client, auth_headers):
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    await client.post(
        "/api/v1/memories",
        json={"category": "Work", "title": "Prefers async standups", "detail": "Not a morning person"},
        headers=auth_headers,
    )

    result = await memory_tool.list_memories.coroutine(state={"user_id": me["id"]})

    assert "Prefers async standups" in result
    assert "Not a morning person" in result
    assert "Work" in result


@pytest.mark.asyncio
async def test_list_memories_no_detail_omits_colon(client, auth_headers):
    me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    await client.post(
        "/api/v1/memories", json={"category": "People", "title": "Manager is Lan"}, headers=auth_headers
    )

    result = await memory_tool.list_memories.coroutine(state={"user_id": me["id"]})

    assert result == "- [People] Manager is Lan"


@pytest.mark.asyncio
async def test_list_memories_no_saved_memories():
    result = await memory_tool.list_memories.coroutine(state={"user_id": "no-such-user"})
    assert result == "The user has no saved memories yet."


def test_list_memories_hidden_from_llm_tool_schema():
    assert list(memory_tool.list_memories.args.keys()) == ["query", "limit"]
