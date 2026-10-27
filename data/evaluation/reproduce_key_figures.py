"""Recompute the key figures of the TAMIA article from the CSV files in this folder.
Standard library only. Run:  python reproduce_key_figures.py
"""
import csv, os, statistics as st
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
P0, P1 = "2026-04-14", "2026-07-13"


def rows(name):
    with open(os.path.join(HERE, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ts(s):
    s = s.replace("T", " ")
    if len(s) > 6 and s[-6] in "+-" and s[-3] == ":":
        s = s[:-6]
    return datetime.fromisoformat(s)


def p95(x):
    x = sorted(x); return x[int(round(0.95 * len(x))) - 1]


def show(label, value, paper):
    print(f"{label:58s} {value:>18s}   article: {paper}")


fr = rows("frame_registry.csv")
print("== Table 3: availability (frame_registry.csv)")
for radar in ("loxx", "guaxx"):
    sel = [r for r in fr if r["radar_id"] == radar and P0 <= r["timestamp_local"][:10] <= P1]
    per_day = {}
    for r in sel:
        per_day[r["timestamp_local"][:10]] = per_day.get(r["timestamp_local"][:10], 0) + 1
    sust = {d: n for d, n in per_day.items() if n >= 280}
    show(f"{radar}: published frames", str(len(sel)), {"loxx": "17 486", "guaxx": "2 373"}[radar])
    show(f"{radar}: days with data / days >= 280 frames", f"{len(per_day)} / {len(sust)}", {"loxx": "67 / 54", "guaxx": "13 / 6"}[radar])
    show(f"{radar}: capture rate on sustained days (%)", f"{100 * sum(sust.values()) / (288 * len(sust)):.1f}", {"loxx": "99.9", "guaxx": "99.4"}[radar])
    sizes = [int(r["size_bytes"]) for r in sel]
    show(f"{radar}: mean PNG size (bytes/1024)", f"{st.mean(sizes) / 1024:.1f}", {"loxx": "52.3", "guaxx": "32.6"}[radar])

print("== Section 4.2: steady-state interval nominal timestamp -> registration")
for radar in ("loxx", "guaxx"):
    sel = sorted([r for r in fr if r["radar_id"] == radar and P0 <= r["timestamp_utc"][:10] <= P1], key=lambda r: r["created_at"])
    lat, bursts, prev = [], 0, None
    for r in sel:
        c = ts(r["created_at"]); L = (c + timedelta(hours=5) - ts(r["timestamp_utc"])).total_seconds()
        if prev is not None and (c - prev).total_seconds() < 60:
            bursts += 1
        elif 3 <= L <= 600:
            lat.append(L)
        prev = c
    show(f"{radar}: mean +- sd (median; P95; N)", f"{st.mean(lat):.1f} +- {st.stdev(lat):.1f} ({st.median(lat):.1f}; {p95(lat):.1f}; {len(lat)})",
         {"loxx": "299.3 +- 20.2 (293.0; 345.3; 13 055)", "guaxx": "28.9 +- 9.5 (32.4; 38.2; 2 373)"}[radar])
    if radar == "loxx":
        show("loxx: frames registered in recovery bursts", str(bursts), "4 357 (24.9 %)")

ar = rows("loxx_node_raw_arrival.csv")
d = [float(r["arrival_delay_s"]) for r in ar]
steady = [x for x in d if x <= 600]
show("Table 4 row 1: LOXX arrival delay at node, mean +- sd (median; N)", f"{st.mean(steady):.0f} +- {st.pstdev(steady):.0f} ({st.median(steady):.1f}; {len(steady)})", "286 +- 21 (281.1; 19 484)")
show("   files excluded (arrived late)", str(len(d) - len(steady)), "4 292")

print("== Section 4.3: controlled reprocessing")
rp = [r for r in rows("loxx_reprocessing_hourly.csv") if r["has_echo"] == "1"]
t = [float(r["total_ms"]) for r in rp]
show("LOXX total per frame, mean (median; P95; max; N) ms", f"{st.mean(t):.1f} ({st.median(t):.1f}; {p95(t):.0f}; {max(t):.0f}; {len(t)})", "2 717.4 (1 570; 8 390; 21 400; 1 972)")
for col, paper in (("decompression_ms", "115.7"), ("extraction_ms", "42.8"), ("clutter_ms", "829.4"), ("projection_ms", "1 089.8"), ("png_ms", "604.6"), ("other_ms", "35.2")):
    v = [float(r[col]) for r in rp]
    show(f"   Table 5: {col} mean +- sd", f"{st.mean(v):.1f} +- {st.pstdev(v):.1f}", paper)
mem = [float(r["rss_mib"]) for r in rp]
show("   resident memory, mean MiB", f"{st.mean(mem):.0f}", "~172")
tg = [float(r["total_ms"]) for r in rows("guaxx_reprocessing.csv")]
show("GUAXX total per frame, mean +- sd (median; max; N) ms", f"{st.mean(tg):.1f} +- {st.pstdev(tg):.1f} ({st.median(tg):.1f}; {max(tg):.1f}; {len(tg)})", "65.8 +- 8.7 (62.8; 108.4; 3 390)")
tf = rows("loxx_reprocessing_june_full.csv")
show("LOXX full-cadence run: days; N; mean ms", f"{len(set(r['date'] for r in tf))}; {len(tf)}; {st.mean(float(r['total_ms']) for r in tf):.0f}", "13; 3 744; 2 500")

print("== Section 4.4: product quality")
ho = rows("loxx_clutter_leave_one_out.csv")
b = sum(int(r["echo_px_before"]) for r in ho); a = sum(int(r["echo_px_after_heldout"]) for r in ho); i = sum(int(r["echo_px_after_insample"]) for r in ho)
show("clutter LOO: echo px before; after held-out; after in-sample", f"{b}; {a}; {i}", "359 842; 4 395; 89")
show("clutter LOO: reduction held-out / in-sample (%)", f"{100 * (1 - a / b):.2f} / {100 * (1 - i / b):.2f}", "98.78 / 99.98")
show("clutter LOO: mean residual dBZ (mean of per-scan means)", f"{st.mean(float(r['residual_mean_dbz_heldout']) for r in ho):.2f}", "13.4")
cp = rows("loxx_composite_vs_lowest_beam.csv")
n = sum(int(r["n_px_compared"]) for r in cp)
show("composite: elevations per volume; lowest elevation", f"{sorted(set(r['n_elevations'] for r in cp))}; {sorted(set(r['elangle_min'] for r in cp))}", "[5]; [-1.5]")
show("composite vs -1.5 deg: pixel comparisons; lowest beam = max (%)", f"{n}; {sum(float(r['pct_px_max_equals_lowest']) * int(r['n_px_compared']) for r in cp) / n:.1f}", "3155725; 9.2")
show("   pixel-weighted mean excess of the composite (dBZ)", f"{sum(float(r['mean_diff_dbz']) * int(r['n_px_compared']) for r in cp) / n:.2f}", "5.75")
show("   P95 of the per-frame P95 differences; largest single-pixel difference (dBZ)", f"{st.quantiles([float(r['p95_diff_dbz']) for r in cp], n=20)[18]:.1f}; {max(float(r['max_diff_dbz']) for r in cp):.1f}", "17.5; 32.5")
n0 = sum(int(r["n_px_compared_0deg"]) for r in cp)
show("composite vs 0 deg: pixel comparisons; 0 deg beam = max (%)", f"{n0}; {sum(float(r['pct_px_max_equals_0deg']) * int(r['n_px_compared_0deg']) for r in cp) / n0:.1f}", "8138974; 32.6")
cm = rows("loxx_reprocessing_vs_production_2026-06-26.csv")
show("reprocessing vs production: identical / total", f"{sum(1 for r in cm if r['status'] == 'identical')} / {len(cm)}", "288 / 288")

print("== Section 4.2: WebSocket push")
ws = [float(r["push_s"]) for r in rows("websocket_push_latency_2026-09.csv")]
show("push latency: median; P95; max; N (s)", f"{st.median(ws):.2f}; {p95(ws):.2f}; {max(ws):.2f}; {len(ws)}", "0.03; 0.12; 0.61; 229")

print("== Section 4.1: LOXX loss decomposition (loxx_daily_frame_balance.csv)")
db = rows("loxx_daily_frame_balance.csv")
show("days with raw files; raw files; published", f"{len(db)}; {sum(int(r['raw_files_at_node']) for r in db)}; {sum(int(r['frames_published']) for r in db)}", "84; 23 776; 17 486")
show("missing at source; attributable to the system", f"{sum(int(r['missing_at_source_vs_288']) for r in db)}; {sum(int(r['missing_attributable_to_system']) for r in db)}", "416; 6 290")
show("   of which in the June episode (5-22 June 2026, incl. recovery day)", str(sum(int(r["missing_attributable_to_system"]) for r in db if "2026-06-05" <= r["date"] <= "2026-06-22")), "5 085")
