import cv2
import numpy as np
import mss
import time
import os
import threading

def record_screen(filename="demo_ivoa.mp4", fps=15.0):
    with mss.mss() as sct:
        # Obtener el monitor principal
        monitor = sct.monitors[1]
        width = monitor["width"]
        height = monitor["height"]
        
        # Configurar el codec para MP4 compatible con WhatsApp (H.264)
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        
        print("\n" + "="*50)
        print(f"🔴 GRABANDO PANTALLA COMPLETA ({width}x{height}) A {fps} FPS")
        print("="*50)
        print(f"Archivo de salida: {os.path.abspath(filename)}")
        print("\n⚠️ IMPORTANTE: Ve a tu navegador y haz la demostracion.")
        print("Cuando termines, regresa a esta consola de texto y...")
        
        stop_event = threading.Event()
        
        def wait_for_enter():
            input("\n👉 PRESIONA LA TECLA [ENTER] AQUI PARA DETENER LA GRABACION...\n")
            stop_event.set()
            
        t = threading.Thread(target=wait_for_enter)
        t.start()
        
        frame_time = 1.0 / fps
        frames_recorded = 0
        
        while not stop_event.is_set():
            start_t = time.time()
            
            # Capturar la pantalla completa
            img = np.array(sct.grab(monitor))
            
            # Convertir colores de BGRA (formato de mss) a BGR (formato de OpenCV)
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Escribir frame al video
            out.write(frame)
            frames_recorded += 1
            
            # Dormir para mantener los FPS consistentes
            elapsed = time.time() - start_t
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)
                
        out.release()
        print("\n" + "="*50)
        print(f"✅ Grabacion terminada. Total frames: {frames_recorded}")
        print(f"🎥 Video guardado con exito en: {os.path.abspath(filename)}")
        print("="*50 + "\n")

if __name__ == "__main__":
    try:
        record_screen()
    except KeyboardInterrupt:
        print("\nGrabación interrumpida por el usuario.")
