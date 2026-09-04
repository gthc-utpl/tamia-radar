# radar_edge_uploader_loxx.py
# Monitorea nuevos archivos .h5.gz, los procesa y los envía al servidor vía API.
#
# 1. Seguridad: la API key se lee de variables de entorno (RADAR_API_KEY /
#    RADAR_API_URL) o de un uploader_config.ini local (excluido por .gitignore).
#    Si no hay clave, el proceso aborta en vez de enviar con un secreto por defecto.
#
# 2. Procesa el archivo detectado: pasa su ruta al generador
#    (generar_png_loxx.py <ruta>), evitando el desfase timestamp/imagen cuando
#    hay backlog de transferencias.
#
# 3. Cola de reintentos persistente: si la subida falla (red/API caída), el
#    frame se encola en disco y se reintenta en el siguiente ciclo.
#
# 4. is_file_stable con tope de tiempo.
#
# 5. 'center' en formato [lat, lon].
#
# 6. Rutas absolutas basadas en la ubicación del script.

import os
import sys
import json
import time
import math
import subprocess
import configparser
from pathlib import Path
from datetime import datetime, timedelta

import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

AQUI = os.path.dirname(os.path.abspath(__file__))

# ============================================================================
# CONFIGURACIÓN (sin secretos en el código)
# ============================================================================

def _load_local_config():
    """Lee uploader_config.ini junto al script, si existe (gitignored)."""
    cfg = configparser.ConfigParser()
    path = os.path.join(AQUI, 'uploader_config.ini')
    if os.path.exists(path):
        cfg.read(path)
    return cfg


_CFG = _load_local_config()


def _get(name, env, section='uploader', default=None):
    """Prioridad: variable de entorno > uploader_config.ini > default."""
    if env in os.environ and os.environ[env] != '':
        return os.environ[env]
    if _CFG.has_option(section, name):
        return _CFG.get(section, name)
    return default


API_URL = _get('api_url', 'RADAR_API_URL', default='http://localhost:8000')
API_KEY = _get('api_key', 'RADAR_API_KEY', default=None)   # SIN valor por defecto

RADAR_ID = _get('radar_id', 'RADAR_ID', default='loxx')
WATCH_DIR = _get('watch_dir', 'RADAR_WATCH_DIR', default=r'F:\LOXX\H5')
OUTPUT_DIR = _get('output_dir', 'RADAR_OUTPUT_DIR',
                  default=r'E:\RainfallMonitorV2\data\h5\output\png_individual')
PROCESSOR_SCRIPT = os.path.join(AQUI, 'generar_png_loxx.py')
OUTPUT_PNG_PATH = os.path.join(OUTPUT_DIR, 'radar_loxx_latest.png')
METADATA_PATH = os.path.join(OUTPUT_DIR, 'radar_loxx_latest_metadata.json')
RETRY_QUEUE_PATH = os.path.join(OUTPUT_DIR, 'upload_retry_queue.json')

# Parámetros de detección
STABLE_CHECKS = 3
STABLE_INTERVAL_SEC = 1.0
STABLE_MAX_WAIT_SEC = 120          # tope: nunca esperar más de esto
FILE_EXT = '.h5.gz'
UPLOAD_TIMEOUT_SEC = 30
PROCESS_TIMEOUT_SEC = 300

# Coordenadas fijas del radar (para el fallback de bounds)
LOXX_LAT, LOXX_LON = -3.989060, -79.145308
LOXX_RADIUS_KM = 94.9              # semiancho real del grid (474.5 px x 200 m)

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def is_file_stable(path, checks=STABLE_CHECKS, interval=STABLE_INTERVAL_SEC,
                   max_wait=STABLE_MAX_WAIT_SEC):
    """
    Espera a que el tamaño del archivo sea estable 'checks' veces seguidas,
    con un TOPE de tiempo total (max_wait) para no bloquearse indefinidamente.
    """
    if not os.path.exists(path):
        return False
    try:
        prev = os.path.getsize(path)
    except OSError:
        return False

    stable_count = 0
    start = time.time()
    while stable_count < checks:
        if time.time() - start > max_wait:
            print(f"  Tope de espera ({max_wait}s) alcanzado sin estabilidad")
            return False
        time.sleep(interval)
        try:
            cur = os.path.getsize(path)
        except OSError:
            return False
        stable_count = stable_count + 1 if cur == prev else 0
        prev = cur
    return True


