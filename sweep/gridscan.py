"""Dense grid probe -> enumerate every distinct TomTom segment in a real area.

The original resolution study (26 Jul 2026): covers the Kalanagar / Kherwadi /
BKC-entry box (~2.4 km square) at ~260 m spacing. Saves full segment geometry
so the result can be drawn on a map by build_map.py.

This is what established the project's central data caveat: 100 probes over
one junction returned many distinct segments, several of them >10 km long.
"""
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent
OUT = SP / "segments.json"
key = next(l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
           if l.startswith("TOMTOM_API_KEY="))

CENTER = (19.0550, 72.8450)
HALF = 0.0110          # ~1.22 km each way
N = 10                 # 10x10 grid -> 100 probes, ~260 m spacing

segments = {}
probes = []
calls = 0

for i in range(N):
    for j in range(N):
        lat = CENTER[0] - HALF + (2 * HALF) * i / (N - 1)
        lon = CENTER[1] - HALF + (2 * HALF) * j / (N - 1)
        url = ("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?"
               + urllib.parse.urlencode({"point": f"{lat:.5f},{lon:.5f}", "unit": "KMPH", "key": key}))
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                s = json.load(r)["flowSegmentData"]
            calls += 1
        except Exception as e:
            print("ERR", lat, lon, e)
            continue
        co = [(c["latitude"], c["longitude"]) for c in s.get("coordinates", {}).get("coordinate", [])]
        sig = f"{co[0]}|{co[-1]}|{len(co)}" if co else f"{s['freeFlowTravelTime']}|{s['freeFlowSpeed']}"
        seg = hashlib.md5(sig.encode()).hexdigest()[:8]
        probes.append({"lat": lat, "lon": lon, "seg": seg})
        if seg not in segments:
            segments[seg] = {
                "seg": seg,
                "frc": s.get("frc"),
                "ff_speed": s.get("freeFlowSpeed"),
                "ff_tt": s.get("freeFlowTravelTime"),
                "cur_speed": s.get("currentSpeed"),
                "len_km": round(s["freeFlowSpeed"] * s["freeFlowTravelTime"] / 3600, 3),
                "n_vertices": len(co),
                "geom": co,
                "hits": 0,
            }
        segments[seg]["hits"] += 1
        time.sleep(0.25)

OUT.write_text(json.dumps({"center": CENTER, "half": HALF, "probes": probes,
                           "segments": list(segments.values())}, indent=1))

print(f"probes: {len(probes)}  api calls: {calls}")
print(f"distinct segments found: {len(segments)}\n")
rows = sorted(segments.values(), key=lambda s: s["len_km"])
print(f"{'seg':>10}{'frc':>6}{'ff':>5}{'len_km':>9}{'verts':>7}{'probes':>8}")
for s in rows:
    print(f"{s['seg']:>10}{str(s['frc']):>6}{s['ff_speed']:>5}{s['len_km']:>9.2f}"
          f"{s['n_vertices']:>7}{s['hits']:>8}")

short = [s for s in rows if s["len_km"] <= 3]
print(f"\nusable (<=3 km): {len(short)} of {len(rows)}")
print(f"saved -> {OUT}")
