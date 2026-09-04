# generar_png_radar.py
"""
Genera un PNG RGBA (con transparencia) desde un archivo .nc4 del radar GUAXX.

Escala de color: LUT discreta Furuno WR110 v8 (jet), 8-70 dBZ, 13 clases,
la misma que usan el nodo LOXX, el visor y las figuras del paper. Los valores
< 8 dBZ (MIN_DBZH_THRESHOLD) son transparentes.

NOTA: GUAXX no corrige clutter, por lo que parte del eco >= 8 dBZ puede ser
clutter de terreno sin filtrar.

Detalles del pipeline:
- Orientación north-up: si la latitud viene ascendente (sur->norte) se aplica
  flip vertical; no se aplica rotación de 90°.
- Geotransform con bordes de píxel vía rasterio.transform.from_origin().
- Metadata Leaflet: bounds [[lat_min, lon_min], [lat_max, lon_max]] y center [lat, lon].
- Permite procesar un archivo específico: --file /ruta/al/archivo.nc4
"""

import os
import sys
import json
import numpy as np
import netCDF4 as nc
import rasterio
from rasterio.transform import from_origin
from PIL import Image
from datetime import datetime, timedelta
from pathlib import Path
import configparser
import argparse
from pyproj import Transformer

# =============================================================================
# CONFIG
# =============================================================================

NODATA = -9999.0

# Umbral inferior (dBZ): por debajo, transparente. Unifica el piso con LOXX.
MIN_DBZH_THRESHOLD = 8.0

