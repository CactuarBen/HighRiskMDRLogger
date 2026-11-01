import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pytest
from compliance_adapter.adapter import ComplianceAdapter


def read_events(queue_file: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in queue_file.read_text().splitlines()]


# integration test examining adapter and SDK
def test_finish_writes_one_event(tmp_path: Path) -> None:
    # GIVEN
    # make a queue file path inside tmp_path
    queue_file = tmp_path / "queue.jsonl"
    # create the adapter, call start() then finish()
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    # WHEN
    adapter.start(b"fake image bytes")
    adapter.finish({"label": "healthy"}, 0.95)

    # THEN
    # read the file and assert it has 1 line
    lines = queue_file.read_text().splitlines()
    assert len(lines) == 1
    # assert the line contains the model_name you passed
    event = json.loads(lines[0])
    assert event["system"]["model_name"] == "demo-model"


def test_event_contains_everything_that_was_passed_in(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "2.5")

    adapter.start(b"scan")
    adapter.finish({"label": "tumor"}, 0.83)

    event = read_events(queue_file)[0]
    result = event["clinical_session"]["inference_result"]
    assert event["system"] == {"model_name": "demo-model", "model_version": "2.5"}
    assert result["prediction"] == {"label": "tumor"}
    assert result["confidence"] == 0.83


def test_input_is_stored_as_a_sha256_fingerprint_only(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")
    patient_data = b"very secret patient scan"

    adapter.start(patient_data)
    adapter.finish({"label": "healthy"}, 0.9)

    expected_hash = "sha256-" + hashlib.sha256(patient_data).hexdigest()
    event = read_events(queue_file)[0]
    assert event["clinical_session"]["input_data_hash"] == expected_hash
    assert "very secret patient scan" not in queue_file.read_text()


def test_same_input_gives_the_same_hash(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    for _ in range(2):
        adapter.start(b"same scan")
        adapter.finish({"label": "healthy"}, 0.9)

    first, second = read_events(queue_file)
    assert first["clinical_session"]["input_data_hash"] == second["clinical_session"]["input_data_hash"]


def test_finish_without_confidence_still_writes_the_event(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    adapter.start(b"scan")
    adapter.finish({"label": "healthy"}, None)

    event = read_events(queue_file)[0]
    assert event["clinical_session"]["inference_result"]["confidence"] is None


def test_finish_before_start_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    with pytest.raises(RuntimeError, match="before start"):
        adapter.finish({"label": "healthy"}, 0.9)

    assert not queue_file.exists()


def test_error_writes_no_event_but_logs_the_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")
    adapter.start(b"scan")

    with caplog.at_level(logging.ERROR):
        adapter.error(ValueError("model crashed"))

    assert not queue_file.exists()
    assert "model crashed" in caplog.text


# link between a patient and an event
def test_finish_returns_the_id_of_the_event_it_logged(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    returned_ids: list[str] = []
    for scan in (b"scan 1", b"scan 2"):
        adapter.start(scan)
        returned_ids.append(adapter.finish({"label": "healthy"}, 0.9))

    assert returned_ids == [event["event_id"] for event in read_events(queue_file)]


def test_every_event_gets_its_own_id(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    for scan in (b"scan 1", b"scan 2"):
        adapter.start(scan)
        adapter.finish({"label": "healthy"}, 0.9)

    first, second = read_events(queue_file)
    assert first["event_id"] != second["event_id"]


def test_execution_time_is_measured(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    adapter.start(b"scan")
    adapter.finish({"label": "healthy"}, 0.9)

    execution_time = read_events(queue_file)[0]["clinical_session"]["inference_result"]["execution_time_ms"]
    assert 0 <= execution_time < 1000
