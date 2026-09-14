# generar_png_loxx.py
"""
Genera el PNG DBZH del radar LOXX a partir de un archivo .h5.gz.

Flujo: extracción DBZH (con enmascarado de 'undetect') -> filtro de mediana 2-D
-> corrección de clutter -> composite multi-elevación (nanmax) -> transformación
polar-cartesiana con límites geográficos (WGS84) -> rasterización RGBA con la
escala de color Furuno WR110 v8 -> PNG + metadata.

Los filtros inteligentes (textura/aislamiento) son opcionales y están
deshabilitados por defecto (apply_filters=False). Importa las funciones de
procesamiento de loxx_dbzh_georeferenciado.py.
"""

import os
import sys
import numpy as np
import gzip
import shutil
import tempfile
import glob
from datetime import datetime, timedelta
from io import BytesIO
import json
import warnings

# El PNG se rasteriza directamente con PIL (Pillow) a la resolución nativa de
# la malla (949x949, 1 píxel = 1 celda), preservando la correspondencia 1:1 con
# los límites geográficos.
from PIL import Image

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Importar funciones del módulo de procesamiento (misma carpeta)
try:
    from loxx_dbzh_georeferenciado import (
        extract_dbzh_data,
        apply_clutter_correction,
        apply_median_filter_2d,
        create_cartesian_data_optimized_new,
        fast_interpolate_small_gaps_optimized,
        apply_texture_filter,
        apply_isolation_filter,
        load_clutter_cache,
        generate_clutter_maps,
        save_clutter_cache,
        extract_timestamp_from_filename,
        load_config,
    )
    IMPORTS_OK = True
except ImportError as e:
    print(f"ADVERTENCIA: No se pudieron importar funciones de loxx_dbzh_georeferenciado.py: {e}")
    IMPORTS_OK = False

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

try:
    CONFIG = load_config('config.ini')
    SETTINGS = CONFIG['Settings']
    PROCESSING = CONFIG['RecentProcessing']

    RADAR_DIR = SETTINGS.get('radar_dir', 'F:/LOXX/H5')
    CLUTTER_DIR = SETTINGS.get('clutter_dir', 'F:/LOXX/Clutter/Reference')
    OUTPUT_DIR = os.path.join(SETTINGS.get('output_dir', 'E:/RainfallMonitorV2/data/h5/output'), 'png_individual')
    CLUTTER_CACHE_FILE = os.path.join(SETTINGS.get('output_dir', 'E:/RainfallMonitorV2/data/h5/output'), SETTINGS.get('clutter_cache_file', 'clutter_cache_dbzh.pkl'))
    REGENERATE_CLUTTER = SETTINGS.getboolean('regenerate_clutter', False)

    MIN_DBZH_THRESHOLD = PROCESSING.getfloat('min_dbzh_threshold', 8.0)
    CLUTTER_FACTOR = 1.3
    CLUTTER_METHOD = 'adaptive'
    RESOLUTION_FACTOR = 2
    ENABLE_SMART_FILTERS = PROCESSING.getboolean('apply_filters', False)
    PLOT_QUALITY = PROCESSING.get('plot_quality', 'medium')
    LOCK_TIMEOUT = SETTINGS.getint('lock_timeout', 60)

    print(f"Configuración cargada de config.ini")
    print(f"  Regenerate Clutter: {REGENERATE_CLUTTER}")
    print(f"  Min DBZH: {MIN_DBZH_THRESHOLD}")
    print(f"  Smart Filters: {ENABLE_SMART_FILTERS}")
    print(f"  Plot Quality: {PLOT_QUALITY}")

except Exception as e:
    print(f"Error cargando configuración: {e}")
    print("Usando valores por defecto...")

    RADAR_DIR = 'F:/LOXX/H5'
    CLUTTER_DIR = 'F:/LOXX/Clutter/Reference'
    OUTPUT_DIR = 'E:/RainfallMonitorV2/data/h5/output/png_individual'
    CLUTTER_CACHE_FILE = 'E:/RainfallMonitorV2/data/h5/output/clutter_cache_dbzh.pkl'
    REGENERATE_CLUTTER = False

    MIN_DBZH_THRESHOLD = 8.0
    CLUTTER_FACTOR = 1.3
    CLUTTER_METHOD = 'adaptive'
    RESOLUTION_FACTOR = 2
    ENABLE_SMART_FILTERS = False
    PLOT_QUALITY = 'medium'
    LOCK_TIMEOUT = 60

