# radar_edge_uploader_guaxx.py
# Monitorea archivos .nc4 del radar GUAXX y los sincroniza con la API Cloud vía REST.
#
# - La API Key se lee de un archivo .env junto a este script (o de la variable de
#   entorno RADAR_API_KEY). Si no hay clave, el servicio aborta en vez de arrancar
#   con un secreto por defecto.
# - API_URL y el directorio a vigilar también se pueden fijar en .env, de modo que
#   para actualizar el nodo basta copiar los .py sin tocar el .env local.

import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import json
import sys

# ============================================================================
# CARGA DE CONFIGURACIÓN DESDE .env (sin dependencias externas)
# ============================================================================

def load_env(env_path):
    """Carga pares CLAVE=VALOR de un archivo .env al entorno del proceso.
    No sobrescribe variables ya presentes en el entorno. Ignora comentarios
    (#) y líneas vacías. Sin dependencia de python-dotenv."""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"Advertencia: no se pudo leer {env_path}: {e}")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_env(os.path.join(SCRIPT_DIR, '.env'))

# ============================================================================
# CONFIGURACIÓN DEL RADAR GUAXX (valores sensibles / de nodo vienen de .env)
# ============================================================================

# URL de la API Central (fijar RADAR_API_URL en .env para producción).
API_URL = os.environ.get('RADAR_API_URL', 'http://localhost:8000')

# Clave de seguridad: OBLIGATORIA vía .env / entorno (debe coincidir con
# RADAR_API_KEY del servidor). Sin valor por defecto: si falta, el servicio no
# arranca (ver verificación en __main__).
API_KEY = os.environ.get('RADAR_API_KEY', '').strip()

RADAR_ID = 'guaxx'
WATCH_DIR = os.environ.get(
    'GUAXX_WATCH_DIR',
    r'D:\Rainview-Analyzer\Rainview-Analyzer\rainbow\online\RS19\100km.ppi'
)
PROCESSOR_SCRIPT = os.environ.get('GUAXX_PROCESSOR_SCRIPT', './generar_png_radar.py')
OUTPUT_PNG_PATH = os.environ.get('GUAXX_OUTPUT_PNG', r'./output/radar_latest.png')

# Parámetros de detección
STABLE_CHECKS = 3
STABLE_INTERVAL_SEC = 1.0
FILE_EXT = '.nc4'

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def is_file_stable(path, checks=STABLE_CHECKS, interval=STABLE_INTERVAL_SEC):
    """
    Espera hasta que el tamaño del archivo sea estable 'checks' veces seguidas.
    Esto asegura que el archivo ha terminado de escribirse/transferirse.
    """
    if not os.path.exists(path):
        return False
    try:
        prev = os.path.getsize(path)
    except OSError:
        return False

    stable_count = 0
    while stable_count < checks:
        time.sleep(interval)
        try:
            cur = os.path.getsize(path)
        except OSError:
            return False
        if cur == prev:
            stable_count += 1
        else:
            stable_count = 0
        prev = cur
    return True

def snapshot_existing(root, ext):
    """Devuelve un set con todos los archivos existentes (para ignorarlos al inicio)."""
    try:
        return {
            os.path.join(root, f)
            for f in os.listdir(root)
            if f.lower().endswith(ext)
        }
    except FileNotFoundError:
        return set()

# ============================================================================
# CLASE PRINCIPAL DE MONITOREO
# ============================================================================

