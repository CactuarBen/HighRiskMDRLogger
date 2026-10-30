from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .audit_log import AuditLog
from .database import Base, engine, get_db
from .schemas.event_request import EventRequest
from .schemas.event_response import EventResponse
from .signing import sign

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Compliance Backend")


# incoming POST request that tells backend to create, then sign, then persist a record into db
@app.post("/events", response_model=EventResponse, status_code=201)
def create_event(event: EventRequest, db: Session = Depends(get_db)) -> AuditLog:
    signature = sign(event.event_id, 
                     event.timestamp, 
                     event.system.model_name, 
                     event.system.model_version, 
                     event.clinical_session.input_data_hash)
    audit_log = AuditLog(event_id=event.event_id, 
                         timestamp=event.timestamp, 
                         model_name=event.system.model_name, 
                         model_version=event.system.model_version, 
                         input_data_hash=event.clinical_session.input_data_hash, 
                         rediction=event.clinical_session.inference_result.prediction, 
                         confidence=event.clinical_session.inference_result.confidence, 
                         execution_time=event.clinical_session.inference_result.execution_time_ms, 
                         signature=signature)
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log

# incoming GET request that requests to present a specific event by ID
@app.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: str, db: Session = Depends(get_db)) -> AuditLog:
    audit_log = db.get(AuditLog, event_id)
    if audit_log is None:
        raise HTTPException(status_code=404, detail="Event not found, make sure the event id is correct")
    return audit_log

# incoming GET request that requests to show all the persisted events
@app.get("/events", response_model=list[EventResponse])
def list_events(db: Session = Depends(get_db)) -> list[AuditLog]:
    audit_log_all_events = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    return audit_log_all_events