RADAR_INFO = {
    'id': 'loxx',
    'name': 'LOXX',
    'default_lat': -3.989060,
    'default_lon': -79.145308,
    'default_height': 2850.0
}

# ============================================================================
# FUNCIONES DE FILTROS INTELIGENTES (opcionales, deshabilitados por defecto)
# ============================================================================

def analyze_data_quality(cart_data, cart_metadata):
    nodata = cart_metadata['nodata']
    valid_mask = cart_data > nodata
    valid_count = np.sum(valid_mask)
    total_pixels = cart_data.size

    if valid_count == 0:
        return {'valid_count': 0, 'density': 0.0, 'mean_value': 0.0,
                'max_value': 0.0, 'spatial_spread': 0.0}

    density = valid_count / total_pixels
    mean_value = np.mean(cart_data[valid_mask])
    max_value = np.max(cart_data[valid_mask])

    y_indices, x_indices = np.where(valid_mask)
    if len(y_indices) > 0:
        y_spread = np.std(y_indices)
        x_spread = np.std(x_indices)
        spatial_spread = np.sqrt(y_spread**2 + x_spread**2)
    else:
        spatial_spread = 0.0

    return {'valid_count': valid_count, 'density': density, 'mean_value': mean_value,
            'max_value': max_value, 'spatial_spread': spatial_spread}


def should_apply_filters(cart_data, cart_metadata, min_pixels=50):
    metrics = analyze_data_quality(cart_data, cart_metadata)

    valid_count = metrics['valid_count']
    density = metrics['density']
    mean_value = metrics['mean_value']
    max_value = metrics['max_value']

    filter_config = {'apply_texture': False, 'apply_isolation': False,
                     'texture_threshold': 1.5, 'isolation_min_size': 5}

    if valid_count < min_pixels:
        return False, filter_config, f"muy pocos datos ({valid_count} píxeles < {min_pixels})"

    if density > 0.15:
        return False, filter_config, f"datos concentrados (densidad: {density:.2%})"

    if mean_value < 20.0 and max_value < 32.0:
        return False, filter_config, f"valores bajos (media: {mean_value:.2f} dBZ, max: {max_value:.2f} dBZ)"

    if density < 0.05 and max_value > 40.0:
        filter_config['apply_texture'] = True
        filter_config['apply_isolation'] = True
        filter_config['texture_threshold'] = 1.0
        filter_config['isolation_min_size'] = 3
        return True, filter_config, f"datos dispersos con señal fuerte (densidad: {density:.2%}, max: {max_value:.2f} dBZ)"

    if valid_count > 500 and density < 0.08:
        filter_config['apply_texture'] = True
        filter_config['apply_isolation'] = True
        filter_config['texture_threshold'] = 1.5
        filter_config['isolation_min_size'] = 5
        return True, filter_config, f"muchos datos dispersos (count: {valid_count}, densidad: {density:.2%})"

    return False, filter_config, f"condiciones normales (count: {valid_count}, densidad: {density:.2%})"


def apply_smart_filters(cart_data, cart_metadata, filter_config):
    nodata = cart_metadata['nodata']
    valid_before = np.sum(cart_data > nodata)

    if valid_before == 0:
        return cart_data

    result_data = cart_data.copy()

    if filter_config['apply_texture']:
        print(f"      Aplicando filtro de textura (threshold={filter_config['texture_threshold']})...")
        filtered = apply_texture_filter(result_data, threshold=filter_config['texture_threshold'], kernel_size=3)
        valid_after = np.sum(filtered > nodata)
        reduction = (valid_before - valid_after) / valid_before if valid_before > 0 else 0
        if reduction <= 0.70:
            result_data = filtered
            print(f"      Filtro de textura OK: {valid_after} píxeles ({reduction*100:.1f}% reducción)")
        else:
            print(f"      Filtro de textura rechazado: eliminaría {reduction*100:.1f}% de datos")

    if filter_config['apply_isolation']:
        valid_before_isolation = np.sum(result_data > nodata)
        print(f"      Aplicando filtro de aislamiento (min_size={filter_config['isolation_min_size']})...")
        filtered = apply_isolation_filter(result_data, min_cluster_size=filter_config['isolation_min_size'], connectivity=2)
        valid_after = np.sum(filtered > nodata)
        reduction = (valid_before_isolation - valid_after) / valid_before_isolation if valid_before_isolation > 0 else 0
        if reduction <= 0.60:
            result_data = filtered
            print(f"      Filtro de aislamiento OK: {valid_after} píxeles ({reduction*100:.1f}% reducción)")
        else:
            print(f"      Filtro de aislamiento rechazado: eliminaría {reduction*100:.1f}% de datos")

    return result_data

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def format_timestamp_for_display(timestamp):
    try:
        if '_' in timestamp:
            date_str, time_str = timestamp.split('_')
        else:
            return timestamp
        dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
        utc_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        local_dt = dt - timedelta(hours=5)
        lt_str = local_dt.strftime("%Y-%m-%d %H:%M LT")
        return f"{utc_str} ({lt_str})"
    except Exception as e:
        print(f"Error al formatear timestamp: {e}")
        return timestamp


