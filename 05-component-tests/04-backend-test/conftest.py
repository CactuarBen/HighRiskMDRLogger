from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator["sessionmaker[Session]"]:
    monkeypatch.chdir(tmp_path)
    from compliance_backend import audit_log
    from compliance_backend.database import Base

    # make every connection shares the same in-memory database
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
