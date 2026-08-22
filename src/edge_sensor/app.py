import os
import warnings
import time
import threading

# Suprimir mensajes de FFmpeg
os.environ["OPENCV_LOG_LEVEL"] = "0"
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"

import cv2
from flask import Flask, Response, render_template, jsonify
from ultralytics import YOLO
import supervision as sv
import numpy as np
from datetime import datetime

import db

app = Flask(__name__)

# Inicializar base de datos
db.init_db()
db.log_event("system_started", {"message": "Motor IVOA iniciado"}, "info")

# --- Estado global compartido entre el hilo de detección y Flask ---
frame_lock = threading.Lock()
latest_frame = None
in_count = 0
out_count = 0
fila_count = 0
modulo_count = 0
alerta_saturacion = False
camera_connected = False
running = True

# Variables para control de eventos
last_alert_time = 0
saturacion_frames = 0
camera_logged = False

# Usar webcam de la laptop local (índice 0)
CAMERA_URL = 0


def detection_thread():
    """Hilo en segundo plano: lee la cámara, detecta personas y actualiza el frame."""
    global latest_frame, in_count, out_count, fila_count, modulo_count, alerta_saturacion, camera_connected
    global last_alert_time, saturacion_frames, camera_logged

    model = YOLO("yolov8n.pt")

    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Línea horizontal centrada (cámara apuntando a la puerta)
    START = sv.Point(0, height // 2)
    END = sv.Point(width, height // 2)
    line_zone = sv.LineZone(
        start=START,
        end=END,
        triggering_anchors=[sv.Position.CENTER]
    )

    # Polígonos de zonas (División Horizontal)
    # Módulo: Toda la mitad SUPERIOR de la pantalla
    modulo_polygon = np.array([[0, 0], [width, 0], [width, height//2], [0, height//2]])
    # Fila: Toda la mitad INFERIOR de la pantalla
    fila_polygon = np.array([[0, height//2], [width, height//2], [width, height], [0, height]])

    # Usar el centro del bounding box para no depender de ver los pies
    fila_zone = sv.PolygonZone(polygon=fila_polygon, triggering_anchors=[sv.Position.CENTER])
    modulo_zone = sv.PolygonZone(polygon=modulo_polygon, triggering_anchors=[sv.Position.CENTER])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tracker = sv.ByteTrack()

    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    trace_annotator = sv.TraceAnnotator(trace_length=20)
    line_zone_annotator = sv.LineZoneAnnotator()
    # Aumentamos el kernel_size a 55 para un desenfoque más fuerte de lejos
    blur_annotator = sv.BlurAnnotator(kernel_size=55)
    
    # Anotadores nuevos
    heatmap_annotator = sv.HeatMapAnnotator(position=sv.Position.BOTTOM_CENTER, opacity=0.5)

    FRAME_SKIP = 2
    frame_count = FRAME_SKIP - 1
    detections = sv.Detections.empty()
    
    track_history = {}
    first_client_seen = False

    while running:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.01)
            continue

        camera_connected = True
        if not camera_logged:
            db.log_event("camera_online", {"message": "Conexión con Cámara Establecida. Procesando video."}, "info")
            camera_logged = True

        frame_count += 1

        if frame_count % FRAME_SKIP == 0:
            result = model(frame, classes=[0], verbose=False, imgsz=320)[0]
            detections = sv.Detections.from_ultralytics(result)
            
            # Aplicar NMS para evitar contar doble a la misma persona si se acerca mucho
            detections = detections.with_nms(threshold=0.3)
            
            detections = tracker.update_with_detections(detections)
            line_zone.trigger(detections=detections)
            in_count = line_zone.in_count
            out_count = line_zone.out_count

            fila_in = fila_zone.trigger(detections=detections)
            modulo_in = modulo_zone.trigger(detections=detections)
            
            fila_count = np.sum(fila_in)
            modulo_count = np.sum(modulo_in)
            
            # Lógica de saturación y eventos IVOA
            alerta_saturacion = bool(fila_count > 3)
            
            if alerta_saturacion:
                saturacion_frames += FRAME_SKIP
                # Si han pasado aprox 30 frames detectados (~2-3 segundos) sostenidos
                if saturacion_frames > 30:
                    current_time = time.time()
                    # Cooldown de 60 segundos para evitar spam en base de datos
                    if current_time - last_alert_time > 60:
                        db.log_event(
                            "queue_threshold_exceeded", 
                            {"queue_length": int(fila_count), "message": f"Saturación sostenida con {int(fila_count)} personas formadas."}, 
                            "warning"
                        )
                        db.log_event(
                            "finding_created", 
                            {"queue_length": int(fila_count), "action_required": "Sugerimos abrir ventanilla para desahogar la fila."}, 
                            "error"
                        )
                        last_alert_time = current_time
            else:
                saturacion_frames = 0
                
            # --- Lógica Avanzada de Rastreo IVOA ---
            if detections.tracker_id is not None:
                current_ids = set()
                current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                current_time_epoch = time.time()
                
                for tid, in_fila, in_modulo in zip(detections.tracker_id, fila_in, modulo_in):
                    current_ids.add(tid)
                    
                    if tid not in track_history:
                        track_history[tid] = {
                            'first_seen': current_time_str,
                            'last_seen_epoch': current_time_epoch,
                            'entered_fila': current_time_str if in_fila else None,
                            'left_fila': None,
                            'entered_modulo': current_time_str if in_modulo else None,
                            'left_modulo': None,
                            'status': 'detectado',
                            'total_service_time': None
                        }
                        
                        if not first_client_seen:
                            first_client_seen = True
                            now = datetime.now()
                            # Alerta de apertura tardía (después de 9:15 AM)
                            if now.hour > 9 or (now.hour == 9 and now.minute > 15):
                                db.log_event("late_opening", {"message": f"Primer cliente detectado a las {now.strftime('%H:%M:%S')}. Apertura tardía."}, "warning")
                    
                    session = track_history[tid]
                    session['last_seen_epoch'] = current_time_epoch
                    
                    if in_fila and not session['entered_fila']:
                        session['entered_fila'] = current_time_str
                        session['status'] = 'en_fila'
                        
                    if not in_fila and session['entered_fila'] and not session['left_fila']:
                        session['left_fila'] = current_time_str
                        
                    if in_modulo and not session['entered_modulo']:
                        session['entered_modulo'] = current_time_str
                        session['status'] = 'en_modulo'
                        
                    if not in_modulo and session['entered_modulo'] and not session['left_modulo']:
                        # Salió del módulo de manera precisa
                        session['left_modulo'] = current_time_str
                        session['status'] = 'atendido'
                        fmt = "%Y-%m-%d %H:%M:%S"
                        t_in = datetime.strptime(session['entered_modulo'], fmt)
                        t_out = datetime.strptime(session['left_modulo'], fmt)
                        service_time = int((t_out - t_in).total_seconds())
                        session['total_service_time'] = service_time
                        db.log_event("service_completed", {"tracker_id": int(tid), "service_time_seconds": service_time}, "info")
                        db.upsert_sesion_persona(int(tid), session)
                        
                tids_to_remove = []
                for tid, session in track_history.items():
                    if tid not in current_ids:
                        time_since_last_seen = current_time_epoch - session['last_seen_epoch']
                        if time_since_last_seen > 60: # 60 segundos de gracia (Abandono)
                            if session['entered_fila'] and not session['entered_modulo']:
                                session['status'] = 'abandonado'
                                if not session['left_fila']:
                                    session['left_fila'] = datetime.fromtimestamp(session['last_seen_epoch']).strftime("%Y-%m-%d %H:%M:%S")
                                db.log_event("customer_abandonment", {"tracker_id": int(tid), "message": "Cliente se retiró sin ser atendido tras 60s"}, "warning")
                            # Guardar estado final en DB
                            db.upsert_sesion_persona(int(tid), session)
                            tids_to_remove.append(tid)
                
                for tid in tids_to_remove:
                    del track_history[tid]
            # --- Fin Lógica Avanzada ---

        # Dibujar mapa de calor en el fondo
        annotated = heatmap_annotator.annotate(scene=frame.copy(), detections=detections)

        # Difuminar rostro (estimación: 45% superior del bounding box para cubrir bien al estar cerca o agachado)
        if len(detections) > 0:
            head_xyxy = detections.xyxy.copy()
            head_xyxy[:, 3] = head_xyxy[:, 1] + (head_xyxy[:, 3] - head_xyxy[:, 1]) * 0.45
            head_detections = sv.Detections(xyxy=head_xyxy)
            annotated = blur_annotator.annotate(scene=annotated, detections=head_detections)

        # Dibujar anotaciones de personas
        if detections.tracker_id is not None:
            annotated = trace_annotator.annotate(scene=annotated, detections=detections)

        annotated = box_annotator.annotate(scene=annotated, detections=detections)

        labels = [f"ID: {tid}" for tid in detections.tracker_id] \
            if detections.tracker_id is not None else []
        annotated = label_annotator.annotate(scene=annotated, detections=detections, labels=labels)
        line_zone_annotator.annotate(annotated, line_counter=line_zone)
        
        # Dibujar zonas directamente con OpenCV (Evita errores de numpy en Supervision)
        cv2.polylines(annotated, [fila_polygon], isClosed=True, color=(15, 196, 241), thickness=2)  # Amarillo BGR
        cv2.polylines(annotated, [modulo_polygon], isClosed=True, color=(219, 152, 52), thickness=2) # Azul BGR
        
        # Etiqueta visual para módulo (Justo arriba de la línea central)
        cv2.putText(annotated, f"Zona Modulo: {int(modulo_count)}", (20, height//2 - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (219, 152, 52), 2)
        # Etiqueta visual para la fila (Justo debajo de la línea central)
        cv2.putText(annotated, f"Zona Fila: {int(fila_count)}", (20, height//2 + 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 196, 241), 2)

        with frame_lock:
            latest_frame = annotated

    cap.release()


def generate_frames():
    """Generador MJPEG para transmitir el video al navegador."""
    while True:
        with frame_lock:
            if latest_frame is None:
                time.sleep(0.05)
                continue
            ret, buffer = cv2.imencode('.jpg', latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not ret:
                continue
            frame_bytes = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
        )
        time.sleep(0.033)  # ~30 fps


# --- Rutas Flask ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/stats')
def stats():
    total = in_count + out_count
    inside = max(0, in_count - out_count)
    personas_en_toma = fila_count + modulo_count # Estimación simple
    
    return jsonify({
        'in_count': in_count,
        'out_count': out_count,
        'total': total,
        'inside': inside,
        'camera_connected': camera_connected,
        'fila_count': int(fila_count),
        'modulo_count': int(modulo_count),
        'personas_en_toma': int(personas_en_toma),
        'alerta_saturacion': alerta_saturacion
    })


@app.route('/api/events')
def api_events():
    events = db.get_recent_events(limit=5)
    return jsonify(events)


if __name__ == '__main__':
    # Iniciar hilo de detección en segundo plano
    t = threading.Thread(target=detection_thread, daemon=True)
    t.start()
    print("\n✅ Dashboard listo en: http://localhost:5000\n")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
