from pydantic import BaseModel
from typing import Optional, Any

class SessionData(BaseModel):
    first_seen: Optional[str] = None
    entered_fila: Optional[str] = None
    left_fila: Optional[str] = None
    entered_modulo: Optional[str] = None
    left_modulo: Optional[str] = None
    status: Optional[str] = "detectado"
    total_service_time: Optional[int] = None

class EventoPayload(BaseModel):
    event_type: str
    details: Any
    severity: str

class PersonSessionPayload(BaseModel):
    tracker_id: int
    session_data: SessionData

class StatusUpdatePayload(BaseModel):
    status: str
