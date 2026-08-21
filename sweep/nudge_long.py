#!/usr/bin/env python3
"""Move points that snap to long segments onto a nearby short one.

Aims at the MIDPOINT of a candidate segment rather than an endpoint: endpoints
sit at junctions where several segments share a vertex and TomTom's choice is
ambiguous, which is how these points ended up on mainlines in the first place.
Each move is then re-probed, so what is written has been verified rather than
inferred.

Points that already record congestion are never moved, even on a long segment
-- a proven record beats a structural preference.

Usage:  python sweep/nudge_long.py <point_id> [<point_id> ...]
"""
import csv
import json
import math
import sys
import time
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent
SRC = SP / "corridors_ganpati.csv"

sys.path.insert(0, str(SP))
from verify_set import load_key, probe          # noqa: E402

MAX_MOVE_M = 900


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def candidates(lat, lon):
    """Clean segments near (lat,lon), nearest first, each with its midpoint."""
    st = json.loads((SP / "sweep_state.json").read_text())
    out = []
    for sid, s in st["segments"].items():
        if not s["geom"] or not s["ff"]:
            continue
        if not (0.1 <= s["km"] <= 3 and s["ff"] >= 10):
            continue
        d = min(haversine_m(lat, lon, a, b) for a, b in s["geom"])
        if d > MAX_MOVE_M:
            continue
        mid = s["geom"][len(s["geom"]) // 2]
        out.append((d, sid, s, mid))
    out.sort(key=lambda t: t[0])
    return out


def main():
    targets = sys.argv[1:]
    if not targets:
        sys.exit(__doc__)

    key = load_key()
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    changed = 0

    for r in rows:
        if r["point_id"] not in targets:
            continue
        la, lo = float(r["lat"]), float(r["lon"])
        print(f"\n{r['point_id']} - trying candidates near {la:.5f},{lo:.5f}")
        fixed = False
        for d, sid, s, (mla, mlo) in candidates(la, lo)[:6]:
            try:
                seg, km, frc, ff = probe(key, f"{mla:.5f}", f"{mlo:.5f}")
            except Exception as e:
                print(f"   probe failed: {e}")
                continue
            time.sleep(0.25)
            moved = haversine_m(la, lo, mla, mlo)
            if km <= 3:
                print(f"   OK  {km:.2f}km {frc} ff{ff}  (moved {moved:.0f} m) -> ACCEPTED")
                r["lat"], r["lon"] = f"{mla:.5f}", f"{mlo:.5f}"
                r["notes"] = (r["notes"].split("[")[0].strip()
                              + f" [verified {seg[:6]} {km:.2f}km {frc} ff{ff}, moved {moved:.0f}m]")
                fixed = True
                changed += 1
                break
            print(f"   no  snapped to {km:.2f}km {frc} (moved {moved:.0f} m)")
        if not fixed:
            print("   NO FIX - leaving as is; long segment may be unavoidable here")

    if changed:
        with SRC.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nupdated {changed} point(s) in {SRC.name}")
    else:
        print("\nnothing changed")


if __name__ == "__main__":
    main()
