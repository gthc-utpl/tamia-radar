# loxx_dbzh_georeferenciado.py
"""
Módulo de procesamiento DBZH del radar LOXX (Furuno WR110, ODIM HDF5).

Comportamiento:

1. Undetect: extract_dbzh_data enmascara el valor crudo 0, que el Furuno
   WR110 usa como 'sin eco' sin declarar el atributo ODIM 'undetect'. Así los
   bines sin eco no se tratan como mediciones de -32 dBZ ni en los datos ni en
   los mapas de clutter.

2. Corrección de clutter: apply_clutter_correction fija el mapa de clutter a
   >= 0 dBZ antes de restar, de modo que la corrección solo puede atenuar,
   nunca amplificar la señal.

3. Filtro de mediana espacial: apply_median_filter_2d opera sobre la matriz
   polar completa (rayos x bins) con envolvimiento en azimut.

Dependencias: numpy, scipy, h5py.
"""

import h5py
import numpy as np
import os
import gzip
import shutil
import tempfile
import glob
from scipy import ndimage
from scipy.ndimage import median_filter
import warnings
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import pickle
import time
import re
import configparser

warnings.filterwarnings("ignore", category=RuntimeWarning)

# Piso físico de la escala DBZH del WR110 (raw 0 con gain 0.5, offset -32).
# Se usa como relleno neutro en el filtro de mediana.
DBZH_FLOOR = -32.0


class TempFileManager:
    def __init__(self):
        self.temp_files = []

    def get_temp_file(self, gz_file_path):
        temp_dir = tempfile.mkdtemp()
        base_filename = os.path.basename(gz_file_path)[:-3]
        output_file = os.path.join(temp_dir, base_filename)
        self.temp_files.append((output_file, temp_dir))
        return output_file

    def cleanup(self):
        for temp_file, temp_dir in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception as e:
                print(f"Error cleaning up temp file: {e}")
        self.temp_files = []


@lru_cache(maxsize=256)
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


def parse_timestamp(timestamp_str):
    try:
        if '_' in timestamp_str:
            date_str, time_str = timestamp_str.split('_')
            dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
            return dt
        return None
    except Exception as e:
        print(f"Error parsing timestamp '{timestamp_str}': {e}")
        return None


def extract_timestamp_from_filename(filename):
    """Extrae timestamp del nombre de archivo"""
    pattern = r'(\d{4})_(\d{8})_(\d{6})'
    match = re.search(pattern, filename)
    if match:
        prefix, date_str, time_str = match.groups()
        return f"{date_str}_{time_str}"

    pattern = r'(\d{8})_(\d{6})'
    match = re.search(pattern, filename)
    if match:
        return match.group(0)

    return None


def is_file_complete(file_path, lock_timeout=60):
    try:
        current_time = time.time()
        file_mod_time = os.path.getmtime(file_path)
        file_size = os.path.getsize(file_path)

        if current_time - file_mod_time < lock_timeout:
            print(f"  Archivo {os.path.basename(file_path)} posiblemente en transferencia")
            return False

        if file_size < 1024:
            print(f"  Archivo {os.path.basename(file_path)} demasiado pequeño")
            return False

        return True
    except Exception as e:
        print(f"  Error al verificar archivo: {e}")
        return False


