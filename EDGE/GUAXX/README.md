# EDGE node — GUAXX radar (Celica)

Edge processing node for the **GUAXX** radar (Rainscanner RS120, Cerro
Guachaurco, Celica). It watches for new radar files, runs the DBZH processing
pipeline, and uploads the resulting georeferenced PNG to the central API.

Input: NetCDF4 (`.nc4`). Center: −4.0333, −79.8667. Coverage: ~100 km.

---

## Files

| File | Purpose |
|------|---------|
| `generar_png_radar.py` | Processing pipeline. Reads one `.nc4` frame and produces an RGBA PNG using the Furuno WR110 "v8" 13-class color scale (discrete classes; transparent below 8 dBZ). |
| `radar_edge_uploader_guaxx.py` | `watchdog` service: on each new file, runs the pipeline and uploads the PNG to the API. The API key is read from `.env` / the `RADAR_API_KEY` environment variable; if absent, the service does not start. |
| `config.ini` | Radar, processing and geo configuration (input path, resolution, gain/offset, CRS, center). |
| `.env.example` | Template for the node environment (copy to `.env` and fill in). |
| `requirements.txt` | Python dependencies. |
| `.gitignore` | Excludes `.env` and generated artifacts. |
| `data_test/` | Example input frames (see the top-level README). |

---

## Requirements

Python 3.11. Install with `pip install -r requirements.txt`
(`numpy`, `netCDF4`, `rasterio`, `Pillow`, `pyproj`).

---

## Usage

Process a single frame (uses a file from `data_test/`):

```bash
python generar_png_radar.py data_test/2025040200000000dBZ.ppi_top.nc4
```

Run the uploader/watchdog (configure the API key first — see below):

```bash
python radar_edge_uploader_guaxx.py
```

---

## Configuration and security

Copy `.env.example` to `.env` and set:

- `RADAR_API_KEY` — central-API key (**required**; the uploader aborts if unset).
- `RADAR_API_URL` — API URL (defaults to `http://localhost:8000`).

The `.env` file is kept out of version control and never travels with the code;
for updates, copy only the `.py` files and leave the node's `.env` untouched.

---

## DBZH color scale — Furuno WR110 "v8"

GUAXX shares the same 13-class lookup table as the LOXX node, the web viewer and
the paper figures (levels 8–70 dBZ; transparent below 8 dBZ). See the LOXX node
README for the full LUT.

> Note: GUAXX does not apply clutter correction, so high reflectivity maxima may
> include unfiltered clutter — verify before reporting them as precipitation.