def snapshot_existing(root, ext):
    try:
        return {os.path.join(root, f) for f in os.listdir(root)
                if f.lower().endswith(ext)}
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

    # ---- timestamps y metadata -------------------------------------------

    def extract_timestamps(self, filename):
        try:
            base = filename.replace('.h5.gz', '')
            parts = base.split('_')
            if len(parts) >= 3:
                date_part, time_part = parts[-2], parts[-1]
                if len(date_part) == 8 and len(time_part) == 6:
                    dt_utc = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
                    return dt_utc, dt_utc - timedelta(hours=5)
        except Exception as e:
            print(f"Error parseando timestamp de {filename}: {e}")
        utc = datetime.utcnow()
        return utc, utc - timedelta(hours=5)

    def read_generated_metadata(self):
        """Lee bounds/center/file del metadata JSON generado por el procesador."""
        try:
            if os.path.exists(METADATA_PATH):
                with open(METADATA_PATH, 'r') as f:
                    meta = json.load(f)
                return meta.get('bounds'), meta.get('center'), meta.get('file')
        except Exception as e:
            print(f"Advertencia: No se pudo leer metadata generado: {e}")

        # Fallback: bounds desde coordenadas fijas del radar. center = [lat, lon]
        # (consistente con el metadata normal; antes estaba invertido).
        lat_off = LOXX_RADIUS_KM / 111.320
        lon_off = LOXX_RADIUS_KM / (111.320 * math.cos(math.radians(LOXX_LAT)))
        bounds = [[LOXX_LAT - lat_off, LOXX_LON - lon_off],
                  [LOXX_LAT + lat_off, LOXX_LON + lon_off]]
        return bounds, [LOXX_LAT, LOXX_LON], None

    # ---- cola de reintentos ----------------------------------------------

    def _load_queue(self):
        try:
            if os.path.exists(RETRY_QUEUE_PATH):
                with open(RETRY_QUEUE_PATH, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Advertencia: cola de reintentos ilegible: {e}")
        return []

    def _save_queue(self, queue):
        try:
            with open(RETRY_QUEUE_PATH, 'w') as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            print(f"Advertencia: no se pudo guardar la cola: {e}")

    def _enqueue(self, entry):
        queue = self._load_queue()
        queue.append(entry)
        self._save_queue(queue)
        print(f"  Frame encolado para reintento ({len(queue)} pendiente(s))")

    def flush_queue(self):
        """Reintenta las subidas pendientes; conserva las que sigan fallando."""
        queue = self._load_queue()
        if not queue:
            return
        print(f"Reintentando {len(queue)} subida(s) pendiente(s)...")
        restantes = []
        for entry in queue:
            png = entry.get('png_path')
            if not png or not os.path.exists(png):
                print(f"  Descartado (PNG ausente): {png}")
                continue
            if not self._post(png, entry['metadata'], entry['ts_filename']):
                restantes.append(entry)
        self._save_queue(restantes)

    # ---- subida -----------------------------------------------------------

    def _post(self, png_path, metadata, ts_filename):
        """POST del PNG + metadata. Devuelve True si 201."""
        try:
            with open(png_path, 'rb') as f:
                files = {'file': (ts_filename, f, 'image/png')}
                data = {'metadata': json.dumps(metadata)}
                headers = {'X-Api-Key': self.api_key}
                print(f"Enviando a la API: {self.api_url}/upload/{self.radar_id}")
                r = requests.post(f"{self.api_url}/upload/{self.radar_id}",
                                  files=files, data=data, headers=headers,
                                  timeout=UPLOAD_TIMEOUT_SEC)
            if r.status_code == 201:
                print("[OK] Sincronización exitosa con el servidor central")
                return True
            print(f"[ERROR] API respondió: {r.status_code} - {r.text[:200]}")
            return False
        except Exception as e:
            print(f"[ERROR] No se pudo conectar con la API: {e}")
            return False

    def upload_to_api(self, original_h5gz_name):
        """Arma metadata y sube; encola si falla. Sube el PNG con timestamp
        (estable), no el 'latest' que puede sobrescribirse."""
        dt_utc, dt_local = self.extract_timestamps(original_h5gz_name)
        bounds, center, gen_file = self.read_generated_metadata()

        # Preferir el PNG con timestamp (estable frente a un nuevo frame)
        png_path = self.output_png
        if gen_file:
            candidate = os.path.join(OUTPUT_DIR, gen_file)
            if os.path.exists(candidate):
                png_path = candidate

        ts_filename = f"radar_{self.radar_id}_{dt_local.strftime('%Y%m%d%H%M%S')}.png"
        metadata = {
            "timestamp_utc": dt_utc.strftime('%Y-%m-%d %H:%M:%S'),
            "timestamp_local": dt_local.strftime('%Y-%m-%d %H:%M:%S'),
            "data_type": "DBZH",
            "bounds": bounds,
            "center": center,
        }

        if self._post(png_path, metadata, ts_filename):
            return True
        # Falló: encolar para reintento
        self._enqueue({'png_path': png_path, 'ts_filename': ts_filename,
                       'metadata': metadata})
        return False

    # ---- ciclo principal --------------------------------------------------

    def process_new_file(self, file_path):
        if not file_path.lower().endswith(FILE_EXT) or file_path in self.known:
            return
        if self.processing:
            print(f"Procesamiento en curso. Saltando: {os.path.basename(file_path)}")
            return

        self.processing = True
        try:
            print(f"\n{'='*60}")
            print(f"ARCHIVO DETECTADO: {os.path.basename(file_path)}")

            # 0. Reintentar pendientes antes de nada (aprovechar que hay red)
            self.flush_queue()

            # 1. Estabilidad (con tope de tiempo)
            print("Esperando estabilidad del archivo...")
            if not is_file_stable(file_path):
                print("Archivo no alcanzó estabilidad, saltando")
                return
            print("[OK] Archivo estable y listo para procesar")
            self.known.add(file_path)

            # 2. Generar PNG del ARCHIVO DETECTADO (pasa la ruta al procesador)
            print("Generando imagen PNG...")
            res = subprocess.run(
                [sys.executable, self.processor_script, file_path],
                capture_output=True, text=True, timeout=PROCESS_TIMEOUT_SEC
            )
            if res.returncode == 0 and os.path.exists(self.output_png):
                if self.upload_to_api(os.path.basename(file_path)):
                    print(f"CICLO COMPLETADO para {os.path.basename(file_path)}")
            else:
                print(f"FALLO en generación de PNG (código {res.returncode})")
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
        if not event.is_directory:
            self.process_new_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.process_new_file(event.dest_path)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    if not API_KEY:
        print("[FATAL] No hay API key. Define RADAR_API_KEY (variable de entorno)")
        print("        o api_key en uploader_config.ini. El proceso no continuará")
        print("        con un secreto por defecto por seguridad.")
        sys.exit(2)

    print(f"SISTEMA EDGE - RADAR {RADAR_ID.upper()}")
    print(f"Monitoreando: {WATCH_DIR}")
    print(f"API destino: {API_URL}")

    known = snapshot_existing(WATCH_DIR, FILE_EXT)
    if known:
        print(f"Ignorando {len(known)} archivo(s) preexistente(s)")

    handler = RadarEdgeUploader(API_URL, API_KEY, RADAR_ID, PROCESSOR_SCRIPT,
                                OUTPUT_PNG_PATH, known)
    # Reintentar pendientes al arrancar
    handler.flush_queue()

    observer = Observer()
    observer.schedule(handler, path=WATCH_DIR, recursive=False)
    observer.start()
    print("Esperando nuevos archivos .h5.gz...\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo sistema Edge...")
        observer.stop()
    observer.join()