class RadarEdgeUploader(FileSystemEventHandler):
    def __init__(self, api_url, api_key, radar_id, processor_script, output_png, known_paths):
        self.api_url = api_url
        self.api_key = api_key
        self.radar_id = radar_id
        self.processor_script = processor_script
        self.output_png = output_png
        self.known = known_paths
        self.processing = False

    def get_timestamps(self, filename):
        """Extrae fecha y hora del nombre del archivo .nc4 (formato: YYYYMMDDHHMMdBuZ...)"""
        try:
            base = filename.split("dBuZ")[0]
            if len(base) >= 12:
                dt_utc = datetime(
                    int(base[:4]), int(base[4:6]), int(base[6:8]),
                    int(base[8:10]), int(base[10:12])
                )
                return dt_utc, dt_utc - timedelta(hours=5)
        except Exception:
            pass

        utc = datetime.utcnow()
        return utc, utc - timedelta(hours=5)

    def read_generated_metadata(self):
        """
        Lee bounds y center desde el metadata JSON generado por generar_png_radar.py.
        Esto asegura que los bounds siempre coincidan con la imagen real.
        """
        metadata_path = os.path.join(
            os.path.dirname(self.output_png),
            "radar_latest_metadata.json"
        )
        try:
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    meta = json.load(f)
                return meta.get('bounds'), meta.get('center')
        except Exception as e:
            print(f"Advertencia: No se pudo leer metadata generado: {e}")

        # Fallback: bounds aproximados del radar GUAXX
        return [[-4.9333, -80.7667], [-3.1333, -78.9667]], [-4.0333, -79.8667]

    def upload_to_api(self, local_png_path, original_filename):
        """Sube el PNG generado a la API central (con API Key)."""
        dt_utc, dt_local = self.get_timestamps(original_filename)

        # Leer bounds reales desde el metadata generado por generar_png_radar.py
        bounds, center = self.read_generated_metadata()

        metadata = {
            "timestamp_utc": dt_utc.strftime('%Y-%m-%d %H:%M:%S'),
            "timestamp_local": dt_local.strftime('%Y-%m-%d %H:%M:%S'),
            "data_type": "DBZH",
            "bounds": bounds,
            "center": center
        }

        # Usar 'with' para asegurar que el file handle se cierra correctamente
        try:
            with open(local_png_path, 'rb') as f:
                ts_filename = f"radar_{self.radar_id}_{dt_local.strftime('%Y%m%d%H%M%S')}.png"
                files = {'file': (ts_filename, f, 'image/png')}
                data = {'metadata': json.dumps(metadata)}
                headers = {'X-Api-Key': self.api_key}

                print(f"Sincronizando con {self.api_url}...")
                response = requests.post(
                    f"{self.api_url}/upload/{self.radar_id}",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=30
                )

            if response.status_code == 201:
                print(f"[OK] Radar {self.radar_id.upper()} actualizado.")
                return True
            else:
                print(f"[ERROR] API falló: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"[ERROR] Error de red: {e}")
            return False

    def process_new_file(self, file_path):
        """Detección -> Estabilización -> Procesamiento -> Sincronización API"""
        if not file_path.lower().endswith(FILE_EXT) or file_path in self.known:
            return

        if self.processing:
            print(f"En proceso, saltando {os.path.basename(file_path)}")
            return

        self.processing = True
        try:
            print(f"\n{'='*60}")
            print(f"NUEVO DATO GUAXX: {os.path.basename(file_path)}")

            # 1. Esperar estabilidad real
            print("Esperando estabilidad del archivo...")
            if not is_file_stable(file_path):
                print("Archivo no alcanzó estabilidad, saltando")
                return

            print(f"[OK] Archivo estable y listo para procesar")
            self.known.add(file_path)

            # 2. Invocar script de procesamiento de radar
            print("Generando imagen de reflectividad...")
            res = subprocess.run(
                [sys.executable, self.processor_script, "--file", file_path],
                capture_output=True, text=True, timeout=300
            )

            if res.returncode == 0 and os.path.exists(self.output_png):
                if self.upload_to_api(self.output_png, os.path.basename(file_path)):
                    print(f"PROCESADO Y ENVIADO exitosamente.")
            else:
                print(f"Error en procesamiento (código {res.returncode}):")
                if res.stderr:
                    print(res.stderr[-500:])
        except subprocess.TimeoutExpired:
            print("Timeout en procesamiento (>5 min)")
        except Exception as e:
            print(f"Error inesperado: {e}")
        finally:
            self.processing = False
            print(f"{'='*60}\n")

    def on_created(self, event):
        if not event.is_directory: self.process_new_file(event.src_path)
    def on_moved(self, event):
        if not event.is_directory: self.process_new_file(event.dest_path)

# ============================================================================
# INICIO DEL SERVICIO EDGE
# ============================================================================

if __name__ == "__main__":
    # Verificación de clave: sin API Key, no se arranca (evita usar un secreto
    # por defecto y evita subir datos con credenciales inválidas).
    if not API_KEY:
        print("[FATAL] Falta la API Key. Crea un archivo '.env' junto a este")
        print("        script (copia .env.example) con la línea:")
        print("            RADAR_API_KEY=<la_clave_real>")
        print("        o define la variable de entorno RADAR_API_KEY. Abortando.")
        sys.exit(1)

    print(f"GUAXX EDGE SERVICE")
    print(f"Vigilando ruta: {WATCH_DIR}")
    print(f"API destino: {API_URL}")

    # Snapshot inicial: ignorar archivos preexistentes
    known = snapshot_existing(WATCH_DIR, FILE_EXT)
    if known:
        print(f"Ignorando {len(known)} archivo(s) preexistente(s)")

    handler = RadarEdgeUploader(API_URL, API_KEY, RADAR_ID, PROCESSOR_SCRIPT, OUTPUT_PNG_PATH, known)

    observer = Observer()
    observer.schedule(handler, path=WATCH_DIR, recursive=True)
    observer.start()

    print("Esperando nuevos archivos .nc4...\n")

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo sistema Edge...")
        observer.stop()
    observer.join()
