import cv2
import os
import shutil
import time

def procesar_videos():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    dataset_dir = os.path.join(desktop, "Dataset_IVOA_Crudo")
    videos_dir = os.path.join(dataset_dir, "videos")
    images_dir = os.path.join(dataset_dir, "images")

    os.makedirs(videos_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)

    print(f"Creando carpeta contenedora en: {dataset_dir}")

    # 1. Mover los videos para no contaminar
    video_files = ["actuacion.mp4", "vestimenta.mp4"]
    for v in video_files:
        src = os.path.join(desktop, v)
        dst = os.path.join(videos_dir, v)
        if os.path.exists(src):
            print(f"Moviendo {v} a la nueva carpeta...")
            shutil.move(src, dst)
        elif not os.path.exists(dst):
            print(f"No se encontro {v} en el escritorio.")

    from ultralytics import YOLO
    # Inicializar el bloqueador facial usando YOLO (censura del 25% superior del cuerpo)
    print("Cargando filtro de Privacidad (YOLOv8 Head Blur)...")
    model = YOLO("yolov8n.pt")

    def extract_frames(video_name):
        vid_path = os.path.join(videos_dir, video_name)
        if not os.path.exists(vid_path):
            return
            
        print(f"Extrayendo imagenes de {video_name}...")
        cap = cv2.VideoCapture(vid_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps is None: fps = 30.0 # Por defecto
        
        frame_count = 0
        saved_count = 0
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            # Guardar 1 frame por cada segundo de video aprox
            if frame_count % int(fps) == 0:
                # Deteccion de personas para censurar la cabeza (25% superior)
                results = model(frame, classes=[0], verbose=False)
                for r in results:
                    for box in r.boxes.xyxy:
                        x1, y1, x2, y2 = map(int, box)
                        # Calcular el 25% superior del bounding box (la cabeza/rostro)
                        head_bottom = y1 + int((y2 - y1) * 0.25)
                        face_roi = frame[y1:head_bottom, x1:x2]
                        if face_roi.size > 0:
                            face_roi = cv2.blur(face_roi, (55, 55)) 
                            frame[y1:head_bottom, x1:x2] = face_roi
                    
                # Guardar la foto
                out_path = os.path.join(images_dir, f"{video_name.split('.')[0]}_frame_{saved_count:04d}.jpg")
                cv2.imwrite(out_path, frame)
                saved_count += 1
                
            frame_count += 1
            
        cap.release()
        elapsed = int(time.time() - start_time)
        print(f"Listo: {video_name}. Se extrajeron {saved_count} fotos en {elapsed} segundos.")

    # Ejecutar extracción
    for v in video_files:
        extract_frames(v)
        
    print("\nPASO 1 TERMINADO! Todo esta en la carpeta 'Dataset_IVOA_Crudo' en tu Escritorio.")

if __name__ == "__main__":
    procesar_videos()
