from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://ivoa_user:ivoa_password@localhost/ivoa_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class SesionPersona(Base):
    __tablename__ = "sesiones_personas"

    id_persona = Column(Integer, primary_key=True, index=True)
    primera_vez_visto = Column(DateTime, nullable=True)
    entro_a_fila = Column(DateTime, nullable=True)
    salio_de_fila = Column(DateTime, nullable=True)
    entro_a_modulo = Column(DateTime, nullable=True)
    salio_de_modulo = Column(DateTime, nullable=True)
    estado = Column(String, default="detectado")
    tiempo_total_atencion_segundos = Column(Integer, nullable=True)

class Evento(Base):
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String, index=True)
    timestamp = Column(DateTime)
    details = Column(String)  # Se guardará como JSON string
    severity = Column(String)

class Hallazgo(Base):
    __tablename__ = "hallazgos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    evento_id = Column(Integer, ForeignKey('eventos.id'))
    categoria = Column(String, index=True)
    estado = Column(String, default="DETECTADO", index=True)
    severidad = Column(String)
    fecha_creacion = Column(DateTime)
    fecha_vencimiento = Column(DateTime)
    asignado_a = Column(String, nullable=True)
    fecha_cierre = Column(DateTime, nullable=True)

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Función para sembrar el admin
def seed_admin():
    db = SessionLocal()
    try:
        admin = db.query(Usuario).filter(Usuario.username == "admin").first()
        if not admin:
            nuevo_admin = Usuario(username="admin", password="admin123")
            db.add(nuevo_admin)
            db.commit()
    finally:
        db.close()

# Sembrar admin al cargar el módulo
seed_admin()
