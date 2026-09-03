import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ..database import get_db, SesionPersona, Evento, Hallazgo
from ..schemas import PersonSessionPayload, EventoPayload

router = APIRouter()

@router.post("/session")
def update_session(payload: PersonSessionPayload, db: Session = Depends(get_db)):
    db_session = db.query(SesionPersona).filter(SesionPersona.id_persona == payload.tracker_id).first()
    
    def parse_dt(dt_str):
        if not dt_str:
            return None
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

    data = payload.session_data
    if not db_session:
        db_session = SesionPersona(
            id_persona=payload.tracker_id,
            primera_vez_visto=parse_dt(data.first_seen),
            entro_a_fila=parse_dt(data.entered_fila),
            salio_de_fila=parse_dt(data.left_fila),
            entro_a_modulo=parse_dt(data.entered_modulo),
            salio_de_modulo=parse_dt(data.left_modulo),
            estado=data.status,
            tiempo_total_atencion_segundos=data.total_service_time
        )
        db.add(db_session)
    else:
        if data.first_seen: db_session.primera_vez_visto = parse_dt(data.first_seen)
        if data.entered_fila: db_session.entro_a_fila = parse_dt(data.entered_fila)
        if data.left_fila: db_session.salio_de_fila = parse_dt(data.left_fila)
        if data.entered_modulo: db_session.entro_a_modulo = parse_dt(data.entered_modulo)
        if data.left_modulo: db_session.salio_de_modulo = parse_dt(data.left_modulo)
        if data.status: db_session.estado = data.status
        if data.total_service_time is not None: db_session.tiempo_total_atencion_segundos = data.total_service_time
        
    db.commit()
    return {"status": "success"}

@router.post("/log")
def log_event(payload: EventoPayload, db: Session = Depends(get_db)):
    nuevo_evento = Evento(
        event_type=payload.event_type,
        timestamp=datetime.now(),
        details=json.dumps(payload.details),
        severity=payload.severity
    )
    db.add(nuevo_evento)
    db.commit()
    db.refresh(nuevo_evento)

    critical_events = [
        "finding_created", "queue_threshold_exceeded", "late_opening", "customer_abandonment",
        "incidencia_rv_conteo", "incidencia_alimentos", "incidencia_celular", "incidencia_uniforme"
    ]
    if payload.event_type in critical_events:
        if payload.event_type == "late_opening":
            cat = "Apertura Tardía"
        elif payload.event_type == "customer_abandonment":
            cat = "Abandono de Cliente"
        elif payload.event_type == "queue_threshold_exceeded":
            cat = "Saturación de Fila"
        elif payload.event_type == "incidencia_uniforme":
            cat = "Uniforme Incompleto"
        elif payload.event_type == "incidencia_celular":
            cat = "Uso de Celular"
        elif payload.event_type == "incidencia_alimentos":
            cat = "Consumo de Alimentos"
        elif payload.event_type == "incidencia_rv_conteo":
            cat = "Efectivo Expuesto"
        else:
            cat = "Acción Requerida"
            
        nuevo_hallazgo = Hallazgo(
            evento_id=nuevo_evento.id,
            categoria=cat,
            estado="DETECTADO",
            severidad=payload.severity,
            fecha_creacion=datetime.now(),
            fecha_vencimiento=datetime.now() + timedelta(minutes=15)
        )
        db.add(nuevo_hallazgo)
        db.commit()

    return {"status": "success"}

@router.get("/log")
def get_events(limit: int = 5, db: Session = Depends(get_db)):
    eventos = db.query(Evento).order_by(Evento.timestamp.desc()).limit(limit).all()
    resultado = []
    for ev in eventos:
        try:
            detalles_dict = json.loads(ev.details)
        except:
            detalles_dict = {}
        resultado.append({
            "id": ev.id,
            "event_type": ev.event_type,
            "timestamp": ev.timestamp.strftime("%Y-%m-%d %H:%M:%S") if ev.timestamp else None,
            "details": detalles_dict,
            "severity": ev.severity
        })
    return resultado

@router.get("/session")
def get_sessions(limit: int = 10, db: Session = Depends(get_db)):
    sesiones = db.query(SesionPersona).order_by(SesionPersona.primera_vez_visto.desc()).limit(limit).all()
    resultado = []
    for s in sesiones:
        resultado.append({
            "id_rastreo": s.id_persona,
            "primera_vez_visto": s.primera_vez_visto.strftime("%Y-%m-%d %H:%M:%S") if s.primera_vez_visto else None,
            "estado": s.estado,
            "tiempo_total_servicio_segundos": s.tiempo_total_atencion_segundos,
            "entro_a_fila": s.entro_a_fila.strftime("%Y-%m-%d %H:%M:%S") if s.entro_a_fila else None,
            "salio_de_fila": s.salio_de_fila.strftime("%Y-%m-%d %H:%M:%S") if s.salio_de_fila else None,
            "entro_a_modulo": s.entro_a_modulo.strftime("%Y-%m-%d %H:%M:%S") if s.entro_a_modulo else None,
            "salio_de_modulo": s.salio_de_modulo.strftime("%Y-%m-%d %H:%M:%S") if s.salio_de_modulo else None
        })
    return resultado
