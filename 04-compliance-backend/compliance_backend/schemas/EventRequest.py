from datetime import datetime

from pydantic import BaseModel

from .ClinicalSessionIn import ClinicalSessionIn
from .SystemMetadataIn import SystemMetadataIn


# final full event accepted by POST /events
# mirrors the SDK's ComplianceObject, but is declared here so the backend does not import the SDK
class EventRequest(BaseModel):
    event_id: str                           # unique id, created by the SDK
    timestamp: datetime                     # when the SDK logged the event, in UTC
    system: SystemMetadataIn
    clinical_session: ClinicalSessionIn
