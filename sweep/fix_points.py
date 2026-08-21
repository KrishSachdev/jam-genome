#!/usr/bin/env python3
"""Propose corrected coordinates for monitoring points sitting on long segments.

For each point in corridors.csv, find the nearest sweep segment that is both
usable (0.1-3 km, freeflow >= 10) AND of an appropriate road class, then
reverse-geocode it so the replacement can be eyeballed before adoption.

Road-class constraint matters: nudging a WEH point 250 m without it can land
on a service lane or a BKC side street, which silently changes what you are
measuring. Expressway points therefore only accept FRC0-FRC2.

Writes corridors_fixed.csv -- same point_ids, so the 29 days already
collected stay joinable.

Usage:  python sweep/fix_points.py [--no-geocode]
"""
import argparse
import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent

EXPRESSWAY = {"WEH", "EEH"}          # corridors that must stay on the mainline
MAX_MOVE_M = 700                     # beyond this it is a different place


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def frc_num(frc):
    return int(frc[-1]) if frc and frc[-1].isdigit() else 9


def load_segments():
    st = json.loads((SP / "sweep_state.json").read_text())
    out = []
    for sid, s in st["segments"].items():
        if not s["geom"] or not s["ff"]:
            continue
        if not (0.1 <= s["km"] <= 3 and s["ff"] >= 10):
            continue
        out.append({"id": sid, **s})
    return out


def load_jams():
    p = ROOT / "analysis" / "outputs" / "league_table.csv"
    if not p.exists():
        return {}
    return {r["point_id"]: int(r["congested_slots"])
            for r in csv.DictReader(p.open(encoding="utf-8"))}


def best_replacement(pt, segs):
    """Closest usable segment of acceptable class; returns (segment, vertex, dist)."""
    max_frc = 2 if pt["corridor"] in EXPRESSWAY else 4
    la, lo = float(pt["lat"]), float(pt["lon"])
    best = None
    for s in segs:
        if frc_num(s["frc"]) > max_frc:
            continue
        for a, b in s["geom"]:
            d = haversine_m(la, lo, a, b)
            if best is None or d < best[2]:
                best = (s, (a, b), d)
    return best


def geocode(key, lat, lon):
    url = ("https://api.tomtom.com/search/2/reverseGeocode/"
           f"{lat},{lon}.json?" + urllib.parse.urlencode({"key": key, "radius": 100}))
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            a = (json.load(r)["addresses"] or [{}])[0].get("address", {})
    except Exception:
        return "?"
    return ", ".join(x for x in (a.get("streetName"),
                                 a.get("municipalitySubdivision")) if x) or "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-geocode", action="store_true", help="skip street-name lookup")
    args = ap.parse_args()

    segs = load_segments()
    jams = load_jams()
    points = list(csv.DictReader((ROOT / "corridors.csv").open(encoding="utf-8")))

    key = None
    if not args.no_geocode:
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("TOMTOM_API_KEY="):
                key = line.split("=", 1)[1].strip()
        if not key:
            sys.exit("no TOMTOM_API_KEY in .env (use --no-geocode to skip)")

    out, moved, skipped = [], 0, 0
    print(f"{'point_id':<20}{'slots':>6}{'move':>8}  new road")
    print("-" * 78)
    for pt in points:
        slots = jams.get(pt["point_id"], 0)
        row = dict(pt)
        if slots >= 10:
            row["notes"] = f"KEPT - records jams ({slots} congested slots)"
            out.append(row)
            print(f"{pt['point_id']:<20}{slots:>6}{'keep':>8}  (unchanged)")
            continue

        best = best_replacement(pt, segs)
        if best is None or best[2] > MAX_MOVE_M:
            d = f"{best[2]:.0f}m" if best else "none"
            row["notes"] = f"NO FIX - nearest usable segment {d} away; consider dropping"
            out.append(row)
            skipped += 1
            print(f"{pt['point_id']:<20}{slots:>6}{'--':>8}  NO FIX (nearest {d})")
            continue

        s, (la, lo), d = best
        name = "?" if args.no_geocode else geocode(key, la, lo)
        if not args.no_geocode:
            time.sleep(0.25)
        row["lat"], row["lon"] = f"{la:.5f}", f"{lo:.5f}"
        row["notes"] = (f"MOVED {d:.0f}m onto {s['frc']} {s['km']:.2f}km segment "
                        f"{s['id'][:6]} ({name})")
        out.append(row)
        moved += 1
        print(f"{pt['point_id']:<20}{slots:>6}{d:>7.0f}m  {s['frc']} {s['km']:.2f}km - {name}")

    dest = SP / "corridors_fixed.csv"
    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(points[0].keys()))
        w.writeheader()
        w.writerows(out)

    print("-" * 78)
    print(f"kept {len(points)-moved-skipped} | moved {moved} | no fix {skipped}")
    print(f"wrote {dest}")
    print("\nVERIFY the road names above before adopting, then:")
    print("  copy corridors_fixed.csv over corridors.csv and run validate_points.py")


if __name__ == "__main__":
    main()
