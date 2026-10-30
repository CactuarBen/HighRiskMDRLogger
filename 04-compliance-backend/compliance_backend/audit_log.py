from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


# one row per stored audit event, the values arrive inside the event sent by the SDK, so nothing is generated here
class AuditLog(Base):

    __tablename__ = "audit_logs"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)         # unique id, a repeated id is rejected
    timestamp: Mapped[datetime] = mapped_column(DateTime)        # when the SDK logged the event, in UTC

    model_name: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)

    input_data_hash: Mapped[str] = mapped_column(String)    # SHA-256 fingerprint of the input, shall be chained
    prediction: Mapped[dict[str, Any] | None] = mapped_column(JSON)                           # the model output, a dictionary
    confidence: Mapped[float | None] = mapped_column(Float)                          # optional, some models give no score

    execution_time_ms: Mapped[float] = mapped_column(Float)   # how long the inference took
    signature: Mapped[str | None] = mapped_column(String)                          # added by the backend before saving
