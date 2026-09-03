import cv2
import time
import os

# Cambia el 0 por la URL RTSP si quieres grabar de Hikvision directamente
CAMERA_SOURCE = 0 # 0 es tu cámara web de la laptop

def grabar_video(duracion_minutos=5):
    print(f"Iniciando cámara... Usa la ventana emergente para verte.")
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    
    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    # Configuraciones de guardado
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = 15.0 # FPS ideal para dataset
    
    ruta_guardado = os.path.join(os.path.expanduser("~"), "Desktop", "video_dataset_ivoa.mp4")
    cuatrocc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(ruta_guardado, cuatrocc, fps, (width, height))

    print("\n" + "="*50)
    print(f"LA GRABACIÓN HA COMENZADO.")
    print(f"Duración objetivo: {duracion_minutos} minutos.")
    print(f"El video se guardará en tu Escritorio como: video_dataset_ivoa.mp4")
    print("PRESIONA LA LETRA 'Q' EN TU TECLADO PARA DETENER LA GRABACIÓN ANTES DE TIEMPO.")
    print("="*50 + "\n")

    start_time = time.time()
    duracion_segundos = duracion_minutos * 60

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Guardar el frame en el archivo de video
        out.write(frame)

        # Mostrar tiempo transcurrido en la pantalla para que el usuario sepa que graba
        elapsed = int(time.time() - start_time)
        faltan = duracion_segundos - elapsed
        
        cv2.putText(frame, f"GRABANDO (Faltan {faltan} seg)", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("Grabadora de Dataset IVOA", frame)

        # Detener si presiona 'q' o se acaba el tiempo
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\nGrabación detenida por el usuario.")
            break
            
        if elapsed >= duracion_segundos:
            print("\n¡Tiempo completado!")
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"✅ VIDEO GUARDADO CON ÉXITO EN: {ruta_guardado}")

if __name__ == "__main__":
    grabar_video(5)
