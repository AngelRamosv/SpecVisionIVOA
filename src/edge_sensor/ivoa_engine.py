import time
from datetime import datetime
import cv2
import numpy as np
import warnings
import supervision as sv
from ultralytics import YOLO

def extract_color_signature(frame, bbox):
    """Extrae una huella digital matemática basada en los colores de la ropa"""
    x1, y1, x2, y2 = map(int, bbox)
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
        
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    return hist

class IVOAVisionEngine:
    """Motor de IA Central: Maneja Modelos, Tracking, Zonas y Reglas de Negocio"""
    def __init__(self, width, height, frame_skip=5):
        self.width = width
        self.height = height
        self.FRAME_SKIP = frame_skip
        
        # 1. Carga de Arquitectura Doble Cerebro (Cascade)
        self.model_base = YOLO("yolov8n.pt") # Rastreador universal
        self.model_custom = YOLO("yolov8_ivoa_v2.pt") # Inspector de objetos
        
        # 2. Configuración Espacial
        self.modulo_polygon = np.array([[0, 0], [width, 0], [width, height//2], [0, height//2]])
        self.fila_polygon = np.array([[0, height//2], [width, height//2], [width, height], [0, height]])
        
        self.fila_zone = sv.PolygonZone(polygon=self.fila_polygon, triggering_anchors=[sv.Position.CENTER])
        self.modulo_zone = sv.PolygonZone(polygon=self.modulo_polygon, triggering_anchors=[sv.Position.CENTER])
        self.line_zone = sv.LineZone(
            start=sv.Point(0, height // 2), 
            end=sv.Point(width, height // 2), 
            triggering_anchors=[sv.Position.CENTER]
        )
        
        # 3. Módulos de Procesamiento y Anotación
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.tracker = sv.ByteTrack()

        self.box_annotator = sv.BoxAnnotator()
        self.label_annotator = sv.LabelAnnotator()
        self.trace_annotator = sv.TraceAnnotator(trace_length=20)
        self.line_zone_annotator = sv.LineZoneAnnotator()
        self.blur_annotator = sv.BlurAnnotator(kernel_size=15)
        
        # 4. Estado Interno (Memoria y Métricas)
        self.id_map = {}
        self.persistent_identities = {}
        self.track_history = {}
        self.first_client_seen = False
        
        self.in_count = 0
        self.out_count = 0
        self.fila_count = 0
        self.modulo_count = 0
        self.alerta_saturacion = False
        self.saturacion_frames = 0
        
        self.last_alert_time = 0
        self.last_alert_uniforme = 0
        
        self.last_detections = sv.Detections.empty()
        self.last_detections_tracked = sv.Detections.empty()

    def process_frame(self, frame, frame_count):
        """Procesa un fotograma y devuelve la imagen dibujada junto con las alertas disparadas"""
        alerts = []
        sessions_to_update = []
        annotated = frame.copy()
        
        # Solo procesar detecciones pesadas cada N frames (Frame Skip)
        if frame_count % self.FRAME_SKIP == 0:
            
            # --- FASE 1: DETECCIÓN EN CASCADA ---
            result_base = self.model_base(frame, verbose=False, imgsz=320)[0]
            detections_base = sv.Detections.from_ultralytics(result_base)
            detections_base = detections_base[detections_base.class_id == 0] # Solo Humanos
            
            result_custom = self.model_custom(frame, verbose=False, imgsz=320)[0]
            detections = sv.Detections.from_ultralytics(result_custom)
            
            # --- FASE 2: MOTOR DE REGLAS Y ALERTAS ---
            current_time = time.time()
            if current_time - self.last_alert_time > 10:
                if 2 in detections.class_id:
                    alerts.append(("incidencia_rv_conteo", "ALERTA: Billetes o efectivo expuesto detectado en el módulo.", "warning"))
                    self.last_alert_time = current_time
                elif 4 in detections.class_id:
                    alerts.append(("incidencia_alimentos", "ALERTA: Consumo de alimentos/bebidas detectado.", "warning"))
                    self.last_alert_time = current_time
                elif 5 in detections.class_id:
                    alerts.append(("incidencia_celular", "ALERTA: Uso de dispositivo móvil (Celular) detectado en horario laboral.", "warning"))
                    self.last_alert_time = current_time
                    
            if len(detections_base) > 0:
                if current_time - self.last_alert_uniforme > 10:
                    c_classes = detections.class_id
                    # Regla Estricta: Obligatorio tener playera(1), pantalon(0) y zapatos(3)
                    if not (0 in c_classes and 1 in c_classes and 3 in c_classes):
                        alerts.append(("incidencia_uniforme", "ALERTA: Uniforme incompleto o vestimenta informal detectada (Falta playera, pantalón o zapatos).", "warning"))
                        self.last_alert_uniforme = current_time
            
            # --- FASE 3: TRACKING Y RE-IDENTIFICACIÓN ---
            detections_tracked = self.tracker.update_with_detections(detections_base)
            
            if detections_tracked.tracker_id is not None:
                new_tracker_ids = []
                current_time_epoch = time.time()
                active_mapped_ids = set()
                
                for tid, bbox in zip(detections_tracked.tracker_id, detections_tracked.xyxy):
                    signature = extract_color_signature(frame, bbox)
                    mapped_tid = self.id_map.get(tid, tid)
                    
                    if mapped_tid not in self.persistent_identities and signature is not None:
                        best_match_id = None
                        best_match_score = -1
                        for old_tid, old_data in self.persistent_identities.items():
                            if old_tid in active_mapped_ids: continue
                            if current_time_epoch - old_data['last_seen'] > 300: continue
                            if old_data['signature'] is not None:
                                score = cv2.compareHist(signature, old_data['signature'], cv2.HISTCMP_CORREL)
                                if score > 0.85 and score > best_match_score:
                                    best_match_score = score
                                    best_match_id = old_tid
                                    
                        if best_match_id is not None:
                            self.id_map[tid] = best_match_id
                            mapped_tid = best_match_id
                            alerts.append(("reid_success", f"Persona recuperada: ID {mapped_tid} restaurado tras pérdida de vista.", "info"))
                        else:
                            self.id_map[tid] = tid
                            mapped_tid = tid
                            
                    self.persistent_identities[mapped_tid] = {'signature': signature, 'last_seen': current_time_epoch}
                    active_mapped_ids.add(mapped_tid)
                    new_tracker_ids.append(mapped_tid)
                    
                detections_tracked.tracker_id = np.array(new_tracker_ids)
                
            # --- FASE 4: ANÁLISIS ESPACIAL Y FLUJOS ---
            self.line_zone.trigger(detections=detections_tracked)
            self.in_count = self.line_zone.in_count
            self.out_count = self.line_zone.out_count
            
            fila_in = self.fila_zone.trigger(detections=detections_tracked)
            modulo_in = self.modulo_zone.trigger(detections=detections_tracked)
            
            self.fila_count = np.sum(fila_in)
            self.modulo_count = np.sum(modulo_in)
            
            self.alerta_saturacion = bool(self.fila_count > 3)
            if self.alerta_saturacion:
                self.saturacion_frames += self.FRAME_SKIP
                if self.saturacion_frames > 30:
                    current_time = time.time()
                    if current_time - self.last_alert_time > 60:
                        alerts.append(("queue_threshold_exceeded", f"Fila saturada ({int(self.fila_count)}), considere abrir otro módulo", "warning"))
                        alerts.append(("finding_created", "Sugerimos abrir ventanilla para desahogar la fila.", "error"))
                        self.last_alert_time = current_time
            else:
                self.saturacion_frames = 0
                
            # Mantenimiento de Sesiones
            if detections_tracked.tracker_id is not None:
                current_ids = set()
                current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                current_time_epoch = time.time()
                
                for tid, in_f, in_m in zip(detections_tracked.tracker_id, fila_in, modulo_in):
                    current_ids.add(tid)
                    
                    if tid not in self.track_history:
                        self.track_history[tid] = {
                            'first_seen': current_time_str,
                            'last_seen_epoch': current_time_epoch,
                            'entered_fila': current_time_str if in_f else None,
                            'left_fila': None,
                            'entered_modulo': current_time_str if in_m else None,
                            'left_modulo': None,
                            'status': 'detectado',
                            'total_service_time': None
                        }
                        if not self.first_client_seen:
                            self.first_client_seen = True
                            now = datetime.now()
                            if now.hour > 9 or (now.hour == 9 and now.minute > 15):
                                alerts.append(("late_opening", f"Primer cliente detectado a las {now.strftime('%H:%M:%S')}. Apertura tardía.", "warning"))
                                
                    session = self.track_history[tid]
                    session['last_seen_epoch'] = current_time_epoch
                    
                    if in_f and not session['entered_fila']:
                        session['entered_fila'] = current_time_str
                        session['status'] = 'en_fila'
                    if not in_f and session['entered_fila'] and not session['left_fila']:
                        session['left_fila'] = current_time_str
                    if in_m and not session['entered_modulo']:
                        session['entered_modulo'] = current_time_str
                        session['status'] = 'en_modulo'
                    if not in_m and session['entered_modulo'] and not session['left_modulo']:
                        session['left_modulo'] = current_time_str
                        session['status'] = 'atendido'
                        fmt = "%Y-%m-%d %H:%M:%S"
                        t_in = datetime.strptime(session['entered_modulo'], fmt)
                        t_out = datetime.strptime(session['left_modulo'], fmt)
                        session['total_service_time'] = int((t_out - t_in).total_seconds())
                        alerts.append(("service_completed", f"Servicio completado en {session['total_service_time']}s", "info"))
                        sessions_to_update.append((int(tid), session.copy()))
                        
                tids_to_remove = []
                for tid, session in self.track_history.items():
                    if tid not in current_ids:
                        if current_time_epoch - session['last_seen_epoch'] > 60:
                            if session['entered_fila'] and not session['entered_modulo']:
                                session['status'] = 'abandonado'
                                if not session['left_fila']:
                                    session['left_fila'] = datetime.fromtimestamp(session['last_seen_epoch']).strftime("%Y-%m-%d %H:%M:%S")
                                alerts.append(("customer_abandonment", "Cliente se retiró sin ser atendido tras 60s", "warning"))
                            sessions_to_update.append((int(tid), session.copy()))
                            tids_to_remove.append(tid)
                for tid in tids_to_remove:
                    del self.track_history[tid]
                    
            self.last_detections = detections
            self.last_detections_tracked = detections_tracked
            
        else:
            # Reutilizar el cálculo del frame anterior para mantener fluidez
            detections = self.last_detections
            detections_tracked = self.last_detections_tracked
            
        # --- FASE 5: DIBUJADO VISUAL ---
        if len(detections) > 0:
            head_xyxy = detections.xyxy.copy()
            head_xyxy[:, 3] = head_xyxy[:, 1] + (head_xyxy[:, 3] - head_xyxy[:, 1]) * 0.45
            head_detections = sv.Detections(xyxy=head_xyxy)
            annotated = self.blur_annotator.annotate(scene=annotated, detections=head_detections)
            
        labels = []
        for class_id, confidence in zip(detections.class_id, detections.confidence):
            labels.append(f"{self.model_custom.names[class_id]} {confidence:.2f}")
            
        annotated = self.box_annotator.annotate(scene=annotated, detections=detections)
        annotated = self.label_annotator.annotate(scene=annotated, detections=detections, labels=labels)
        
        if hasattr(detections_tracked, 'tracker_id') and detections_tracked.tracker_id is not None:
            annotated = self.box_annotator.annotate(scene=annotated, detections=detections_tracked)
            tracked_labels = [f"Empleado ID: {tid}" for tid in detections_tracked.tracker_id]
            annotated = self.label_annotator.annotate(scene=annotated, detections=detections_tracked, labels=tracked_labels)
            annotated = self.trace_annotator.annotate(scene=annotated, detections=detections_tracked)
            
        self.line_zone_annotator.annotate(annotated, line_counter=self.line_zone)
        cv2.polylines(annotated, [self.fila_polygon], isClosed=True, color=(15, 196, 241), thickness=2)
        cv2.polylines(annotated, [self.modulo_polygon], isClosed=True, color=(219, 152, 52), thickness=2)
        
        cv2.putText(annotated, f"Zona Modulo: {int(self.modulo_count)}", (20, self.height//2 - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (219, 152, 52), 2)
        cv2.putText(annotated, f"Zona Fila: {int(self.fila_count)}", (20, self.height//2 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 196, 241), 2)
        
        return annotated, alerts, sessions_to_update
