from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from .routers import events, views

app = FastAPI(title="IVOA Central Cloud API")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")

# Montar archivos estáticos si la carpeta existe
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Incluir las rutas modulares
app.include_router(events.router, prefix="/v1/events", tags=["events"])
app.include_router(views.router, tags=["views"])
