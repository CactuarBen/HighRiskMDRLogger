import json
from pathlib import Path
from typing import Any

import httpx
from compliance_forwarder.forwarder import Forwarder


def test_all_events_are_sent_in_order(tmp_path: Path) -> None:
    backend = FakeBackend(201)
    forwarder = make_forwarder(tmp_path, backend)
    add_events(tmp_path, "e1", "e2", "e3")

    sent = forwarder.run_once()

    assert sent == 3
    assert backend.received_ids == ["e1", "e2", "e3"]


def test_an_event_is_not_sent_a_second_time(tmp_path: Path) -> None:
    backend = FakeBackend(201)
    forwarder = make_forwarder(tmp_path, backend)
    add_events(tmp_path, "e1", "e2", "e3")

    forwarder.run_once()
    sent_again = forwarder.run_once()

    assert sent_again == 0
    assert backend.received_ids == ["e1", "e2", "e3"]


def test_new_events_are_picked_up_on_the_next_pass(tmp_path: Path) -> None:
    backend = FakeBackend(201)
    forwarder = make_forwarder(tmp_path, backend)
    add_events(tmp_path, "e1")
    forwarder.run_once()

    add_events(tmp_path, "e2")
    forwarder.run_once()

    assert backend.received_ids == ["e1", "e2"]


def test_a_server_error_is_retried_and_the_order_is_kept(tmp_path: Path) -> None:
    backend = FakeBackend(201, 500, 201)
    forwarder = make_forwarder(tmp_path, backend)
    add_events(tmp_path, "e1", "e2", "e3")

    first_pass = forwarder.run_once()
    assert first_pass == 1
    assert backend.received_ids == ["e1", "e2"]  # e3 must not jump the queue

    second_pass = forwarder.run_once() # all will be 201 now
    assert second_pass == 2
    assert backend.received_ids == ["e1", "e2", "e2", "e3"]


def test_a_network_error_is_retried(tmp_path: Path) -> None:
    backend = FakeBackend(None, 201)
    forwarder = make_forwarder(tmp_path, backend)
    add_events(tmp_path, "e1", "e2")

    assert forwarder.run_once() == 0 # fails since reply is None (backend down)
    assert forwarder.run_once() == 2


def test_a_rejected_event_is_dead_lettered_and_the_next_one_still_goes(tmp_path: Path) -> None:
    backend = FakeBackend(422, 201)
    forwarder = make_forwarder(tmp_path, backend)
    add_events(tmp_path, "bad", "good")

    sent = forwarder.run_once() # bad gets rejected with 422

    assert sent == 1
    assert backend.received_ids == ["bad", "good"]
    dead_letters = read_dead_letters(tmp_path) # bad should be here
    assert len(dead_letters) == 1
    assert "bad" in dead_letters[0]["line"]
    assert "422" in dead_letters[0]["reason"] # youp
    assert forwarder.run_once() == 0  # the rejected event is not tried again

# json format check
def test_a_line_that_is_not_json_is_dead_lettered_without_being_sent(tmp_path: Path) -> None:
    backend = FakeBackend(201)
    forwarder = make_forwarder(tmp_path, backend)
    (tmp_path / "queue.jsonl").write_text("this is not json\n")
    add_events(tmp_path, "e1")

    sent = forwarder.run_once()

    assert sent == 1
    assert backend.received_ids == ["e1"]
    assert read_dead_letters(tmp_path)[0]["reason"] == "not valid json"

# no resubmissions of already processed events
def test_a_restart_carries_on_where_the_last_run_stopped(tmp_path: Path) -> None:
    backend = FakeBackend(201)
    add_events(tmp_path, "e1", "e2")
    make_forwarder(tmp_path, backend).run_once()

    add_events(tmp_path, "e3")
    restarted = make_forwarder(tmp_path, backend)  # a new object, same state folder
    sent = restarted.run_once()

    assert sent == 1
    assert backend.received_ids == ["e1", "e2", "e3"]

# won't happen, since the file is created once the first event is sent by the SDK, but stilll
def test_a_missing_queue_file_is_not_an_error(tmp_path: Path) -> None:
    forwarder = make_forwarder(tmp_path, FakeBackend(201))

    assert forwarder.run_once() == 0

# DOES NOT REPORT UNFINISHED EVENTS!!!
def test_a_line_that_is_still_being_written_waits(tmp_path: Path) -> None:
    backend = FakeBackend(201)
    forwarder = make_forwarder(tmp_path, backend)
    queue_file = tmp_path / "queue.jsonl"
    queue_file.write_text(json.dumps({"event_id": "e1"}) + "\n" + '{"event_id": "e2"')

    assert forwarder.run_once() == 1
    assert backend.received_ids == ["e1"]

    with queue_file.open("a") as file:
        file.write("}\n")  # the SDK finishes the line, which was beinng written

    assert forwarder.run_once() == 1
    assert backend.received_ids == ["e1", "e2"]

# incremental delays and their reset
def test_the_waiting_time_grows_while_the_backend_fails_and_resets_afterwards(tmp_path: Path) -> None:
    backend = FakeBackend(500, 500, 201)
    forwarder = make_forwarder(
        tmp_path, backend, poll_seconds=0.5, backoff_start_seconds=1.0, backoff_max_seconds=60.0
    )
    add_events(tmp_path, "e1")
    delays: list[float] = []

    # sleep only records the delay, so the test does not really wait
    forwarder.run_forever(stop=lambda: len(delays) >= 4, sleep=delays.append)

    assert delays == [1.0, 2.0, 0.5, 0.5]

# reaching the maximum delay
def test_the_waiting_time_stops_growing_at_the_maximum(tmp_path: Path) -> None:
    forwarder = make_forwarder(
        tmp_path, FakeBackend(500), backoff_start_seconds=1.0, backoff_max_seconds=5.0
    )
    add_events(tmp_path, "e1")
    delays: list[float] = []

    forwarder.run_forever(stop=lambda: len(delays) >= 5, sleep=delays.append)

    assert delays == [1.0, 2.0, 4.0, 5.0, 5.0]


# helper classes and methods

# a fake backend. it answers with the given status codes one after the other,
# the last one is repeated, where none means "the network is down" (no answer at all)
class FakeBackend:

    # unresponsive backend
    def __init__(self, *statuses: int | None) -> None:
        self.statuses = list(statuses)
        self.received_ids: list[str] = []

    # any response
    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.received_ids.append(json.loads(request.content)["event_id"])
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if status is None:
            raise httpx.ConnectError("backend is down", request=request)
        return httpx.Response(status)


# create a forwarder that would be sending events from queue.jsonl to backend
def make_forwarder(tmp_path: Path, backend: FakeBackend, **settings: Any) -> Forwarder:
    client = httpx.Client(transport=httpx.MockTransport(backend))
    return Forwarder(str(tmp_path / "queue.jsonl"), "http://backend", str(tmp_path / "state"), client=client, **settings)


# mock SDK that adds one event at a time to the queue file
def add_events(tmp_path: Path, *event_ids: str) -> None:
    with (tmp_path / "queue.jsonl").open("a") as file:
        for event_id in event_ids:
            file.write(json.dumps({"event_id": event_id}) + "\n")

# used to detect dead letters
def read_dead_letters(tmp_path: Path) -> list[dict[str, Any]]:
    dead_letter_file = tmp_path / "state" / "dead_letter.jsonl"
    return [json.loads(line) for line in dead_letter_file.read_text().splitlines()]