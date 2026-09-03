import os
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db, Usuario, Hallazgo
from ..schemas import StatusUpdatePayload

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("ivoa_session")
    if not session_token:
        raise HTTPException(status_code=401, detail="No autenticado")
    user = db.query(Usuario).filter(Usuario.username == session_token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")
    return user

@router.get("/")
def read_root():
    return RedirectResponse(url="/dashboard")

@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@router.post("/login")
def login_post(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.username == username, Usuario.password == password).first()
    if not user:
        return RedirectResponse(url="/login?error=1", status_code=303)
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="ivoa_session", value=user.username, httponly=True)
    return response

@router.get("/logout")
@router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("ivoa_session")
    return response

@router.get("/dashboard")
def get_dashboard(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("ivoa_session")
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
        
    user = db.query(Usuario).filter(Usuario.username == session_token).first()
    if not user:
         return RedirectResponse(url="/login", status_code=303)
         
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"username": user.username})

@router.get("/v1/findings")
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

@router.delete("/v1/findings")
def delete_all_findings(db: Session = Depends(get_db)):
    db.query(Hallazgo).delete()
    db.commit()
    return {"status": "success", "message": "Todos los tickets han sido eliminados."}

@router.put("/v1/findings/{finding_id}/status")
def update_finding_status(finding_id: int, payload: StatusUpdatePayload, db: Session = Depends(get_db)):
    hallazgo = db.query(Hallazgo).filter(Hallazgo.id == finding_id).first()
    if not hallazgo:
        raise HTTPException(status_code=404, detail="Hallazgo no encontrado")
    
    hallazgo.estado = payload.status
    if payload.status == "CERRADO":
        hallazgo.fecha_cierre = datetime.now()
        
    db.commit()
    return {"status": "success", "nuevo_estado": hallazgo.estado}