# Escala de reflectividad OFICIAL Furuno WR110 (familia jet), 10-70 dBZ paso 5
# (12 clases) + clase inferior 8-10 dBZ (navy). 13 clases. LUT ÚNICA compartida
# por LOXX, GUAXX y la leyenda del visor (VISOR/src/config/radars.js). Los hex
# DEBEN ser idénticos entre los tres. Si cambia uno, cambiar los otros.
DBZH_LEVELS = [8, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
DBZH_COLORS = [
    (0, 0, 128),      # 8-10   navy (eco débil; piso = umbral 8 dBZ)
    (0, 0, 180),      # 10-15  azul oscuro
    (0, 96, 255),     # 15-20  azul
    (0, 200, 240),    # 20-25  cian / turquesa
    (0, 224, 160),    # 25-30  verde-cian
    (0, 200, 0),      # 30-35  verde
    (128, 224, 0),    # 35-40  verde-amarillo
    (255, 240, 0),    # 40-45  amarillo
    (255, 192, 0),    # 45-50  ámbar
    (255, 128, 0),    # 50-55  naranja
    (255, 56, 0),     # 55-60  rojo-naranja
    (224, 0, 0),      # 60-65  rojo
    (144, 0, 0),      # 65-70  rojo oscuro
]
assert len(DBZH_COLORS) == len(DBZH_LEVELS) - 1, "colores != intervalos"

def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists("config.ini"):
        print("Error: No se encontró el archivo config.ini")
        sys.exit(1)
    config.read("config.ini")
    return config

config = load_config()

# Radar / I/O
BASE_INPUT = config["RADAR"]["base_input"]
RESOLUCION = config["RADAR"]["resolution"]
BASE_OUTPUT = config["PROCESSING"]["output_dir"]
OUTPUT_PNG_NAME = config["PROCESSING"]["output_png_name"]
AJUSTE_HORA_MAQUINA = int(config["RADAR"].get("machine_time_adjustment", "0"))

# Geo
CRS_RADAR = config["GEO"].get("crs_radar", "EPSG:4326")

# Centro (Leaflet usa [lat, lon])
CENTER_LAT = float(config["GEO"].get("center_lat", "-3.9960"))
CENTER_LON = float(config["GEO"].get("center_lon", "-79.2058"))

# Conversión a dBZ
DBZH_GAIN = float(config["RADAR"]["dbzh_gain"])
DBZH_OFFSET = float(config["RADAR"]["dbzh_offset"])

# Rotación (DEPRECADA aquí: si no es 0, solo avisamos)
ROTATION_DEGREES = float(config["PROCESSING"].get("rotation_degrees", "0"))

def extraer_fecha_hora(nombre_archivo: str):
    """Extrae fecha y hora (UTC) del nombre del archivo .nc4: YYYYMMDDHHMM..."""
    try:
        base = nombre_archivo.split("dBuZ")[0]
        if len(base) >= 12:
            year = int(base[:4])
            month = int(base[4:6])
            day = int(base[6:8])
            hour = int(base[8:10])
            minute = int(base[10:12])
            return datetime(year, month, day, hour, minute)
    except Exception:
        pass
    return None

def format_timestamp_for_display(dt_utc: datetime):
    """Formato para visor: UTC y LT (Ecuador UTC-5)"""
    utc_str = dt_utc.strftime("%Y-%m-%d %H:%M UTC")
    dt_local = dt_utc - timedelta(hours=5)
    lt_str = dt_local.strftime("%Y-%m-%d %H:%M LT")
    return f"{utc_str} ({lt_str})"

def convertir_bounds_a_latlon(bounds, src_crs: str):
    """
    Convierte bounds (left,bottom,right,top) del CRS src_crs a EPSG:4326 y devuelve:
    Leaflet bounds: [[lat_min, lon_min], [lat_max, lon_max]]
    """
    left, bottom, right, top = bounds  # x_min, y_min, x_max, y_max

    # Si ya está en 4326, no transformamos
    if str(src_crs).upper().replace(" ", "") in ("EPSG:4326", "4326"):
        return [[bottom, left], [top, right]]

    transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    lon_sw, lat_sw = transformer.transform(left, bottom)
    lon_ne, lat_ne = transformer.transform(right, top)
    return [[lat_sw, lon_sw], [lat_ne, lon_ne]]

def convertir_raw_a_dbz(radar_raw: np.ndarray, fill_value=0):
    """
    Convierte raw (0..255) a dBZ usando fórmula: dBZ = raw*GAIN + OFFSET
    Donde fill_value se convierte a NODATA.
    """
    radar = radar_raw.astype(np.float32)

    # fill_value a NaN
    radar = np.where(radar == fill_value, np.nan, radar)

    dbz = np.full(radar.shape, NODATA, dtype=np.float32)
    mask = ~np.isnan(radar) & (radar >= 0) & (radar <= 255)
    if np.any(mask):
        dbz[mask] = radar[mask] * DBZH_GAIN + DBZH_OFFSET
    return dbz

def asegurar_orientacion_north_up(dbz: np.ndarray, lat: np.ndarray, lon: np.ndarray):
    """
    Asegura:
    - lon ascendente (oeste->este)
    - lat descendente (norte->sur) para que fila 0 sea el norte (north-up)
    Aplica flip en el array dbz cuando sea necesario.
    """
    lat_fixed = np.array(lat, dtype=np.float64)
    lon_fixed = np.array(lon, dtype=np.float64)
    dbz_fixed = dbz

    # Lon descendente -> flip horizontal
    if lon_fixed.size > 1 and lon_fixed[1] < lon_fixed[0]:
        lon_fixed = lon_fixed[::-1]
        dbz_fixed = np.fliplr(dbz_fixed)

    # Lat ascendente (sur->norte) -> flip vertical para north-up
    if lat_fixed.size > 1 and lat_fixed[1] > lat_fixed[0]:
        lat_fixed = lat_fixed[::-1]
        dbz_fixed = np.flipud(dbz_fixed)

    return dbz_fixed, lat_fixed, lon_fixed

def construir_transform_desde_latlon(lat: np.ndarray, lon: np.ndarray):
    """
    Construye transform Affine asumiendo lat/lon como centros de píxel,
    con datos ya en orientación north-up (lat descendente, lon ascendente).
    """
    if lon.size < 2 or lat.size < 2:
        raise ValueError("lon/lat deben tener al menos 2 elementos para calcular resolución.")

    dx = float(lon[1] - lon[0])
    dy = float(abs(lat[1] - lat[0]))  # positivo

    # Bordes (si lon/lat son centros)
    west = float(lon[0] - dx / 2.0)
    north = float(lat[0] + dy / 2.0)

    transform = from_origin(west, north, dx, dy)  # dy positivo, internamente crea -dy en Affine
    return transform

def convertir_a_imagen_vectorizado(datos_dbz: np.ndarray):
    """
    Convierte dBZ a RGBA con la escala DISCRETA Furuno WR110 (v8), unificada con
    LOXX y la leyenda del visor. Cada celda se asigna al intervalo
    [DBZH_LEVELS[i], DBZH_LEVELS[i+1]) y toma DBZH_COLORS[i]. Transparente en
    NODATA y por debajo de MIN_DBZH_THRESHOLD (8 dBZ). Misma lógica de
    rasterizado que visualize_dbzh_transparent de LOXX.
    """
    valido = (datos_dbz != NODATA) & (datos_dbz >= MIN_DBZH_THRESHOLD) & ~np.isnan(datos_dbz)
    if not np.any(valido):
        return None

    altura, ancho = datos_dbz.shape

    # Índice de color por celda; se recorta a 0..len(DBZH_COLORS)-1.
    bin_idx = np.digitize(datos_dbz, DBZH_LEVELS) - 1
    bin_idx = np.clip(bin_idx, 0, len(DBZH_COLORS) - 1)

    lut = np.array(DBZH_COLORS, dtype=np.uint8)          # (N, 3)
    rgba = np.zeros((altura, ancho, 4), dtype=np.uint8)
    rgba[..., :3] = lut[bin_idx]                          # color por bin
    rgba[..., 3] = np.where(valido, 255, 0).astype(np.uint8)  # alfa
    rgba[~valido, :3] = 0                                 # limpiar RGB donde es transparente

    return Image.fromarray(rgba, "RGBA")

def procesar_nc4(filepath: str):
    """Lee el .nc4 y devuelve: dbz (north-up), transform, bounds_leaflet, dt_utc, dimensiones"""
    dataset = nc.Dataset(filepath, "r")
    try:
        if "Band1" not in dataset.variables:
            raise ValueError("No existe variable 'Band1' en el archivo")

        band1 = dataset.variables["Band1"]
        fill_value = getattr(band1, "_FillValue", 0)

        raw = band1[:]
        dbz = convertir_raw_a_dbz(raw, fill_value=fill_value)

        if "lat" not in dataset.variables or "lon" not in dataset.variables:
            raise ValueError("No se encontraron variables 'lat' y 'lon' en el NetCDF")

        lat = dataset.variables["lat"][:]
        lon = dataset.variables["lon"][:]

        # Orientación correcta
        dbz, lat, lon = asegurar_orientacion_north_up(dbz, lat, lon)

        # Transform correcto
        transform = construir_transform_desde_latlon(lat, lon)

        # Bounds del raster (en CRS_RADAR)
        h, w = dbz.shape
        bounds = rasterio.transform.array_bounds(h, w, transform)  # (left,bottom,right,top)

        # Bounds para Leaflet (EPSG:4326)
        bounds_leaflet = convertir_bounds_a_latlon(bounds, CRS_RADAR)

        # Fecha/hora desde nombre (UTC)
        dt_utc = extraer_fecha_hora(os.path.basename(filepath))
        if dt_utc is None:
            dt_utc = datetime.utcnow()

        return dbz, transform, bounds_leaflet, dt_utc, (w, h)

    finally:
        dataset.close()

def encontrar_ultimo_archivo():
    """
    Encuentra el .nc4 más reciente dentro de la carpeta por fecha.
    Para evitar problemas en cambio de día, busca hoy y ayer.
    """
    ahora = datetime.now() + timedelta(hours=AJUSTE_HORA_MAQUINA)
    candidatos = []

    data_dir = os.path.join(BASE_INPUT, f"{RESOLUCION}km.ppi")

    for delta_days in (0, 1):  # hoy y ayer
        carpeta = (ahora - timedelta(days=delta_days)).strftime("%Y-%m-%d")
        carpeta_path = Path(data_dir) / carpeta
        if not carpeta_path.is_dir():
            continue

        for p in carpeta_path.glob("*.nc4"):
            dt = extraer_fecha_hora(p.name)
            if dt:
                candidatos.append((dt, str(p)))

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: x[0], reverse=True)
    return candidatos[0]