def meters_per_degree(center_lat):
    """Longitud (m) de un grado de latitud y de longitud a la latitud dada
    (serie estándar sobre WGS84, error < 1 m). Sustituye la constante 111320
    usada antes también para la latitud, que comprimía la imagen un 0.67 %
    en N-S (~630 m en los bordes del lienzo a la latitud de LOXX)."""
    import math
    phi = math.radians(center_lat)
    m_per_deg_lat = 111132.954 - 559.822 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
    m_per_deg_lon = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
    return m_per_deg_lat, m_per_deg_lon


def calculate_bounds_from_metadata(center_lat, center_lon, max_radius_meters):
    m_per_deg_lat, m_per_deg_lon = meters_per_degree(center_lat)
    lat_offset = max_radius_meters / m_per_deg_lat
    lon_offset = max_radius_meters / m_per_deg_lon
    lat_sw = center_lat - lat_offset
    lon_sw = center_lon - lon_offset
    lat_ne = center_lat + lat_offset
    lon_ne = center_lon + lon_offset
    bounds = [[lat_sw, lon_sw], [lat_ne, lon_ne]]
    print(f"Bounds calculados para Leaflet (EPSG:4326):")
    print(f"  Centro: [{center_lat:.6f}, {center_lon:.6f}]")
    print(f"  SW: [{lat_sw:.6f}, {lon_sw:.6f}]")
    print(f"  NE: [{lat_ne:.6f}, {lon_ne:.6f}]")
    print(f"  Radio: {max_radius_meters/1000:.1f} km  (m/grado: lat {m_per_deg_lat:.0f}, lon {m_per_deg_lon:.0f})")
    return bounds


