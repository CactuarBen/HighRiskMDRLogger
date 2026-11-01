import json
import socket
import threading
import time
from collections.abc import Callable, Iterator
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import uvicorn
from compliance_forwarder.forwarder import Forwarder
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if TYPE_CHECKING:
    from compliance_backend.audit_log import AuditLog


@pytest.fixture
def session_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator["sessionmaker[Session]"]:
    monkeypatch.chdir(tmp_path)
    # importing audit_log registers the table on Base, nothing in this file uses the name
    from compliance_backend import audit_log  # noqa: F401  # pylint: disable=unused-import
    from compliance_backend.database import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def client(session_factory: "sessionmaker[Session]", monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SIGNING_KEY", "test-key")
    from compliance_backend.database import get_db
    from compliance_backend.main import app

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def live_backend(session_factory: "sessionmaker[Session]", monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("SIGNING_KEY", "test-key")
    from compliance_backend.database import get_db
    from compliance_backend.main import app

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started, "the backend did not start"

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)
    app.dependency_overrides.clear()


@pytest.fixture
def make_forwarder(tmp_path: Path) -> Iterator[Callable[[Path, str], Forwarder]]:
    created: list[Forwarder] = []

    def make(queue_file: Path, backend_url: str) -> Forwarder:
        forwarder = Forwarder(str(queue_file), backend_url, str(tmp_path / "forwarder_state"))
        created.append(forwarder)
        return forwarder

    yield make
    for forwarder in created:
        forwarder.close()


@pytest.fixture
def forward(client: TestClient) -> Callable[[Path], list[int]]:
    def forward_queue(queue_file: Path) -> list[int]:
        return [
            client.post("/events", json=json.loads(line)).status_code
            for line in queue_file.read_text().splitlines()
        ]

    return forward_queue

@pytest.fixture
def recompute_signature() -> Callable[["AuditLog"], str]:
    def recompute(row: "AuditLog") -> str:
        from compliance_backend.signing import sign

        timestamp = row.timestamp.replace(tzinfo=timezone.utc)
        return sign(row.event_id, timestamp, row.model_name, row.model_version, row.input_data_hash)

    return recompute
