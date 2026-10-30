from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from .clinical_session import ClinicalSession
from .system_metadata import SystemMetadata


# full audit record
# it's the top-level object that gets written to the queue and sent to the backend
class ComplianceObject(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))                     # unique id, generated automatically
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC)) # when it was logged, in UTC, generated automatically
    system: SystemMetadata
    clinical_session: ClinicalSession
