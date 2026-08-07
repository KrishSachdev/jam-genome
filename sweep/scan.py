"""Map TomTom's REAL segment boundaries.

Two scans:
  A) transect along the WEH polyline (Mahim -> Dahisar), to find where the
     mainline segment actually changes -- i.e. how many distinct mainline
     nodes WEH can support at all.
  B) micro-grid around Kalanagar junction, to enumerate the distinct
     junction-layer segments available there.

Segment identity = hash of the returned geometry (first/last vertex + count),
which is exact, rather than inferring from travel time.
"""
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
key = next(l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
           if l.startswith("TOMTOM_API_KEY="))

CALLS = 0


def call(lat, lon):
    global CALLS
    CALLS += 1
    url = ("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?"
           + urllib.parse.urlencode({"point": f"{lat:.5f},{lon:.5f}", "unit": "KMPH", "key": key}))
    with urllib.request.urlopen(url, timeout=20) as r:
        s = json.load(r)["flowSegmentData"]
    co = s.get("coordinates", {}).get("coordinate", [])
    if co:
        sig = (f"{co[0]['latitude']:.5f},{co[0]['longitude']:.5f}|"
               f"{co[-1]['latitude']:.5f},{co[-1]['longitude']:.5f}|{len(co)}")
    else:
        sig = f"nogeom|{s['freeFlowTravelTime']}|{s['freeFlowSpeed']}"
    seg = hashlib.md5(sig.encode()).hexdigest()[:6]
    s["_seg"] = seg
    s["_len_km"] = s["freeFlowSpeed"] * s["freeFlowTravelTime"] / 3600
    return s


# ---- A) WEH transect -------------------------------------------------------
# waypoints south -> north, taken from corridors.csv so we stay on the road
WEH = [
    (19.0420, 72.8410),    # Mahim
    (19.0525, 72.8425),    # Kalanagar
    (19.0600, 72.8470),    # Kherwadi
    (19.09324, 72.85071),  # Vile Parle
    (19.10557, 72.85385),  # Airport
    (19.1235, 72.8565),    # JVLR
    (19.17283, 72.85936),  # Goregaon
    (19.18607, 72.85845),  # Malad
    (19.22893, 72.86342),  # Borivali
    (19.24797, 72.86508),  # Dahisar
]


def interpolate(pts, step_km=1.5):
    out = []
    for (la, lo), (lb, lob) in zip(pts, pts[1:]):
        d = (((la - lb) * 111) ** 2 + ((lo - lob) * 111 * 0.945) ** 2) ** 0.5
        n = max(1, int(d / step_km))
        for i in range(n):
            f = i / n
            out.append((la + (lb - la) * f, lo + (lob - lo) * f))
    out.append(pts[-1])
    return out


print("=== SCAN A: WEH mainline transect (south -> north, ~1.5 km steps) ===")
print(f"{'#':>3}{'lat':>10}{'lon':>10}{'frc':>6}{'ff':>5}{'len_km':>8}  segment")
prev = None
rows = []
for i, (la, lo) in enumerate(interpolate(WEH, 1.5)):
    try:
        s = call(la, lo)
    except Exception as e:
        print(f"{i:>3}  ERROR {e}")
        continue
    mark = "" if s["_seg"] == prev else "   <-- NEW SEGMENT"
    print(f"{i:>3}{la:>10.5f}{lo:>10.5f}{s['frc']:>6}{s['freeFlowSpeed']:>5}"
          f"{s['_len_km']:>8.2f}  {s['_seg']}{mark}")
    rows.append((la, lo, s["_seg"], s["frc"], s["_len_km"]))
    prev = s["_seg"]
    time.sleep(0.3)

uniq = []
for r in rows:
    if not uniq or uniq[-1] != r[2]:
        uniq.append(r[2])
print(f"\n{len(rows)} samples over ~23 km of WEH -> {len(set(r[2] for r in rows))} distinct segments "
      f"({len(uniq)} boundary crossings)")

# ---- B) Kalanagar micro-grid ----------------------------------------------
print("\n=== SCAN B: Kalanagar junction micro-grid (~600 m box) ===")
print(f"{'lat':>10}{'lon':>10}{'frc':>6}{'ff':>5}{'len_km':>8}  segment")
seen = {}
base_la, base_lo = 19.0540, 72.8420
for dla in (-0.003, 0.0, 0.003):
    for dlo in (-0.003, 0.0, 0.003):
        la, lo = base_la + dla, base_lo + dlo
        try:
            s = call(la, lo)
        except Exception as e:
            print(f"{la:>10.5f}{lo:>10.5f}  ERROR {e}")
            continue
        print(f"{la:>10.5f}{lo:>10.5f}{s['frc']:>6}{s['freeFlowSpeed']:>5}"
              f"{s['_len_km']:>8.2f}  {s['_seg']}")
        seen.setdefault(s["_seg"], (s["frc"], s["_len_km"], la, lo))
        time.sleep(0.3)

print(f"\ndistinct segments found near Kalanagar: {len(seen)}")
for seg, (frc, ln, la, lo) in sorted(seen.items(), key=lambda kv: kv[1][1]):
    print(f"  {seg}  frc={frc:<5} len={ln:6.2f} km   sample point ({la:.5f}, {lo:.5f})")

print(f"\nTOTAL API CALLS USED: {CALLS}")
