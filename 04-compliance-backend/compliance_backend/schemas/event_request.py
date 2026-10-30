from datetime import datetime

from pydantic import BaseModel

from .clinical_session_in import ClinicalSessionIn
from .system_metadata_in import SystemMetadataIn


# final full event accepted by POST /events
# mirrors the SDK's ComplianceObject, but is declared here so the backend does not import the SDK
class EventRequest(BaseModel):
    event_id: str                           # unique id, created by the SDK
    timestamp: datetime                     # when the SDK logged the event, in UTC
    system: SystemMetadataIn
    clinical_session: ClinicalSessionIn
