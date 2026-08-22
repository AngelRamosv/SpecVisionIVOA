import sqlite3
import json
import os
from datetime import datetime

DB_NAME = "ivoa.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa la base de datos y crea la tabla de eventos si no existe."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            details TEXT,
            severity TEXT DEFAULT 'info'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS sesiones_personas (
            id_persona INTEGER PRIMARY KEY,
            primera_vez_visto DATETIME,
            entro_a_fila DATETIME,
            salio_de_fila DATETIME,
            entro_a_modulo DATETIME,
            salio_de_modulo DATETIME,
            estado TEXT,
            tiempo_total_atencion_segundos INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def log_event(event_type, details=None, severity="info"):
    """Registra un nuevo evento en la base de datos."""
    conn = get_db_connection()
    c = conn.cursor()
    details_json = json.dumps(details) if details else None
    
    # Obtener el tiempo local exacto en formato ISO para la BD
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute(
        "INSERT INTO events (timestamp, event_type, details, severity) VALUES (?, ?, ?, ?)",
        (now_str, event_type, details_json, severity)
    )
    conn.commit()
    conn.close()

def get_recent_events(limit=10):
    """Obtiene los últimos eventos registrados para mostrarlos en el dashboard."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, timestamp, event_type, details, severity FROM events ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    events = []
    for row in rows:
        events.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "event_type": row["event_type"],
            "details": json.loads(row["details"]) if row["details"] else None,
            "severity": row["severity"]
        })
    return events


def upsert_sesion_persona(tracker_id, session_data):
    """Inserta o actualiza una sesión de persona en la base de datos."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Verificar si existe
    c.execute("SELECT id_persona FROM sesiones_personas WHERE id_persona = ?", (tracker_id,))
    exists = c.fetchone()
    
    if not exists:
        c.execute('''
            INSERT INTO sesiones_personas (id_persona, primera_vez_visto, entro_a_fila, salio_de_fila, entro_a_modulo, salio_de_modulo, estado, tiempo_total_atencion_segundos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tracker_id, 
            session_data.get('first_seen'), 
            session_data.get('entered_fila'), 
            session_data.get('left_fila'), 
            session_data.get('entered_modulo'), 
            session_data.get('left_modulo'), 
            session_data.get('status', 'detectado'), 
            session_data.get('total_service_time')
        ))
    else:
        c.execute('''
            UPDATE sesiones_personas 
            SET primera_vez_visto = COALESCE(?, primera_vez_visto),
                entro_a_fila = COALESCE(?, entro_a_fila),
                salio_de_fila = COALESCE(?, salio_de_fila),
                entro_a_modulo = COALESCE(?, entro_a_modulo),
                salio_de_modulo = COALESCE(?, salio_de_modulo),
                estado = COALESCE(?, estado),
                tiempo_total_atencion_segundos = COALESCE(?, tiempo_total_atencion_segundos)
            WHERE id_persona = ?
        ''', (
            session_data.get('first_seen'), 
            session_data.get('entered_fila'), 
            session_data.get('left_fila'), 
            session_data.get('entered_modulo'), 
            session_data.get('left_modulo'), 
            session_data.get('status'), 
            session_data.get('total_service_time'),
            tracker_id
        ))
    
    conn.commit()
    conn.close()

