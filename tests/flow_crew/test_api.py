"""HTTP surface mà dashboard dùng: đúng mã lỗi cho từng loại từ chối."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.flow_crew.app import app

API = "/api/v1/flow-crew"


@pytest.fixture
def client() -> TestClient:
    client = TestClient(app)
    client.post(f"{API}/simulation/reset")
    return client


def _decide(client: TestClient, ticket_id: str, role: str, *, approved: bool = True):
    return client.post(
        f"{API}/approvals/{ticket_id}/decision",
        json={"role": role, "actor_name": f"người duyệt {role}", "approved": approved},
    )


def test_dashboard_and_empty_snapshot_are_served(client: TestClient) -> None:
    assert client.get("/").status_code == 200
    snapshot = client.get(f"{API}/snapshot").json()
    assert len(snapshot["zones"]) == 6
    assert snapshot["alerts"] == []
    assert snapshot["approvals"] == []


def test_full_flow_over_http(client: TestClient) -> None:
    snapshot = client.post(f"{API}/incidents", json={}).json()
    pending = {ticket["required_role"]: ticket["ticket_id"] for ticket in snapshot["approvals"]}
    assert set(pending) == {"shift_lead", "marketing", "park_manager"}

    for role, ticket_id in pending.items():
        assert _decide(client, ticket_id, role).status_code == 200

    guest_ticket = next(
        ticket for ticket in client.get(f"{API}/snapshot").json()["approvals"] if ticket["status"] == "pending"
    )
    final = _decide(client, guest_ticket["ticket_id"], "guest").json()

    workflow = final["workflows"][0]
    assert workflow["status"] == "closed"
    assert final["kpis"]["audit_chain_valid"] is True
    assert any(message["author"] == "người duyệt shift_lead" for message in final["room"])


def test_opening_the_same_incident_twice_is_a_conflict(client: TestClient) -> None:
    assert client.post(f"{API}/incidents", json={}).status_code == 200
    assert client.post(f"{API}/incidents", json={}).status_code == 409


def test_wrong_desk_gets_403_and_nothing_runs(client: TestClient) -> None:
    snapshot = client.post(f"{API}/incidents", json={}).json()
    marketing = next(ticket for ticket in snapshot["approvals"] if ticket["required_role"] == "marketing")
    response = _decide(client, marketing["ticket_id"], "shift_lead")
    assert response.status_code == 403
    assert client.get(f"{API}/snapshot").json()["park"]["promotions"] == []


def test_deciding_twice_is_a_conflict(client: TestClient) -> None:
    snapshot = client.post(f"{API}/incidents", json={}).json()
    ticket = next(ticket for ticket in snapshot["approvals"] if ticket["required_role"] == "shift_lead")
    assert _decide(client, ticket["ticket_id"], "shift_lead").status_code == 200
    assert _decide(client, ticket["ticket_id"], "shift_lead").status_code == 409


def test_a_system_that_stays_down_returns_503(client: TestClient) -> None:
    client.post(f"{API}/simulation/inject-failure", json={"tool": "app", "times": 5})
    assert client.post(f"{API}/incidents", json={}).status_code == 503


def test_ask_answers_without_an_incident(client: TestClient) -> None:
    response = client.post(f"{API}/ask", json={"agent": "A2", "question": "Mật độ Fairy Land hiện giờ thế nào?"})
    assert response.status_code == 200
    assert response.json()["text"].startswith("Fairy Land")