def decompress_gz_file_simple(gz_file_path):
    try:
        temp_dir = tempfile.mkdtemp()
        base_filename = os.path.basename(gz_file_path)[:-3]
        output_file = os.path.join(temp_dir, base_filename)
        with gzip.open(gz_file_path, 'rb') as f_in:
            with open(output_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return output_file, temp_dir
    except Exception as e:
        print(f"Error al descomprimir {os.path.basename(gz_file_path)}: {e}")
        return None, None


def cleanup_temp_files(h5_file, temp_dir):
    try:
        if h5_file and os.path.exists(h5_file):
            try:
                os.remove(h5_file)
                print(f"   Archivo temporal eliminado: {os.path.basename(h5_file)}")
            except Exception as e:
                print(f"   Advertencia: No se pudo eliminar {h5_file}: {e}")
        if temp_dir and os.path.exists(temp_dir):
            try:
                for file in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except Exception:
                        pass
                os.rmdir(temp_dir)
                print(f"   Directorio temporal eliminado")
            except Exception as e:
                print(f"   Advertencia: No se pudo eliminar directorio temporal: {e}")
    except Exception as e:
        print(f"   Error en limpieza de archivos temporales: {e}")


# Escala de reflectividad OFICIAL Furuno WR110 (familia jet): 10-70 dBZ en
# pasos de 5 (12 clases), MÁS una clase inferior 8-10 dBZ (navy) para que el
# piso de la paleta coincida EXACTAMENTE con el umbral de ruido calibrado
# (MIN_DBZH_THRESHOLD = 8 dBZ). Así los píxeles 8-10 dBZ no se pintan como si
# fueran "10-15". Transparente < 8 dBZ. LUT única compartida por LOXX, GUAXX y
# las figuras del paper (ambos radares son banda X). El colormap Furuno de 10
# dBZ hacia arriba se mantiene sin modificar (SIN magenta).
DBZH_LEVELS = [8, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
DBZH_COLORS = [
    (0, 0, 128),      # 8-10   navy (eco débil; piso de la paleta = umbral 8 dBZ)
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

# quality -> factor de ampliación ENTERO por vecino más cercano (bloque). Todo
# múltiplo entero preserva la correspondencia 1:1 con los bounds geográficos y
# no introduce interpolación. Para el overlay de Leaflet, 1x (nativo) es lo
# ideal; 'ultra' permite un tile 2x exacto si se necesitara.
QUALITY_SCALE = {'low': 1, 'medium': 1, 'high': 1, 'ultra': 2}


def visualize_dbzh_transparent(cart_data, cart_metadata, radar_metadata,
                               min_dbzh=8.0, max_dbzh=70.0, quality='medium'):
    """
    Rasteriza el PNG RGBA transparente DIRECTAMENTE desde la malla cartesiana
    (1 píxel = 1 celda), sin matplotlib ni interpolación. Salida exactamente
    width x height (949x949), o un múltiplo entero exacto según `quality`.
    """
    nodata = cart_metadata['nodata']
    height_px, width_px = cart_data.shape

    # Píxeles a colorear: dato válido y >= umbral mínimo.
    valid = (cart_data != nodata) & (cart_data >= min_dbzh) & ~np.isnan(cart_data)

    # Índice de color por celda: bin de [DBZH_LEVELS[i], DBZH_LEVELS[i+1]).
    # np.digitize(cart_data, DBZH_LEVELS)-1 se recorta a 0..len(DBZH_COLORS)-1.
    bin_idx = np.digitize(cart_data, DBZH_LEVELS) - 1
    bin_idx = np.clip(bin_idx, 0, len(DBZH_COLORS) - 1)

    lut = np.array(DBZH_COLORS, dtype=np.uint8)          # (N, 3)
    rgba = np.zeros((height_px, width_px, 4), dtype=np.uint8)
    rgba[..., :3] = lut[bin_idx]                          # color por bin
    rgba[..., 3] = np.where(valid, 255, 0).astype(np.uint8)  # alfa (transparencia)
    rgba[~valid, :3] = 0                                  # limpiar RGB donde es transparente

    img = Image.fromarray(rgba, mode='RGBA')

    scale = QUALITY_SCALE.get(quality, 1)
    if scale > 1:
        img = img.resize((width_px * scale, height_px * scale), resample=Image.NEAREST)

    buf = BytesIO()
    img.save(buf, format='PNG')
    img_data = buf.getvalue()
    buf.close()

    timestamp_str = "Fecha/hora desconocida"
    if 'timestamp' in radar_metadata:
        timestamp_str = format_timestamp_for_display(radar_metadata['timestamp'])

    out_w, out_h = img.size
    print(f"Imagen PNG generada: {out_w}x{out_h} píxeles (nativo {width_px}x{height_px}, escala {scale}x, sin interpolación)")
    print(f"Píxeles con eco: {int(valid.sum())}")
    print(f"Timestamp: {timestamp_str}")

    return img_data, timestamp_str


def process_single_file(h5_file, clutter_maps, timestamp_str):
    try:
        print(f"  Procesando archivo H5...")

        all_dbzh_data = []
        all_metadata = []

        for dataset_number in range(1, 6):
            data, metadata = extract_dbzh_data(h5_file, dataset_number, 2)

            if data is None or metadata is None or metadata.get('quantity', '') != 'DBZH':
                continue

            # Filtro de mediana 2-D sobre la matriz polar
            if data is not None:
                data = np.where(data > 100.0, 100.0, data)
                data = apply_median_filter_2d(data, size=3)

            clutter_key = f"dataset{dataset_number}_data2"
            if clutter_key in clutter_maps:
                clutter_map = clutter_maps[clutter_key]
                if data.shape == clutter_map.shape:
                    corrected_data = apply_clutter_correction(
                        data, clutter_map, method=CLUTTER_METHOD,
                        min_threshold=MIN_DBZH_THRESHOLD,
                        clutter_factor=CLUTTER_FACTOR * 1.5
                    )
                    if not np.isnan(corrected_data).all():
                        corrected_data = fast_interpolate_small_gaps_optimized(corrected_data, max_gap_size=2)
                        all_dbzh_data.append(corrected_data)
                        all_metadata.append(metadata)
                        print(f"    Dataset{dataset_number}/data2 procesado con corrección de clutter")
            else:
                all_dbzh_data.append(data)
                all_metadata.append(metadata)
                print(f"    Dataset{dataset_number}/data2 procesado sin corrección de clutter")

        if not all_dbzh_data:
            print(f"    No se pudieron extraer datos DBZH")
            return None, None

        stacked_data = np.stack(all_dbzh_data)
        max_dbzh = np.nanmax(stacked_data, axis=0)

        if np.isnan(max_dbzh).all():
            print(f"    Todos los valores son NaN")
            return None, None

        metadata = all_metadata[0]

        print(f"    Aplicando transformación cartesiana...")
        cart_data, cart_metadata = create_cartesian_data_optimized_new(
            max_dbzh, metadata, MIN_DBZH_THRESHOLD, RESOLUTION_FACTOR
        )

        valid_before = np.sum(cart_data > cart_metadata['nodata'])
        print(f"    Píxeles válidos antes de filtros: {valid_before}")

        if ENABLE_SMART_FILTERS:
            print(f"    Analizando calidad de datos para filtros inteligentes...")
            should_filter, filter_config, reason = should_apply_filters(cart_data, cart_metadata)
            print(f"    Decisión: {reason}")
            if should_filter:
                cart_data = apply_smart_filters(cart_data, cart_metadata, filter_config)
                valid_after = np.sum(cart_data > cart_metadata['nodata'])
                print(f"    Píxeles después de filtros: {valid_after}")
            else:
                print(f"    Filtros omitidos para preservar datos")
        else:
            print(f"    Filtros inteligentes deshabilitados")

        valid_data = cart_data > cart_metadata['nodata']
        if not np.any(valid_data):
            print("    No hay datos válidos después del procesamiento")
            return None, None

        valid_count = np.sum(cart_data >= MIN_DBZH_THRESHOLD)
        print(f"    Píxeles sobre umbral: {valid_count}")

        if valid_count < 3:
            print(f"    Insuficientes valores sobre el umbral")
            return None, None

        print(f"    Generando imagen PNG transparente...")
        img_data, formatted_time = visualize_dbzh_transparent(
            cart_data, cart_metadata, metadata,
            min_dbzh=MIN_DBZH_THRESHOLD,
            quality=PLOT_QUALITY
        )

        center_lat = RADAR_INFO['default_lat']
        center_lon = RADAR_INFO['default_lon']

        effective_radius = cart_metadata['pixel_size'] * (cart_metadata['width'] / 2)
        bounds = calculate_bounds_from_metadata(center_lat, center_lon, effective_radius)

        output_metadata = {
            'timestamp': timestamp_str,
            'formatted_time': formatted_time,
            'bounds': bounds,
            'center': [center_lat, center_lon],
            'radar_info': {
                'id': RADAR_INFO['id'],
                'name': RADAR_INFO['name'],
                'lat': center_lat,
                'lon': center_lon,
                'height': metadata.get('height', RADAR_INFO['default_height'])
            },
            'dimensions': {'width': cart_metadata['width'], 'height': cart_metadata['height']},
            'processing': {
                'data_type': 'DBZH',
                'resolution_factor': RESOLUTION_FACTOR,
                'min_threshold': MIN_DBZH_THRESHOLD,
                'clutter_correction': CLUTTER_METHOD,
                'smart_filters': ENABLE_SMART_FILTERS,
                'pipeline_version': 'loxx-dbzh-1.0'
            }
        }

        return img_data, output_metadata

    except Exception as e:
        print(f"    Error procesando archivo: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def find_latest_file():
    try:
        all_files = glob.glob(os.path.join(RADAR_DIR, "*.h5.gz"))
        if not all_files:
            print(f"No se encontraron archivos .h5.gz en {RADAR_DIR}")
            return None
        all_files.sort()
        return all_files[-1]
    except Exception as e:
        print(f"Error buscando archivos: {e}")
        return None


def generar_png_ultimo_loxx(target_file=None):
    """
    Genera el PNG del archivo indicado. Si target_file es None, usa el .h5.gz
    más reciente de RADAR_DIR (comportamiento anterior). Pasar el archivo
    detectado por el watchdog evita el desfase timestamp/imagen cuando hay
    backlog de transferencias.
    """
    h5_file = None
    temp_dir = None
    try:
        print("=" * 70)
        print("  GENERANDO PNG DEL ARCHIVO RADAR LOXX (DBZH)")
        print("=" * 70)
        print()

        if not IMPORTS_OK:
            print("ERROR: No se pudieron importar las funciones necesarias")
            return False

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        print("Cargando mapas de clutter DBZH...")
        clutter_maps = None
        global_metadata = None

        if not REGENERATE_CLUTTER:
            clutter_maps, global_metadata = load_clutter_cache(CLUTTER_CACHE_FILE)
        else:
            print("AVISO: regenerate_clutter = True. Se forzará la regeneración de mapas de clutter.")

        if clutter_maps is None:
            if REGENERATE_CLUTTER:
                print("Regenerando mapas de clutter (configuración activada)...")
            else:
                print("No se encontró cache de clutter. Generando nuevos mapas DBZH...")
            clutter_maps, global_metadata = generate_clutter_maps(CLUTTER_DIR, data_number=2)
            if clutter_maps:
                save_clutter_cache(clutter_maps, global_metadata, CLUTTER_CACHE_FILE)
            else:
                print("ADVERTENCIA: No se pudieron generar mapas de clutter")
                clutter_maps = {}

        print(f"Mapas de clutter cargados: {len(clutter_maps)} datasets")
        print()

        if target_file:
            latest_file = target_file
            if not os.path.exists(latest_file):
                print(f"El archivo indicado no existe: {latest_file}")
                return False
            print(f"Archivo indicado por argumento: {os.path.basename(latest_file)}")
        else:
            print("Buscando último archivo .h5.gz...")
            latest_file = find_latest_file()
        if not latest_file:
            print("No se encontró ningún archivo para procesar")
            return False

        filename = os.path.basename(latest_file)
        print(f"Archivo más reciente: {filename}")

        timestamp_str = extract_timestamp_from_filename(filename)
        if not timestamp_str:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"  Usando timestamp actual: {timestamp_str}")

        print(f"Timestamp: {timestamp_str}")
        print()

        print("Descomprimiendo archivo .h5.gz...")
        h5_file, temp_dir = decompress_gz_file_simple(latest_file)
        if not h5_file:
            print("Error al descomprimir archivo")
            return False

        print(f"Archivo descomprimido: {os.path.basename(h5_file)}")
        print()

        try:
            img_data, metadata = process_single_file(h5_file, clutter_maps, timestamp_str)
            if img_data is None or metadata is None:
                print("Error: No se pudo procesar el archivo")
                return False

            output_filename = f"radar_loxx_{timestamp_str}.png"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            latest_path = os.path.join(OUTPUT_DIR, "radar_loxx_latest.png")

            with open(output_path, 'wb') as f:
                f.write(img_data)
            with open(latest_path, 'wb') as f:
                f.write(img_data)

            metadata['file'] = output_filename
            metadata_path = os.path.join(OUTPUT_DIR, f"radar_loxx_{timestamp_str}_metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            latest_metadata_path = os.path.join(OUTPUT_DIR, "radar_loxx_latest_metadata.json")
            with open(latest_metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            print()
            print("=" * 70)
            print("[OK] PNG DBZH creado exitosamente:")
            print(f"  Con timestamp: {output_path}")
            print(f"  Latest: {latest_path}")
            print(f"  Metadata: {metadata_path}")
            print("=" * 70)
            return True
        finally:
            cleanup_temp_files(h5_file, temp_dir)

    except Exception as e:
        print(f"\n[ERROR] Error general: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if h5_file or temp_dir:
            cleanup_temp_files(h5_file, temp_dir)
        import gc
        gc.collect()


def main():
    # Uso: generar_png_loxx.py [ruta_al_archivo.h5.gz]
    target = sys.argv[1] if len(sys.argv) > 1 else None
    success = generar_png_ultimo_loxx(target)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