def get_files_in_timeframe(directory, hours=2, lock_timeout=60):
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist")
        return []

    now = datetime.utcnow()
    cutoff_time = now - timedelta(hours=hours)

    print(f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cutoff time (UTC-{hours}h): {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")

    all_files = glob.glob(os.path.join(directory, "*.h5.gz"))
    recent_files = []

    for file_path in all_files:
        filename = os.path.basename(file_path)

        if not is_file_complete(file_path, lock_timeout):
            continue

        timestamp_str = extract_timestamp_from_filename(filename)

        if timestamp_str:
            file_time = parse_timestamp(timestamp_str)
            if file_time and file_time >= cutoff_time:
                recent_files.append(file_path)

    recent_files.sort()
    print(f"Selected {len(recent_files)} files within the last {hours} hours")

    return recent_files


def decompress_gz_file(gz_file_path, temp_manager):
    output_file = temp_manager.get_temp_file(gz_file_path)

    try:
        with gzip.open(gz_file_path, 'rb') as f_in:
            with open(output_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        return output_file
    except Exception as e:
        print(f"Error al descomprimir {os.path.basename(gz_file_path)}: {e}")
        return None


def extract_dbzh_data(h5_file_path, dataset_number, data_number=2):
    """
    Extrae datos DBZH de un archivo H5 de radar.

    Enmascara 'undetect' (valor crudo 0 en el Furuno WR110, que no declara el
    atributo ODIM 'undetect') para que los bines sin eco no se tomen como -32 dBZ.

    Args:
        h5_file_path: Ruta al archivo H5
        dataset_number: Número de dataset (1-5, corresponde a elevaciones)
        data_number: Número de data (2 para DBZH)

    Returns:
        tuple: (physical_data, metadata) o (None, None) si no se encuentra DBZH
    """
    try:
        with h5py.File(h5_file_path, 'r') as f:
            dataset_path = f"dataset{dataset_number}/data{data_number}/data"
            what_path = f"dataset{dataset_number}/data{data_number}/what"

            if dataset_path not in f or what_path not in f:
                return None, None

            # Verificar que sea DBZH
            quantity = f[what_path].attrs.get('quantity', b'').decode() if isinstance(
                f[what_path].attrs.get('quantity', b''), bytes) else f[what_path].attrs.get('quantity', '')

            if quantity != 'DBZH':
                return None, None

            # Parámetros de conversión para DBZH
            gain = f[what_path].attrs.get('gain', 0.5)
            offset = f[what_path].attrs.get('offset', -32.0)
            nodata = f[what_path].attrs.get('nodata', 255.0)

            # Furuno no declara el atributo ODIM 'undetect'; el valor crudo 0
            # es "sin eco detectado" y no debe tratarse como medición.
            undetect = f[what_path].attrs.get('undetect', None)
            if undetect is None:
                undetect = 0.0

            metadata = {
                'gain': gain,
                'offset': offset,
                'nodata': nodata,
                'undetect': undetect,
                'quantity': quantity,
                'dataset': f"dataset{dataset_number}",
                'data_number': data_number
            }

            # Extraer metadata adicional
            where_path = f"dataset{dataset_number}/where"
            if where_path in f:
                metadata['elangle'] = f[where_path].attrs.get('elangle', 0.0)
                metadata['nbins'] = f[where_path].attrs.get('nbins', 0)
                metadata['nrays'] = f[where_path].attrs.get('nrays', 0)
                metadata['rscale'] = f[where_path].attrs.get('rscale', 0.0)
                metadata['rstart'] = f[where_path].attrs.get('rstart', 0.0)

            # Azimut real de inicio de cada rayo (grados, brújula 0=N horario).
            # El Furuno WR110 muestrea los rayos de forma NO uniforme; usar estos
            # azimuts reales en la proyección evita el error (~1.5°) de asumir
            # rayos equiespaciados desde 0°. Ordenado ascendente en el archivo.
            how_path = f"dataset{dataset_number}/how"
            if how_path in f and 'startazA' in f[how_path].attrs:
                metadata['startazA'] = np.asarray(
                    f[how_path].attrs['startazA'], dtype=np.float64
                )

            if 'where' in f:
                metadata['lat'] = f['where'].attrs.get('lat', 0.0)
                metadata['lon'] = f['where'].attrs.get('lon', 0.0)
                metadata['height'] = f['where'].attrs.get('height', 0.0)

            if 'what' in f:
                start_date = f['what'].attrs.get('startdate', b'').decode() if isinstance(
                    f['what'].attrs.get('startdate', b''), bytes) else f['what'].attrs.get('startdate', '')
                start_time = f['what'].attrs.get('starttime', b'').decode() if isinstance(
                    f['what'].attrs.get('starttime', b''), bytes) else f['what'].attrs.get('starttime', '')
                if start_date and start_time:
                    metadata['timestamp'] = f"{start_date}_{start_time}"

            if 'timestamp' not in metadata:
                filename = os.path.basename(h5_file_path)
                parts = filename.split('_')
                if len(parts) >= 3:
                    metadata['timestamp'] = f"{parts[1]}_{parts[2].split('.')[0]}"

            # Leer datos crudos
            data = f[dataset_path][:]

            # Convertir a valores físicos (dBZ): nodata Y undetect -> NaN
            physical_data = np.where(
                (data == nodata) | (data == undetect),
                np.nan,
                data * gain + offset
            )

            return physical_data, metadata
    except Exception as e:
        print(f"Error al procesar {os.path.basename(h5_file_path)}, dataset{dataset_number}/data{data_number}: {e}")
        return None, None


def apply_median_filter_2d(data, size=3, min_valid=1):
    """
    Filtro de mediana espacial 2-D que IGNORA los NaN (edge-preserving).

    Opera sobre la matriz polar completa (rayos x bins) con envolvimiento en
    azimut.

    Diseño (vectorizado, ~150 ms por barrido 488x704):
      - La mediana de cada celda se calcula SOLO sobre los vecinos válidos
        de su ventana (np.nanmedian sobre los desplazamientos apilados). Así
        no se erosionan los bordes de los ecos hacia el piso -32 dBZ, ni se
        inventan ecos en celdas sin dato (la máscara NaN original se respeta
        exactamente: el conteo de píxeles válidos se conserva).
      - Eje de azimut (eje 0): envolvimiento circular (rayo N-1 vecino del 0).
      - Eje de rango (eje 1): borde replicado ('nearest').
      - min_valid: nº mínimo de vecinos válidos para suavizar una celda; por
        debajo se conserva su valor original (no se destruye señal escasa).
        La eliminación de píxeles/clústeres aislados corresponde al filtro de
        aislamiento (apply_isolation_filter), no a la mediana.

    Args:
        data: matriz polar 2-D en dBZ con NaN en píxeles sin eco
        size: tamaño del kernel (3 -> 3x3)
        min_valid: soporte mínimo de vecinos válidos para aplicar la mediana

    Returns:
        numpy.ndarray: matriz filtrada, con la máscara NaN original intacta
    """
    if data is None or data.ndim != 2:
        return data

    orig_valid = ~np.isnan(data)
    if not orig_valid.any():
        return data

    pad = size // 2
    P = np.pad(data, ((pad, pad), (pad, pad)), mode='wrap')
    # Rango (eje 1): reemplazar el wrap por borde replicado (nearest)
    P[:, :pad] = P[:, pad:pad + 1]
    P[:, -pad:] = P[:, -pad - 1:-pad]

    h, w = data.shape
    stack = np.empty((size * size, h, w), dtype=np.float64)
    k = 0
    for i in range(size):
        for j in range(size):
            stack[k] = P[i:i + h, j:j + w]
            k += 1

    valid_count = np.sum(~np.isnan(stack), axis=0)
    med = np.nanmedian(stack, axis=0)

    # Suavizar donde hay soporte suficiente; conservar el valor original
    # en celdas válidas con poco soporte; NaN donde no había dato.
    result = np.where(
        orig_valid & (valid_count >= min_valid),
        med,
        np.where(orig_valid, data, np.nan)
    )
    return result


def fast_interpolate_small_gaps_optimized(data, max_gap_size=2):
    if not np.any(np.isnan(data)):
        return data

    filled_data = data.copy()
    nan_mask = np.isnan(data)

    if not np.any(nan_mask):
        return filled_data

    labeled_array, num_features = ndimage.label(nan_mask)

    if num_features == 0:
        return filled_data

    kernel_size = max_gap_size
    kernel = np.ones((kernel_size, kernel_size))

    for i in range(1, num_features + 1):
        region_coords = np.where(labeled_array == i)
        region_size = len(region_coords[0])

        if region_size <= max_gap_size * max_gap_size:
            dilated = ndimage.binary_dilation(labeled_array == i, structure=kernel)
            neighbor_mask = dilated & ~(labeled_array == i)
            neighbor_values = data[neighbor_mask]

            valid_neighbors = neighbor_values[~np.isnan(neighbor_values)]
            if len(valid_neighbors) > 0:
                fill_value = np.nanmedian(valid_neighbors)
                filled_data[region_coords] = fill_value

    return filled_data


def apply_texture_filter(cart_data, threshold=2.0, kernel_size=3):
    """
    ADVERTENCIA: NO usar. Este filtro elimina píxeles de BAJA desviación
    estándar local (campos lisos), que es justo el interior de la precipitación
    estratiforme, borrando eco real; deja solo las líneas de borde de alto
    gradiente. Es lo contrario de un filtro de textura SD(Z) meteorológico, que
    remueve la ALTA textura (clutter/ruido incoherente). Queda desactivado
    (apply_filters=False) y se conserva solo por compatibilidad.
    """
    from scipy.ndimage import uniform_filter

    data = np.copy(cart_data)
    nodata = -999
    mask = data == nodata
    data[mask] = np.nan

    valid = ~np.isnan(data)

    if np.sum(valid) < 100:
        return cart_data

    mean = uniform_filter(np.where(valid, data, 0), size=kernel_size)
    mean2 = uniform_filter(np.where(valid, data * data, 0), size=kernel_size)
    valid_count = uniform_filter(valid.astype(float), size=kernel_size)

    mean = np.where(valid_count > 0, mean / valid_count, 0)
    mean2 = np.where(valid_count > 0, mean2 / valid_count, 0)

    variance = np.maximum(mean2 - mean**2, 0)
    std_dev = np.sqrt(variance)

    low_texture = std_dev < threshold
    noise_pixels = valid & low_texture

    if np.sum(noise_pixels) < np.sum(valid) * 0.9:
        data[noise_pixels] = np.nan
    else:
        noise_pixels = valid & (std_dev < threshold * 0.5)
        data[noise_pixels] = np.nan

    data[mask] = nodata
    data[np.isnan(data)] = nodata

    return data


def apply_isolation_filter(cart_data, min_cluster_size=10, connectivity=2):
    from scipy.ndimage import label, sum as ndsum

    data = np.copy(cart_data)
    nodata = -999
    mask = data == nodata

    binary = ~mask
    labeled, num_features = label(binary, structure=np.ones((3, 3)))
    sizes = ndsum(binary, labeled, range(1, num_features + 1))

    too_small = sizes < min_cluster_size
    remove_pixels = np.zeros_like(binary)

    for i, too_small_flag in enumerate(too_small, 1):
        if too_small_flag:
            remove_pixels[labeled == i] = True

    data[remove_pixels] = nodata

    return data


def save_clutter_cache(clutter_maps, global_metadata, cache_file):
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump((clutter_maps, global_metadata), f)
        print(f"Mapas de clutter guardados en cache: {cache_file}")
        return True
    except Exception as e:
        print(f"Error al guardar cache de clutter: {e}")
        return False


def load_clutter_cache(cache_file):
    try:
        if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
            with open(cache_file, 'rb') as f:
                clutter_maps, global_metadata = pickle.load(f)
            print(f"Mapas de clutter cargados desde cache: {cache_file}")

            print(f"Mapas de clutter disponibles:")
            for key in clutter_maps:
                shape = clutter_maps[key].shape
                if np.isnan(clutter_maps[key]).all():
                    print(f"  - {key}: {shape}, sin clutter persistente (todo NaN)")
                    continue
                min_val = round(float(np.nanmin(clutter_maps[key])), 2)
                max_val = round(float(np.nanmax(clutter_maps[key])), 2)
                print(f"  - {key}: {shape}, valores: {min_val} a {max_val} dBZ")

            return clutter_maps, global_metadata
        else:
            print(f"Archivo de cache no encontrado o vacío: {cache_file}")
            return None, None
    except Exception as e:
        print(f"Error al cargar cache de clutter: {e}")
        return None, None


def generate_clutter_maps(clutter_dir, data_number=2):
    """
    Genera mapas de clutter usando datos DBZH (data2).

    Con el enmascarado de 'undetect' en extract_dbzh_data, los píxeles donde
    nunca se observó eco en los días de referencia quedan NaN en el mapa, y
    apply_clutter_correction no corrige en esas zonas.

    Args:
        clutter_dir: Directorio con archivos de referencia
        data_number: Número de data (2 para DBZH)
    """
    gz_files = glob.glob(os.path.join(clutter_dir, "*.h5.gz"))

    if not gz_files:
        print(f"No se encontraron archivos .h5.gz en {clutter_dir}")
        return None, None

    print(f"Procesando {len(gz_files)} archivos para generar mapas de clutter DBZH...")

    clutter_maps = {}
    global_metadata = {}
    temp_manager = TempFileManager()

    try:
        with ThreadPoolExecutor(max_workers=min(os.cpu_count(), 12)) as executor:
            h5_files = []
            for gz_file in gz_files:
                future = executor.submit(decompress_gz_file, gz_file, temp_manager)
                try:
                    result = future.result()
                    if result:
                        h5_files.append(result)
                except Exception as e:
                    print(f"Error decompressing {gz_file}: {e}")

        if not h5_files:
            print("No se pudieron descomprimir archivos para mapas de clutter")
            return None, None

        for h5_file in h5_files:
            for dataset_number in range(1, 6):
                try:
                    data, metadata = extract_dbzh_data(h5_file, dataset_number, data_number)

                    if data is not None and metadata is not None and metadata.get('quantity', '') == 'DBZH':
                        key = f"dataset{dataset_number}_data{data_number}"

                        if key not in global_metadata:
                            global_metadata[key] = metadata

                        if key not in clutter_maps:
                            clutter_maps[key] = []

                        clutter_maps[key].append(data)
                        print(f"  Datos DBZH extraídos de dataset{dataset_number}/data{data_number}")
                except Exception as e:
                    print(f"Error processing dataset{dataset_number}/data{data_number}: {e}")

        final_clutter_maps = {}

        for key, data_list in clutter_maps.items():
            if data_list:
                try:
                    if len(data_list) > 1:
                        stacked_data = np.stack(data_list)
                        max_data = np.nanmax(stacked_data, axis=0)
                    else:
                        max_data = data_list[0]

                    final_clutter_maps[key] = max_data
                    print(f"Mapa de clutter generado para {key} (DBZH): {max_data.shape}")
                except Exception as e:
                    print(f"Error creating clutter map for {key}: {e}")

        return final_clutter_maps, global_metadata

    except Exception as e:
        print(f"Error generando mapas de clutter: {e}")
        return None, None

    finally:
        temp_manager.cleanup()


def apply_clutter_correction(radar_data, clutter_map, method='substract', min_threshold=None, clutter_factor=1.0):
    """
    Aplica corrección de clutter sobre datos polares en dBZ.

    El mapa de clutter se fija a >= 0 dBZ antes de restar, de modo que la
    corrección solo puede atenuar, nunca amplificar la señal. Los NaN del mapa
    (píxeles sin clutter persistente) se preservan: ahí no se corrige.
    """
    if radar_data is None or clutter_map is None:
        return radar_data

    if radar_data.shape != clutter_map.shape:
        print(f"Error: Las formas no coinciden. Radar: {radar_data.shape}, Clutter: {clutter_map.shape}")
        return radar_data

    # La corrección solo puede atenuar, nunca amplificar.
    # np.maximum preserva los NaN (quedan fuera de valid_mask).
    clutter_map = np.maximum(clutter_map, 0.0)

    valid_mask = ~np.isnan(radar_data) & ~np.isnan(clutter_map)
    if not np.any(valid_mask):
        return radar_data

    corrected_data = radar_data.copy()

    if method == 'substract':
        corrected_data[valid_mask] -= clutter_map[valid_mask] * clutter_factor

    elif method == 'mask':
        threshold = min_threshold if min_threshold is not None else np.nanmean(clutter_map)
        mask = clutter_map > threshold
        corrected_data[mask] = np.nan

    elif method == 'adaptive':
        strong_signal = radar_data > (clutter_map * 2)

        strong_indices = valid_mask & strong_signal
        weak_indices = valid_mask & ~strong_signal

        if np.any(strong_indices):
            corrected_data[strong_indices] -= clutter_map[strong_indices] * 0.5

        if np.any(weak_indices):
            corrected_data[weak_indices] -= clutter_map[weak_indices] * clutter_factor

    if min_threshold is not None:
        corrected_data[corrected_data < min_threshold] = np.nan

    return corrected_data


def create_cartesian_data_optimized_new(data, metadata, min_dbzh_threshold=8.0, resolution_factor=2):
    """
    Convierte datos polares de DBZH a coordenadas cartesianas

    Args:
        data: Datos en coordenadas polares (dBZ)
        metadata: Metadata del radar
        min_dbzh_threshold: Umbral mínimo en dBZ (default: 8.0, calibrado)
        resolution_factor: Factor de resolución
    """
    if data is None or len(data.shape) != 2:
        print(f"Error: Invalid data shape: {None if data is None else data.shape}")
        return np.full((949, 949), -999, dtype=np.float32), {'width': 949, 'height': 949, 'nodata': -999}

    if hasattr(data, 'shape') and len(data.shape) == 2:
        default_nrays, default_nbins = data.shape
    else:
        default_nrays, default_nbins = 360, 120

    nrays = metadata.get('nrays', default_nrays)
    nbins = metadata.get('nbins', default_nbins)
    rscale = metadata.get('rscale', 75.0)

    max_radius_meters = nbins * rscale
    pixel_size = rscale * resolution_factor

    width_px = height_px = 949
    center_px_x = width_px // 2
    center_px_y = height_px // 2

    y, x = np.ogrid[:height_px, :width_px]

    dx = x - center_px_x
    dy = center_px_y - y

    distance = np.hypot(dx, dy) * pixel_size
    angle = np.arctan2(dy, dx)
    angle = np.where(angle < 0, angle + 2 * np.pi, angle)

    bin_idx = (distance / rscale).astype(np.int32)
    # Azimut de brújula de cada píxel (0=N, horario), en grados.
    ray_angle = (np.pi / 2 - angle) % (2 * np.pi)
    az_deg = np.degrees(ray_angle)

    startazA = metadata.get('startazA', None)
    if startazA is not None and np.ndim(startazA) == 1 and len(startazA) == nrays:
        # Mapeo por azimut REAL: cada píxel se asigna al rayo cuyo sector
        # [startazA[i], startazA[i+1]) contiene su azimut. searchsorted sobre el
        # arreglo ordenado; los píxeles entre startazA[-1] y startazA[0] (sector
        # que cruza el norte) caen en el último rayo (índice -1 -> nrays-1).
        ray_idx = np.searchsorted(startazA, az_deg, side='right') - 1
        ray_idx[ray_idx < 0] = nrays - 1
        ray_idx = ray_idx.astype(np.int32)
    else:
        # Fallback: rayos equiespaciados desde 0° (comportamiento anterior).
        ray_idx = ((ray_angle / (2 * np.pi) * nrays) % nrays).astype(np.int32)

    valid_mask = (distance <= max_radius_meters) & (bin_idx < nbins)

    cart_data = np.full((height_px, width_px), -999, dtype=np.float32)

    valid_points = valid_mask & (bin_idx >= 0) & (ray_idx >= 0) & (bin_idx < nbins) & (ray_idx < nrays)
    valid_y, valid_x = np.where(valid_points)

    try:
        valid_bin_idx = bin_idx[valid_points]
        valid_ray_idx = ray_idx[valid_points]

        valid_indices = (valid_ray_idx < nrays) & (valid_bin_idx < nbins)
        valid_ray_idx = valid_ray_idx[valid_indices]
        valid_bin_idx = valid_bin_idx[valid_indices]
        valid_y = valid_y[valid_indices]
        valid_x = valid_x[valid_indices]

        valid_values = data[valid_ray_idx, valid_bin_idx]

        valid_values_mask = ~np.isnan(valid_values) & (valid_values >= min_dbzh_threshold)
        cart_data[valid_y[valid_values_mask], valid_x[valid_values_mask]] = valid_values[valid_values_mask]
    except Exception as e:
        print(f"Error durante la transformación de datos: {e}")

    mask = cart_data == -999
    temp_data = np.copy(cart_data)
    temp_data[mask] = np.nan

    filled_data = fast_interpolate_small_gaps_optimized(temp_data, max_gap_size=4)
    filled_data[np.isnan(filled_data)] = -999

    cart_metadata = {
        'width': width_px,
        'height': height_px,
        'center_x': center_px_x,
        'center_y': center_px_y,
        'pixel_size': pixel_size,
        'max_radius': max_radius_meters,
        'nodata': -999,
        'resolution_factor': resolution_factor
    }

    return filled_data, cart_metadata


def process_dataset_optimized_dbzh(h5_file, dataset_number, data_number, clutter_maps, method, clutter_factor):
    """
    Procesa un dataset específico con datos DBZH
    """
    data, metadata = extract_dbzh_data(h5_file, dataset_number, data_number)

    if data is None or metadata is None or metadata.get('quantity', '') != 'DBZH':
        return None, None

    # Asegurar ángulo de elevación positivo
    if 'elangle' in metadata:
        if metadata['elangle'] < 0:
            metadata['elangle'] = abs(metadata['elangle'])

    # Limitar valores extremos y aplicar filtro de mediana 2-D
    if data is not None:
        data = np.where(data > 100.0, 100.0, data)
        data = apply_median_filter_2d(data, size=3)

    # Aplicar corrección de clutter
    clutter_key = f"dataset{dataset_number}_data{data_number}"
    if clutter_key not in clutter_maps:
        return data, metadata

    clutter_map = clutter_maps[clutter_key]

    if data.shape != clutter_map.shape:
        return None, None

    adjusted_clutter_factor = clutter_factor * 1.5

    corrected_data = apply_clutter_correction(
        data, clutter_map, method='adaptive',
        min_threshold=10.0,
        clutter_factor=adjusted_clutter_factor
    )

    if np.isnan(corrected_data).all():
        return None, None

    corrected_data = fast_interpolate_small_gaps_optimized(corrected_data, max_gap_size=2)

    return corrected_data, metadata


def load_config(config_file='config.ini'):
    config = configparser.ConfigParser()

    default_config = {
        'Settings': {
            'clutter_dir': r"F:\LOXX\Clutter\Reference",
            'radar_dir': r"F:\LOXX\H5",
            'output_dir': r"E:\RainfallMonitorV2\data\h5\output",
            'regenerate_clutter': 'False',
            'clutter_cache_file': 'clutter_cache_dbzh.pkl',
            'cache_cleanup_days': '30',
            'lock_timeout': '60'
        },
        'RecentProcessing': {
            'hours_to_process': '4',
            'interval_minutes': '10',
            'min_dbzh_threshold': '8.0',
            'plot_quality': 'medium',
            'reuse_processed_files': 'True',
            'skip_frames': 'None',
            'apply_filters': 'False'
        }
    }

    if os.path.exists(config_file):
        config.read(config_file)

        if 'Settings' not in config:
            config['Settings'] = {}

        for key, value in default_config['Settings'].items():
            if key not in config['Settings']:
                config['Settings'][key] = value

        if 'RecentProcessing' not in config:
            config['RecentProcessing'] = {}

        for key, value in default_config['RecentProcessing'].items():
            if key not in config['RecentProcessing']:
                config['RecentProcessing'][key] = value
    else:
        config = configparser.ConfigParser()
        config['Settings'] = default_config['Settings']
        config['RecentProcessing'] = default_config['RecentProcessing']

        with open(config_file, 'w') as f:
            config.write(f)

        print(f"Configuration file {config_file} not found. Created one with default values.")

    return config


if __name__ == "__main__":
    print("Módulo loxx_dbzh_georeferenciado.py")
    print("Procesamiento DBZH del radar LOXX: extracción, clutter, mediana 2-D, proyección")
    print("Importar en otros scripts para usar las funciones")
