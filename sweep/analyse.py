#!/usr/bin/env python3
"""Analyse the completed sweep: where does Mumbai have usable resolution?

Two questions this answers:
  1. Per zone of the city -- how many segments, and what share are short
     enough (0.1-3 km, freeflow >= 10) to measure a single junction?
  2. For each existing monitoring point in corridors.csv -- is there a clean
     candidate segment nearby to re-site onto?

Usage:  python sweep/analyse.py [--csv]     (--csv writes candidates.csv)
"""
import argparse
import csv
import json
import math
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent

# name, lat_min, lat_max, lon_min, lon_max  (generous, first match wins)
ZONES = [
    ("South Mumbai (Colaba-Byculla)", 18.87, 18.99, 72.77, 72.90),
    ("Central (Dadar-Sion-Matunga)", 18.99, 19.06, 72.80, 72.89),
    ("Bandra-Khar-Santacruz + BKC", 19.04, 19.11, 72.81, 72.88),
    ("Kurla-Chembur-Ghatkopar", 19.02, 19.12, 72.88, 72.95),
    ("Andheri-Jogeshwari-Powai", 19.11, 19.16, 72.81, 72.95),
    ("Goregaon-Malad-Borivali-Dahisar", 19.16, 19.30, 72.80, 72.90),
    ("Bhandup-Mulund-Thane", 19.12, 19.30, 72.90, 73.00),
]


def zone_of(lat, lon):
    for name, la0, la1, lo0, lo1 in ZONES:
        if la0 <= lat < la1 and lo0 <= lon < lo1:
            return name
    return "other / edge"


def centroid(geom):
    return (sum(p[0] for p in geom) / len(geom), sum(p[1] for p in geom) / len(geom))


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_clean(s):
    return 0.1 <= s["km"] <= 3 and s["ff"] and s["ff"] >= 10


def nearest_point_on_seg(lat, lon, geom):
    """Distance from (lat,lon) to the closest vertex of a segment."""
    return min(haversine_m(lat, lon, a, b) for a, b in geom)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help="write candidates.csv")
    args = ap.parse_args()

    st = json.loads((SP / "sweep_state.json").read_text())
    segs = []
    for sid, s in st["segments"].items():
        if not s["geom"]:
            continue
        la, lo = centroid(s["geom"])
        segs.append({**s, "id": sid, "lat": la, "lon": lo, "zone": zone_of(la, lo),
                     "clean": is_clean(s)})

    # ---------------------------------------------------------------- zones
    print("=" * 78)
    print("RESOLUTION BY ZONE  (clean = 0.1-3 km and freeflow >= 10 km/h)")
    print("=" * 78)
    print(f"{'zone':<34}{'segs':>6}{'clean':>7}{'%':>6}{'median km':>11}{'>3km':>7}")
    order = [z[0] for z in ZONES] + ["other / edge"]
    for zname in order:
        z = [s for s in segs if s["zone"] == zname]
        if not z:
            continue
        clean = [s for s in z if s["clean"]]
        med = sorted(s["km"] for s in z)[len(z) // 2]
        long_n = sum(1 for s in z if s["km"] > 3)
        print(f"{zname:<34}{len(z):>6}{len(clean):>7}{len(clean)/len(z)*100:>5.0f}%"
              f"{med:>11.2f}{long_n:>7}")
    allc = [s for s in segs if s["clean"]]
    print(f"{'TOTAL':<34}{len(segs):>6}{len(allc):>7}{len(allc)/len(segs)*100:>5.0f}%")

    # ------------------------------------------------- existing points
    with open(ROOT / "corridors.csv", newline="", encoding="utf-8") as f:
        points = list(csv.DictReader(f))

    print()
    print("=" * 78)
    print("EXISTING MONITORING POINTS vs nearest clean segment")
    print("=" * 78)
    print(f"{'point_id':<20}{'nearest clean':>14}{'len km':>8}{'frc':>6}  zone")
    rows = []
    for pt in points:
        la, lo = float(pt["lat"]), float(pt["lon"])
        best, bestd = None, float("inf")
        for s in allc:
            d = nearest_point_on_seg(la, lo, s["geom"])
            if d < bestd:
                best, bestd = s, d
        rows.append((pt["point_id"], bestd, best))
        print(f"{pt['point_id']:<20}{bestd:>12.0f} m{best['km']:>8.2f}{best['frc']:>6}  "
              f"{best['zone']}")

    far = [r for r in rows if r[1] > 300]
    print(f"\n{len(rows)-len(far)}/{len(rows)} points have a clean segment within 300 m.")
    if far:
        print("Further than 300 m (re-siting would move the point noticeably):")
        for pid, d, _ in sorted(far, key=lambda r: -r[1]):
            print(f"  {pid:<20}{d:>7.0f} m")

    if args.csv:
        out = SP / "candidates.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["segment_id", "lat", "lon", "km", "frc", "freeflow_kmph",
                        "probe_hits", "zone"])
            for s in sorted(allc, key=lambda s: (s["zone"], s["km"])):
                w.writerow([s["id"], f"{s['lat']:.5f}", f"{s['lon']:.5f}", s["km"],
                            s["frc"], s["ff"], s["hits"], s["zone"]])
        print(f"\nwrote {out}  ({len(allc)} clean candidates)")


if __name__ == "__main__":
    main()
