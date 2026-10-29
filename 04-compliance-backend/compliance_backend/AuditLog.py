from sqlalchemy import Column, DateTime, Float, JSON, String

from .database import Base

# one row per stored audit event, the values arrive inside the event sent by the SDK, so nothing is generated here
class AuditLog(Base):

    __tablename__ = "audit_logs"

    event_id = Column(String, primary_key=True)         # unique id, a repeated id is rejected
    timestamp = Column(DateTime, nullable=False)        # when the SDK logged the event, in UTC

    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)

    input_data_hash = Column(String, nullable=False)    # SHA-256 fingerprint of the input, shall be chained
    prediction = Column(JSON)                           # the model output, a dictionary
    confidence = Column(Float)                          # optional, some models give no score

    execution_time_ms = Column(Float, nullable=False)   # how long the inference took
    signature = Column(String)                          # added by the backend before saving
