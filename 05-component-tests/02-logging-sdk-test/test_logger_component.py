import ast
import json
from pathlib import Path

import compliance_logging_sdk
from compliance_logging_sdk.core import ComplianceLogger
from compliance_logging_sdk.model.clinical_session import ClinicalSession
from compliance_logging_sdk.model.compliance_object import ComplianceObject
from compliance_logging_sdk.model.inference_result import InferenceResult
from compliance_logging_sdk.model.system_metadata import SystemMetadata

# modules that would mean the SDK talks to the network
NETWORK_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx",
    "aiohttp", "websockets", "ftplib", "smtplib", "xmlrpc",
}

# the logging sdk must not have any connectivity as it must write EVERY event into jsonl with no hiccups
# introduction of any network module violates the isolation of this service and thus introduces possible interference
def test_sdk_imports_no_network_modules() -> None:
    assert compliance_logging_sdk.__file__ is not None
    source_files = list(Path(compliance_logging_sdk.__file__).parent.rglob("*.py"))
    assert source_files  # the scan really looked at something

    found: list[str] = []
    for source_file in source_files:
        for node in ast.walk(ast.parse(source_file.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            found += [f"{source_file.name}: {name}" for name in names if name.split(".")[0] in NETWORK_MODULES]

    assert found == []


def make_event(label: str = "healthy") -> ComplianceObject:
    return ComplianceObject(
        # eventId gets assigned automatically
        # timestamp gets assigned automatically
        system=SystemMetadata(model_name="demo-model", model_version="1.0"),
        clinical_session=ClinicalSession(
            input_data_hash="sha256-abc",
            inference_result=InferenceResult(prediction={"label": label}, confidence=0.9, execution_time_ms=1.5),
        ),
    )

# send three simple events to SDK and check output in jsonl
def test_each_event_becomes_one_json_line(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    logger = ComplianceLogger(str(queue_file))

    for _ in range(3):
        logger.write_event(make_event())

    lines = queue_file.read_text().splitlines()
    assert len(lines) == 3
    for line in lines:
        assert "event_id" in json.loads(line)

# first run of the service must create the folder with jsonl file itself
def test_missing_folder_is_created(tmp_path: Path) -> None:
    queue_file = tmp_path / "not" / "yet" / "there" / "queue.jsonl"

    logger = ComplianceLogger(str(queue_file))
    logger.write_event(make_event())

    assert queue_file.exists()

# the logger must ONLY append, never modify or delete records
def test_a_second_logger_appends_instead_of_overwriting(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    ComplianceLogger(str(queue_file)).write_event(make_event("first"))

    ComplianceLogger(str(queue_file)).write_event(make_event("second"))

    labels = [json.loads(line)["clinical_session"]["inference_result"]["prediction"]["label"]
              for line in queue_file.read_text().splitlines()]
    assert labels == ["first", "second"]

# simple reconciliation checks
def test_a_written_line_can_be_read_back_into_the_same_event(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    event = make_event()

    ComplianceLogger(str(queue_file)).write_event(event)

    line = queue_file.read_text().splitlines()[0]
    assert ComplianceObject.model_validate_json(line) == event
