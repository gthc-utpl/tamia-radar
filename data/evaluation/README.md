# TAMIA evaluation data

Measurement records that support the operational evaluation reported in
*TAMIA: An Edge Computing System for Real-Time Processing and Visualization of
Weather Radar Reflectivity in the Tropical Andes* (Quiñones-Cuenca et al.,
submitted to *Remote Sensing*). Every number in Section 4 (Results) of the
article can be recomputed from these files with `reproduce_key_figures.py`
(Python 3.8+, standard library only):

    python reproduce_key_figures.py

The script prints each figure next to the value stated in the article.

## Conventions

* **Evaluation period:** 14 April to 13 July 2026 (91 days). `frame_registry.csv`
  and `websocket_push_latency_2026-09.csv` extend beyond it; the period filter is
  applied by the reproduction script, as described below.
* **Radars:** `loxx` = Furuno WR110, El Tiro, Loja (polar ODIM HDF5 input);
  `guaxx` = Selex RS120 RAINSCANNER, Cerro Guachaurco, Celica (gridded NetCDF4 input).
* **Time:** all columns ending in `_utc` are UTC. `timestamp_local` and
  `created_at` in `frame_registry.csv` are continental Ecuador time (UTC−5);
  `created_at` carries its offset explicitly. Timestamps are ISO 8601.
* **Nominal timestamps:** the LOXX file name encodes the **start** of the volume
  scan; the GUAXX file name encodes the **end** of its 5-min averaging window.
  Intervals measured from these timestamps are therefore not comparable between
  radars (Section 4.2 of the article).
* **Sizes** are in bytes. The article quotes kilobytes computed as bytes/1024.
* **Times** are in seconds (`_s`) or milliseconds (`_ms`); reflectivity in dBZ.
* **File names:** raw LOXX volumes `1003_YYYYMMDD_HHMMSS.h5.gz`; raw GUAXX
  products `YYYYMMDDHHMMSS00dBuZ.ppi_top.nc4`; published frames
  `radar_<radar_id>_YYYYMMDDHHMMSS.png` (nominal UTC timestamp).

## Files

### frame_registry.csv — 30 581 rows
Export of the `radar_frames` table of the central API database on 15 September
2026 (all frames published since the start of operation). Supports Table 3
(availability), the measured intervals of Section 4.2, the PNG sizes of
Section 4.3 and the archive figures of Section 5.5.

| column | meaning |
|---|---|
| `id` | database primary key (monotonic, in order of registration) |
| `radar_id` | `loxx` or `guaxx` |
| `filename` | published PNG |
| `timestamp_local` | nominal timestamp of the frame, UTC−5 |
| `timestamp_utc` | nominal timestamp of the frame, UTC |
| `size_bytes` | size of the published PNG |
| `created_at` | instant of registration on the server (server clock, UTC−5, with offset) |

Notes: the export starts at `id` 140; lower identifiers are not present.
Four LOXX frames of July–August 2026 (outside the evaluation period) were
registered twice, about five minutes apart, with identical name and size; they
are kept as recorded and do not affect any figure of the article.

Rules used in the article: *availability on active days* and *capture rate*
count frames per calendar day (`timestamp_local`) against 288 expected; a
*day of sustained operation* has ≥ 280 frames. The *steady-state latency*
(nominal timestamp → registration) uses frames with `timestamp_utc` in the
period, excludes any frame registered less than 60 s after the previous one
(recovery bursts) and keeps intervals between 3 and 600 s; this gives
N = 13 055 (LOXX) and N = 2 373 (GUAXX).

### loxx_node_raw_arrival.csv — 23 776 rows
Every raw volume of the evaluation period preserved in the archive of the LOXX
edge node, with the file-system modification time recorded at the node
(converted from the node clock, UTC−5, to UTC). Supports the first row of
Table 4 and Section 4.2.

| column | meaning |
|---|---|
| `filename` | raw volume |
| `scan_start_utc` | nominal scan start, from the file name |
| `node_mtime_utc` | modification time of the file at the node |
| `arrival_delay_s` | `node_mtime_utc` − `scan_start_utc` |

Rule: files with `arrival_delay_s` ≤ 600 s are the steady-state sample
(N = 19 484; 286 ± 21 s); the remaining 4 292 arrived hours to days late through
the transmission queue of the acquisition workstation, or were touched by the
periodic backup.