def guardar_outputs(imagen: Image.Image, dt_utc: datetime, bounds_leaflet, dims_wh, filepath_nc4: str):
    os.makedirs(BASE_OUTPUT, exist_ok=True)

    timestamp_utc = dt_utc.strftime("%Y%m%d%H%M%S")
    dt_local = dt_utc - timedelta(hours=5)
    timestamp_local = dt_local.strftime("%Y%m%d%H%M%S")

    output_filename = f"{timestamp_utc}.png"
    output_path = os.path.join(BASE_OUTPUT, output_filename)

    # Guardar PNG con timestamp
    imagen.save(output_path, "PNG", optimize=False, compress_level=1)

    # Guardar latest
    latest_path = os.path.join(BASE_OUTPUT, OUTPUT_PNG_NAME)
    imagen.save(latest_path, "PNG", optimize=False, compress_level=1)

    # Metadata
    metadata = {
        "radar_id": "guaxx",
        "source_nc4": os.path.basename(filepath_nc4),
        "timestamp_utc": timestamp_utc,
        "timestamp_local": timestamp_local,
        "datetime_utc": dt_utc.strftime("%Y-%m-%d %H:%M"),
        "datetime_local": dt_local.strftime("%Y-%m-%d %H:%M"),
        "formatted_time": format_timestamp_for_display(dt_utc),

        "bounds": bounds_leaflet,           # [[lat_min, lon_min], [lat_max, lon_max]]
        "center": [CENTER_LAT, CENTER_LON], # [lat, lon] correcto para Leaflet
        "crs": str(CRS_RADAR),

        "dimensions": {"width": dims_wh[0], "height": dims_wh[1]},
        "file": output_filename,

        "orientation_fix": "flip_vertical_if_lat_ascending",
        "rotation_degrees": 0
    }

    metadata_path = os.path.join(BASE_OUTPUT, f"{timestamp_utc}_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    latest_metadata_path = os.path.join(BASE_OUTPUT, "radar_latest_metadata.json")
    with open(latest_metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("[OK] PNG creado exitosamente")
    print(f"  Archivo:   {output_path}")
    print(f"  Latest:    {latest_path}")
    print(f"  Metadata:  {metadata_path}")
    print(f"  Bounds:    {bounds_leaflet}")
    print(f"  Center:    {metadata['center']} (Leaflet [lat, lon])")
    print("=" * 60 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Genera PNG del radar desde .nc4")
    parser.add_argument("--file", help="Ruta del archivo .nc4 a procesar (si no se da, procesa el más reciente)")
    args = parser.parse_args()

    if ROTATION_DEGREES != 0:
        print(f"[AVISO] rotation_degrees={ROTATION_DEGREES} en config.ini, pero este pipeline NO rota.")
        print("        La rotación rompe la georreferenciación en Leaflet. Se forzará a 0.\n")

    if args.file:
        filepath = args.file
        if not os.path.exists(filepath):
            print(f"Error: No existe el archivo: {filepath}")
            sys.exit(2)
        dt_guess = extraer_fecha_hora(os.path.basename(filepath))
        print("=== Generando PNG (archivo específico) ===")
        print(f"Archivo: {os.path.basename(filepath)}")
        if dt_guess:
            print(f"Fecha (UTC) desde nombre: {dt_guess.strftime('%Y-%m-%d %H:%M')}")
    else:
        print("=== Generando PNG del último archivo detectado ===")
        ultimo = encontrar_ultimo_archivo()
        if not ultimo:
            print("No se encontró ningún archivo .nc4 para procesar.")
            sys.exit(3)
        _, filepath = ultimo
        print(f"Archivo más reciente: {os.path.basename(filepath)}")

    # Procesar
    dbz, transform, bounds_leaflet, dt_utc, dims_wh = procesar_nc4(filepath)

    # Convertir a imagen
    img = convertir_a_imagen_vectorizado(dbz)
    if img is None:
        print("Error: No hay datos válidos para convertir a imagen.")
        sys.exit(4)

    # Guardar
    guardar_outputs(img, dt_utc, bounds_leaflet, dims_wh, filepath)

if __name__ == "__main__":
    main()