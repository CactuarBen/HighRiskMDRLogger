import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from compliance_adapter.adapter import ComplianceAdapter
from compliance_forwarder.forwarder import Forwarder
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from compliance_backend.audit_log import AuditLog


def read_queue(queue_file: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in queue_file.read_text().splitlines()]


# runs the adapter once per scan, the way an application would
def log_predictions(queue_file: Path, scans: list[bytes]) -> None:
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")
    for scan in scans:
        adapter.start(scan)
        adapter.finish({"label": "healthy"}, 0.9)


def test_events_travel_from_adapter_to_backend(
    tmp_path: Path, client: TestClient, forward: Callable[[Path], list[int]]
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    log_predictions(queue_file, [b"scan 1", b"scan 2", b"scan 3"])

    codes = forward(queue_file)

    assert codes == [201, 201, 201]
    for sent in read_queue(queue_file):
        stored = client.get(f"/events/{sent['event_id']}").json()
        assert stored["model_name"] == sent["system"]["model_name"]
        assert stored["input_data_hash"] == sent["clinical_session"]["input_data_hash"]
        assert stored["prediction"] == sent["clinical_session"]["inference_result"]["prediction"]
        assert len(stored["signature"]) == 64


def test_delivering_the_queue_twice_stores_each_event_once(
    tmp_path: Path, client: TestClient, forward: Callable[[Path], list[int]]
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    log_predictions(queue_file, [b"scan 1", b"scan 2", b"scan 3"])

    forward(queue_file)
    forward(queue_file)

    assert len(client.get("/events").json()) == 3


def test_a_failed_prediction_leaves_no_event(
    tmp_path: Path, client: TestClient, forward: Callable[[Path], list[int]]
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    for scan in (b"scan 1", b"bad scan", b"scan 3"):
        adapter.start(scan)
        try:
            if scan == b"bad scan":
                raise ValueError("model crashed")
            adapter.finish({"label": "healthy"}, 0.9)
        except ValueError as error:
            adapter.error(error)

    codes = forward(queue_file)

    assert codes == [201, 201]
    assert len(client.get("/events").json()) == 2


# the claim of the whole project: a changed record no longer matches its signature
def test_a_tampered_row_no_longer_matches_its_signature(
    tmp_path: Path,
    forward: Callable[[Path], list[int]],
    session_factory: "sessionmaker[Session]",
    recompute_signature: Callable[["AuditLog"], str],
) -> None:
    from compliance_backend.audit_log import AuditLog

    queue_file = tmp_path / "queue.jsonl"
    log_predictions(queue_file, [b"scan 1"])
    forward(queue_file)
    event_id = read_queue(queue_file)[0]["event_id"]

    with session_factory() as db:
        row = db.get(AuditLog, event_id)
        assert row is not None
        assert row.signature == recompute_signature(row)  # untouched, signature matches
        row.model_name = "tampered-model"
        db.commit()

    with session_factory() as db:
        row = db.get(AuditLog, event_id)
        assert row is not None
        assert row.signature != recompute_signature(row)  # changed, signature no longer matches!


# below are tests with real forwarder delivering the events, over real http to a running backend

def stored_events(backend_url: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = httpx.get(f"{backend_url}/events").json()
    return events


def test_the_forwarder_delivers_what_the_adapter_logged(
    tmp_path: Path, live_backend: str, make_forwarder: Callable[[Path, str], Forwarder]
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    log_predictions(queue_file, [b"scan 1", b"scan 2", b"scan 3"])

    sent = make_forwarder(queue_file, live_backend).run_once()

    assert sent == 3
    stored = stored_events(live_backend)
    assert {event["event_id"] for event in stored} == {event["event_id"] for event in read_queue(queue_file)}
    assert all(len(event["signature"]) == 64 for event in stored)


def test_events_wait_in_the_queue_while_the_backend_is_down(
    tmp_path: Path, live_backend: str, make_forwarder: Callable[[Path, str], Forwarder]
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    log_predictions(queue_file, [b"scan 1", b"scan 2"])

    down = make_forwarder(queue_file, "http://127.0.0.1:1")  # nothing listens on port 1
    assert down.run_once() == 0
    assert down.failures == 1
    assert stored_events(live_backend) == []

    up = make_forwarder(queue_file, live_backend)
    assert up.run_once() == 2
    assert len(stored_events(live_backend)) == 2


def test_a_bad_line_is_dead_lettered_and_later_events_still_arrive(
    tmp_path: Path, live_backend: str, make_forwarder: Callable[[Path, str], Forwarder]
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    log_predictions(queue_file, [b"scan 1"])
    with queue_file.open("a") as file:
        file.write(json.dumps({"event_id": "broken"}) + "\n")  # the backend answers 422
    log_predictions(queue_file, [b"scan 2"])

    sent = make_forwarder(queue_file, live_backend).run_once()

    assert sent == 2
    assert len(stored_events(live_backend)) == 2
    dead_letters = (tmp_path / "forwarder_state" / "dead_letter.jsonl").read_text().splitlines()
    assert len(dead_letters) == 1
    assert "broken" in dead_letters[0]


def test_a_restarted_forwarder_sends_only_the_new_events(
    tmp_path: Path, live_backend: str, make_forwarder: Callable[[Path, str], Forwarder]
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    log_predictions(queue_file, [b"scan 1", b"scan 2"])
    assert make_forwarder(queue_file, live_backend).run_once() == 2

    log_predictions(queue_file, [b"scan 3"])
    restarted = make_forwarder(queue_file, live_backend)

    assert restarted.run_once() == 1
    assert len(stored_events(live_backend)) == 3
