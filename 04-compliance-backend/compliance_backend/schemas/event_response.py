from datetime import datetime

from pydantic import BaseModel, ConfigDict


# the stored event which is returned by the API
# the fields match the columns of the AuditLog table
class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    timestamp: datetime
    model_name: str
    model_version: str
    input_data_hash: str
    prediction: dict[str, str] | None
    confidence: float | None
    execution_time_ms: float
    signature: str | None