### loxx_reprocessing_hourly.csv — 1 982 rows
Controlled reprocessing of the production module on the LOXX node hardware,
one raw file per hour over the evaluation period, with per-stage timings
(`time.perf_counter`) and resource use (`psutil`). Supports Table 5 and
Section 4.3. Frames with `has_echo` = 1 (N = 1 972) are the valid sample.

| column | meaning |
|---|---|
| `filename` | raw volume |
| `date`, `datetime_utc` | nominal scan time (UTC), from the file name |
| `total_ms` | wall-clock time of the whole chain, decompression included |
| `decompression_ms` | `.h5.gz` → `.h5` |
| `extraction_ms` | DBZH extraction and median filter, five elevations |
| `clutter_ms` | clutter correction and gap filling |
| `projection_ms` | polar-to-Cartesian transformation and georeferencing |
| `filters_ms` | optional texture/isolation filters; always 0 because they are disabled in production |
| `png_ms` | PNG generation and encoding |
| `other_ms` | multi-elevation compositing, bounds and remaining operations |
| `cpu_pct` | CPU share of the process during the frame; values above 100 % (14 of 1 972 frames) occur when NumPy briefly uses a second core |
| `rss_mib` | resident memory of the process, MiB |
| `png_size_bytes` | size of the reprocessed PNG (0 when no image was produced) |
| `has_echo` | 1 if the module produced a PNG; 0 if no echo remained above the 8 dBZ floor after processing, in which case no image is generated |

### loxx_reprocessing_june_full.csv — 3 744 rows
Same procedure at the native 5-min cadence, 14–26 June 2026 (13 days × 288),
used to check the hourly sampling (mean 2.50 s versus 2.72 s; Section 3.5).
Columns as in `loxx_reprocessing_hourly.csv`; only the total time was recorded.

### guaxx_reprocessing.csv — 3 390 rows
Controlled reprocessing of the GUAXX module on the raw NetCDF4 files available
on that node (14–26 June 2026). Supports Section 4.3 (65.8 ± 8.7 ms).
Columns as in `loxx_reprocessing_june_full.csv`, plus `width_px` and
`height_px`, the size of the output PNG (the native grid, 999 × 1002).

### loxx_clutter_leave_one_out.csv — 28 rows
Leave-one-out evaluation of the clutter correction on the 28 clear-air scans of
1 December 2025 (procedure C of Section 3.5). For each scan, a reference map
built from the other 27 is applied to it. Pixel counts are over the Cartesian
composite above the 8 dBZ floor. Supports Table 6 and Section 4.4.

| column | meaning |
|---|---|
| `echo_px_before` | echo pixels of the uncorrected composite |
| `echo_px_after_heldout` | pixels remaining after correction with the map built from the other 27 scans |
| `echo_px_after_insample` | pixels remaining after correction with the map built from all 28 scans |
| `reduction_heldout_pct`, `reduction_insample_pct` | 100 × (1 − after / before) for that scan |
| `residual_mean_dbz_heldout`, `residual_max_dbz_heldout` | mean and maximum reflectivity of the remaining pixels (held-out map) |

The 98.78 % and 99.98 % of the article are computed on the sums over the 28
scans. The 13.4 dBZ is the unweighted mean of `residual_mean_dbz_heldout` over
the 28 scans.

### loxx_composite_vs_lowest_beam.csv — 311 rows
Pixel-by-pixel comparison of the operational composite (maximum over the five
elevations, −1.5° to 4.5°, exactly as in production) against the lowest
elevation alone (−1.5°) and against the 0° elevation, for every raw file of the
26 June 2026 event (procedure D). Pixels are compared where both fields have
echo above 8 dBZ. Aggregates in the article are weighted by the number of
pixels compared.

| column | meaning |
|---|---|
| `n_elevations`, `elangle_min`, `elangle_max` | elevations in the volume and their range (degrees) |
| `n_px_compared` | pixels with echo in both the composite and the −1.5° field |
| `mean_diff_dbz`, `p95_diff_dbz`, `max_diff_dbz` | composite − lowest elevation, over those pixels (dBZ) |
| `pct_px_max_above_lowest` | % of those pixels where a higher elevation supplies the maximum |
| `pct_px_max_equals_lowest` | % of those pixels where the −1.5° beam supplies the maximum |
| `n_px_compared_0deg`, `pct_px_max_equals_0deg` | the same comparison against the 0° elevation |

