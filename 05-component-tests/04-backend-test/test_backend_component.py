from datetime import UTC
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from compliance_backend.audit_log import AuditLog


def recompute_signature(row: "AuditLog") -> str:
    from compliance_backend.signing import sign
    timestamp = row.timestamp.replace(tzinfo=UTC)
    return sign(row.event_id, timestamp, row.model_name, row.model_version, row.input_data_hash)


# an SDK event forwarded from the queue
def make_event(event_id: str = "event-1", timestamp: str = "2026-10-29T10:00:00Z",confidence: float | None = 0.9) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "system": {"model_name": "demo-model", "model_version": "1.0"},
        "clinical_session": {
            "input_data_hash": "sha256-abc",
            "inference_result": {
                "prediction": {"label": "tumor"},
                "confidence": confidence,
                "execution_time_ms": 1.5,
            },
        },
    }


def test_post_stores_the_event_and_signs_it(client: TestClient) -> None:
    response = client.post("/events", json=make_event())

    assert response.status_code == 201
    body = response.json()
    assert body["event_id"] == "event-1"
    assert body["model_name"] == "demo-model"
    assert body["input_data_hash"] == "sha256-abc"
    assert body["prediction"] == {"label": "tumor"}
    assert len(body["signature"]) == 64
    int(body["signature"], 16)

# acceptance by missing optional attribute test
def test_post_without_confidence_is_accepted(client: TestClient) -> None:
    response = client.post("/events", json=make_event(confidence=None))

    assert response.status_code == 201
    assert response.json()["confidence"] is None

# rejection by missing required attribute test
def test_post_with_a_missing_required_field_is_rejected(client: TestClient) -> None:
    event = make_event()
    del event["clinical_session"]["input_data_hash"]

    response = client.post("/events", json=event)

    assert response.status_code == 422
    assert client.get("/events").json() == []

# indempotency test
def test_posting_the_same_event_twice_stores_it_once(client: TestClient) -> None:
    first = client.post("/events", json=make_event())
    second = client.post("/events", json=make_event())

    assert second.status_code == 201
    assert second.json()["signature"] == first.json()["signature"]
    assert len(client.get("/events").json()) == 1

# simulate audit pulling existing data by exsiting eventId
def test_get_returns_a_stored_event(client: TestClient) -> None:
    posted = client.post("/events", json=make_event()).json()

    response = client.get("/events/event-1")

    assert response.status_code == 200
    assert response.json() == posted

# simulate audit pulling non-existing data by non-existing eventId
def test_get_unknown_event_is_404(client: TestClient) -> None:
    assert client.get("/events/does-not-exist").status_code == 404

# simulate audit pulling all events, when none exist yet
def test_list_is_empty_at_first(client: TestClient) -> None:
    assert client.get("/events").json() == []

# simulate audit pulling all events, when a few exist already
def test_list_shows_newest_first(client: TestClient) -> None:
    client.post("/events", json=make_event("event-2", "2026-10-29T11:00:00Z"))
    client.post("/events", json=make_event("event-3", "2026-10-29T12:00:00Z"))
    client.post("/events", json=make_event("event-1", "2026-10-29T10:00:00Z"))

    ids = [event["event_id"] for event in client.get("/events").json()]

    assert ids == ["event-3", "event-2", "event-1"]


# prove the signature survives a trip through the database
def test_stored_row_still_matches_its_signature(client: TestClient, session_factory: "sessionmaker[Session]") -> None:
    from compliance_backend.audit_log import AuditLog

    client.post("/events", json=make_event())

    with session_factory() as db:
        row = db.get(AuditLog, "event-1")
        assert row is not None
        assert row.signature == recompute_signature(row)


def test_signature_depends_on_the_secret_key(client: TestClient, session_factory: "sessionmaker[Session]", monkeypatch: pytest.MonkeyPatch) -> None:
    from compliance_backend.audit_log import AuditLog

    client.post("/events", json=make_event())
    monkeypatch.setenv("SIGNING_KEY", "some-other-key")

    with session_factory() as db:
        row = db.get(AuditLog, "event-1")
        assert row is not None
        assert row.signature != recompute_signature(row)
