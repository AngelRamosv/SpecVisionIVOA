import os
import warnings
# Suprimir mensajes de FFmpeg (stream HTTP de DroidCam)
os.environ["OPENCV_LOG_LEVEL"] = "0"
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
import cv2
from ultralytics import YOLO
import supervision as sv

def main():
    # 1. Cargar el modelo YOLOv8 nano (más rápido)
    model = YOLO("yolov8n.pt")

    # 2. Iniciar la cámara conectándose al celular a través de DroidCam
    cap = cv2.VideoCapture("http://192.168.137.222:4747/video")

    # ✅ OPTIMIZACIÓN: Reducir el buffer de video para evitar frames acumulados
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # 3. Obtener la resolución del video de la cámara
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 4. Configurar la línea virtual para contar (coordenadas x, y)
    # Línea HORIZONTAL en el centro de la pantalla
    # Usada cuando la cámara apunta de frente a la puerta
    START = sv.Point(0, height // 2)
    END = sv.Point(width, height // 2)
    line_zone = sv.LineZone(
        start=START,
        end=END,
        triggering_anchors=[sv.Position.CENTER]  # Usa el CENTRO del bounding box
    )

    # 5. Inicializar el tracker de supervision
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tracker = sv.ByteTrack()

    # 6. Configurar los anotadores visuales
    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    # ✅ OPTIMIZACIÓN: Reducir historial del trazo (línea morada) a 20 frames
    trace_annotator = sv.TraceAnnotator(trace_length=20)
    line_zone_annotator = sv.LineZoneAnnotator()
    # Aumentamos el kernel_size a 55 para un desenfoque más fuerte de lejos
    blur_annotator = sv.BlurAnnotator(kernel_size=55)

    print("Cámara iniciada. Presiona 'q' en la ventana para salir.")

    # ✅ OPTIMIZACIÓN: Procesar solo 1 de cada N frames para aliviar la CPU
    FRAME_SKIP = 2       # Ejecutar YOLO cada 2 frames
    # Iniciar en FRAME_SKIP-1 para que YOLO corra desde el primer frame
    frame_count = FRAME_SKIP - 1
    detections = sv.Detections.empty()  # Detecciones vacías al inicio

    while True:
        # Leer frame del stream de red
        ret, frame = cap.read()
        if not ret or frame is None:
            continue  # Si falla un frame, saltar al siguiente (no cerrar)

        frame_count += 1

        # Solo ejecutar YOLO cada FRAME_SKIP frames
        if frame_count % FRAME_SKIP == 0:
            # ✅ OPTIMIZACIÓN: Reducir el tamaño de imagen que procesa YOLO (320 en vez de 640)
            result = model(frame, classes=[0], verbose=False, imgsz=320)[0]

            # Convertir el resultado de YOLO a formato Supervision
            detections = sv.Detections.from_ultralytics(result)

            # Actualizar el tracker con las detecciones
            detections = tracker.update_with_detections(detections)

            # Contar cuántas personas cruzan la línea
            line_zone.trigger(detections=detections)

        # --- DIBUJAR EN EL FRAME (siempre, para que el video no se congele) ---
        # 0. Difuminar rostro (estimación: 45% superior del bounding box para cubrir bien al estar cerca o agachado)
        annotated_frame = frame.copy()
        if len(detections) > 0:
            head_xyxy = detections.xyxy.copy()
            head_xyxy[:, 3] = head_xyxy[:, 1] + (head_xyxy[:, 3] - head_xyxy[:, 1]) * 0.45
            head_detections = sv.Detections(xyxy=head_xyxy)
            annotated_frame = blur_annotator.annotate(scene=annotated_frame, detections=head_detections)

        # 1. Dibujar trazos del camino de las personas (línea morada)
        # Solo dibujar trazos si hay tracker_id disponible
        if detections.tracker_id is not None:
            annotated_frame = trace_annotator.annotate(
                scene=annotated_frame,
                detections=detections
            )

        # 2. Dibujar cajas delimitadoras (bounding boxes)
        annotated_frame = box_annotator.annotate(
            scene=annotated_frame,
            detections=detections
        )

        # 3. Agregar las etiquetas con el ID de la persona
        labels = [
            f"ID: {tracker_id}"
            for tracker_id in detections.tracker_id
        ] if detections.tracker_id is not None else []

        annotated_frame = label_annotator.annotate(
            scene=annotated_frame,
            detections=detections,
            labels=labels
        )

        # 4. Dibujar la línea virtual y los conteos (In / Out)
        line_zone_annotator.annotate(annotated_frame, line_counter=line_zone)

        # Mostrar el resultado final
        cv2.imshow("Contador de Personas", annotated_frame)

        # Si se presiona 'q', salir del bucle
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Liberar recursos
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
