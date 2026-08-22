import json
import os
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime, timedelta
from .database import get_db, SesionPersona, Evento, Hallazgo, Usuario

app = FastAPI(title="IVOA Central Cloud API")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

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

@app.post("/v1/events/session")
def update_session(payload: PersonSessionPayload, db: Session = Depends(get_db)):
    # Función equivalente a db.upsert_sesion_persona
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

@app.post("/v1/events/log")
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

    # Crear hallazgo automáticamente si el evento es crítico
    if payload.event_type in ["finding_created", "queue_threshold_exceeded", "late_opening", "customer_abandonment"]:
        if payload.event_type == "late_opening":
            cat = "Apertura Tardía"
        elif payload.event_type == "customer_abandonment":
            cat = "Abandono de Cliente"
        elif payload.event_type == "queue_threshold_exceeded":
            cat = "Saturación de Fila"
        else:
            cat = "Acción Requerida"
            
        nuevo_hallazgo = Hallazgo(
            evento_id=nuevo_evento.id,
            categoria=cat,
            estado="DETECTADO",
            severidad=payload.severity,
            fecha_creacion=datetime.now(),
            fecha_vencimiento=datetime.now() + timedelta(minutes=15) # SLA 15 min
        )
        db.add(nuevo_hallazgo)
        db.commit()

    return {"status": "success"}

@app.get("/v1/events/log")
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

@app.get("/v1/events/session")
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

class StatusUpdatePayload(BaseModel):
    status: str

@app.get("/v1/findings")
def get_findings(limit: int = 10, db: Session = Depends(get_db)):
    hallazgos = db.query(Hallazgo).order_by(Hallazgo.fecha_creacion.desc()).limit(limit).all()
    resultado = []
    for h in hallazgos:
        resultado.append({
            "id": h.id,
            "evento_id": h.evento_id,
            "categoria": h.categoria,
            "estado": h.estado,
            "severidad": h.severidad,
            "fecha_creacion": h.fecha_creacion.strftime("%Y-%m-%d %H:%M:%S") if h.fecha_creacion else None,
            "fecha_vencimiento": h.fecha_vencimiento.strftime("%Y-%m-%d %H:%M:%S") if h.fecha_vencimiento else None,
            "fecha_cierre": h.fecha_cierre.strftime("%Y-%m-%d %H:%M:%S") if h.fecha_cierre else None,
            "asignado_a": h.asignado_a
        })
    return resultado

@app.delete("/v1/findings")
def delete_all_findings(db: Session = Depends(get_db)):
    db.query(Hallazgo).delete()
    db.commit()
    return {"status": "success", "message": "Todos los tickets han sido eliminados."}

@app.put("/v1/findings/{finding_id}/status")
def update_finding_status(finding_id: int, payload: StatusUpdatePayload, db: Session = Depends(get_db)):
    hallazgo = db.query(Hallazgo).filter(Hallazgo.id == finding_id).first()
    if not hallazgo:
        raise HTTPException(status_code=404, detail="Hallazgo no encontrado")
    
    hallazgo.estado = payload.status
    if payload.status == "CERRADO":
        hallazgo.fecha_cierre = datetime.now()
        
    db.commit()
    return {"status": "success", "nuevo_estado": hallazgo.estado}

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("ivoa_session")
    if not session_token:
        raise HTTPException(status_code=401, detail="No autenticado")
    user = db.query(Usuario).filter(Usuario.username == session_token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")
    return user

@app.get("/")
def read_root():
    return RedirectResponse(url="/dashboard")

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/login")
def login_post(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.username == username, Usuario.password == password).first()
    if not user:
        return RedirectResponse(url="/login?error=1", status_code=303)
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="ivoa_session", value=user.username, httponly=True)
    return response

@app.get("/logout")
@app.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("ivoa_session")
    return response

@app.get("/dashboard")
def get_dashboard(request: Request, db: Session = Depends(get_db)):
    # Redirigir a login si no hay token
    session_token = request.cookies.get("ivoa_session")
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
        
    user = db.query(Usuario).filter(Usuario.username == session_token).first()
    if not user:
         return RedirectResponse(url="/login", status_code=303)
         
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"username": user.username})
