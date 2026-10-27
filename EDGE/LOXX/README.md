# EDGE node — LOXX radar (Loja)

Edge processing node for the **LOXX** radar (Furuno WR110, Cerro El Tiro, Loja).
It watches for new radar files, runs the DBZH processing pipeline, and uploads
the resulting georeferenced PNG to the central API.

Input: ODIM HDF5 (`.h5.gz`). Coordinates: −3.989060, −79.145308 (2 850 m).
Coverage: ~70 km.

---

## Files

| File | Purpose |
|------|---------|
| `loxx_dbzh_georeferenciado.py` | Core module: DBZH extraction, clutter correction, 2-D median filter, polar→Cartesian projection with WGS84 bounds. |
| `generar_png_loxx.py` | Processing pipeline. Reads one `.h5.gz`, produces an RGBA PNG rasterized directly from the Cartesian grid with PIL (Furuno WR110 "v8" 13-class color scale). |
| `radar_edge_uploader_loxx.py` | `watchdog` service: on each new file, calls the pipeline and uploads the PNG to the API (API key read from environment / ini, never hardcoded). Failed uploads (link down, API unreachable) are appended to a persistent retry queue (`upload_retry_queue.json` in the output directory) and resent at start-up and before each new frame, so no frame is lost during an outage. |
| `clutter_cache_dbzh.pkl` | Precomputed clutter map used by the pipeline. |
| `config.ini` | Processing configuration (paths, thresholds, cache file, clutter regeneration). |
| `uploader_config.ini.example` | Template for the uploader configuration (copy to `uploader_config.ini`, git-ignored). |
| `requirements.txt` | Python dependencies. |
| `data_test/` | Example input frames (see the top-level README). |

---

## Requirements

Python 3.11. Install with `pip install -r requirements.txt`.

Production (watchdog → pipeline) needs `h5py, numpy, scipy, Pillow` — the PNG is
rasterized with PIL, so **matplotlib is not required** at runtime. `GDAL`,
`cartopy` and `pyproj` are used by the georeferencing module; on Windows they are
easiest to install with conda (`conda install gdal cartopy`).

---

## Usage

Process a single frame (uses a file from `data_test/`):

```bash
python generar_png_loxx.py data_test/20260626/1003_20260626_034500.h5.gz
```

Run the uploader/watchdog (configure the API key first — see below):

```bash
python radar_edge_uploader_loxx.py
```

Regenerating the clutter cache (optional; a precomputed
`clutter_cache_dbzh.pkl` is already provided): set `regenerate_clutter = True`
in `config.ini` and point `clutter_dir` at a set of reference frames. On the next
run the pipeline rebuilds the clutter maps with `generate_clutter_maps` and saves
them to `clutter_cache_file`; set it back to `False` afterwards.

---

## Configuration and security

The uploader reads the central-API key from the `RADAR_API_KEY` environment
variable, or from `uploader_config.ini` (copied from the `.example` template and
kept out of version control). If no key is provided, the uploader aborts instead
of sending with a default secret. The `/upload` endpoint is protected with the
`X-Api-Key` header.

---

## Processing notes

- **Undetect handling.** The Furuno WR110 uses raw value `0` as *undetect* but
  does not declare the ODIM `undetect` attribute. `extract_dbzh_data` masks raw
  `0` (→ NaN) in both data and clutter maps, and `apply_clutter_correction`
  clamps the clutter map to `>= 0 dBZ` before subtracting, so the correction can
  never amplify the signal.
- **Non-uniform azimuth.** When present, `dataset{n}/how/startazA` (the real
  start azimuth of each ray) is used to assign each Cartesian pixel to its ray
  (with wrap-around at north); otherwise a uniform ray spacing is assumed.
- **Exact-resolution PNG.** The RGBA image is rasterized 1 pixel = 1 grid cell
  (no interpolation); output size is an exact integer multiple of the grid.

## DBZH color scale — Furuno WR110 "v8"

Single 13-class lookup table, shared by the LOXX node, the GUAXX node, the web
viewer (`VISOR/src/config/radars.js`) and the paper figures. Values below
**8 dBZ** are transparent (`MIN_DBZH_THRESHOLD`). Defined in
`generar_png_loxx.py` (`DBZH_LEVELS` / `DBZH_COLORS`).

```
levels (dBZ): 8 10 15 20 25 30 35 40 45 50 55 60 65 70
RGB: (0,0,128) (0,0,180) (0,96,255) (0,200,240) (0,224,160) (0,200,0)
     (128,224,0) (255,240,0) (255,192,0) (255,128,0) (255,56,0) (224,0,0) (144,0,0)
```