### loxx_reprocessing_vs_production_2026-06-26.csv — 288 rows
Byte and pixel comparison between the frames of 26 June 2026 reprocessed offline
and the PNGs retrieved from the public API (Section 3.5). All 288 are identical.

| column | meaning |
|---|---|
| `status` | `identical` when both files are byte-identical |
| `reprocessed_bytes`, `production_bytes` | file sizes |
| `n_px_total` | pixels per image (949 × 949) |
| `n_px_different`, `pct_px_different` | pixels whose RGBA value differs |
| `max_abs_diff`, `mean_abs_diff` | maximum and mean absolute difference of the RGBA channels |

### websocket_push_latency_2026-09.csv — 229 rows
Independent WebSocket client subscribed to the public channel on 15–17 September
2026 (procedure E). `push_s` = reception at the client − registration in the
database; negative values of a few tenths of a second reflect the clock offset
between client and server. Supports Section 4.2 (median 0.03 s, P95 0.12 s).

| column | meaning |
|---|---|
| `scan_utc` | nominal scan time (UTC) |
| `created_at_utc` | registration in the database (UTC) |
| `recv_ws_utc` | reception of the `NEW_RADAR_FRAME` message at the client (UTC, client clock) |
| `push_s` | `recv_ws_utc` − `created_at_utc` |
| `scan_to_registration_s`, `scan_to_client_s` | interval from the nominal scan time to registration and to reception |
| `after_client_reconnection` | 1 if received within 180 s of a client reconnection (6 frames); reported, not excluded |

### loxx_daily_frame_balance.csv — 84 rows
For each of the 84 days of the period with at least one raw file: raw files
generated at the node, frames published, frames missing at the source (fewer
than 288 scans) and frames that never reached the API. Supports the loss
decomposition of Section 4.1 (416 missing at source; 6 290 attributable to the
system, 5 085 of them in the June episode: 5–21 June without any registration plus the partial recovery day of 22 June).

| column | meaning |
|---|---|
| `date` | calendar day (UTC−5) |
| `raw_files_at_node` | raw volumes generated that day, from the node archive |
| `frames_published` | frames registered in the API for that day |
| `missing_at_source_vs_288` | 288 − `raw_files_at_node`: scans the instrument did not produce |
| `missing_attributable_to_system` | `raw_files_at_node` − `frames_published`: volumes generated but never published |
The four days of degraded delivery that preceded the episode (1–4 June, 748 frames) are counted among the remaining 1 205.

### link_throughput_2026-10-26.csv — 8 rows
Spot measurements of the Internet link of each site, taken simultaneously from
the two node computers (wired) on 26 October 2026, after the evaluation period,
with three browser-based tests and one command-line tool. Supports the upstream
throughput quoted in Section 3.4 (45–51 Mbps at LOXX, 68–94 Mbps at GUAXX, from
the two tests that report upload against servers in Ecuador). The two rows
against Rio de Janeiro are kept because they show how much a distant server
depresses the result (175–183 ms round trip); they are not used in the article.
Both sites are served by the same provider (AS266894).

| column | meaning |
|---|---|
| `site` | `LOXX` or `GUAXX` |
| `local_time` | start of the test, continental Ecuador time (UTC−5); the GUAXX node clock runs on UTC and its screenshots show 21:5x |
| `tool` | test used |
| `server_location` | remote end of the test |
| `download_mbps`, `upload_mbps` | reported throughput, Mbit/s; empty when the test does not report it |
| `idle_latency_ms` | unloaded round-trip latency reported by the test |
| `packet_loss_pct` | packet loss reported by the test (Cloudflare only) |
| `result_id` | public result identifier (Ookla), when available |

## Licence

The data in this directory are released under the Creative Commons Attribution
4.0 International License (CC BY 4.0); see `DATA_LICENSE.txt`. The source code of
the system, including `reproduce_key_figures.py`, is distributed under the MIT
License (see the `LICENSE` file at the repository root).

## Provenance

Exports were produced with the scripts kept in the authors' working repository
(`mediciones/`), run on the API server, on the LOXX node and on the GUAXX node
between July and September 2026; the link throughput tests of October 2026 were read from the tools' screens and transcribed. Column names were translated to English and
the node clock converted to UTC for publication; no value was altered.
