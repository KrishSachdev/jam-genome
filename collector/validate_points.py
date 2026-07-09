#!/usr/bin/env python3
"""One-shot sanity check of every point in corridors.csv.

Queries Flow Segment Data once per point and reports what the API actually
snapped to: functional road class (frc), free-flow speed, current speed, and
how far the returned segment is from the requested coordinate. The starter
coordinates in corridors.csv are approximate — run this BEFORE trusting any
collected data, nudge bad coordinates onto the intended carriageway, and
re-run until clean. A point snapped to the wrong road (service lane, side
street, opposite carriageway) poisons everything downstream.

Red flags (type-aware — junction points are legitimately slow, so only
FAR_SNAP applies to them):
  FAR_SNAP      snap distance > 150 m       -> probably the wrong road
  LOW_FREEFLOW  ff < 30 (WEH/EEH), < 15 (arterial) -> probably a service lane
  MINOR_ROAD    frc > FRC2 (WEH/EEH), > FRC4 (arterial)

Usage:  TOMTOM_API_KEY=... python collector/validate_points.py
Writes validation_report.csv to the repo root (commit it as a record).
"""

import csv
import math
import os
import sys
import time

import requests

from poll import ROOT, fetch_segment, load_points

REPORT = ROOT / "validation_report.csv"
FIELDS = ["point_id", "name", "frc", "freeflow_kmph", "current_kmph", "snap_m", "flags", "error"]


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def check_point(session, api_key, pt):
    lat, lon = float(pt["lat"]), float(pt["lon"])
    row = {"point_id": pt["point_id"], "name": pt["name"]}
    try:
        seg = fetch_segment(session, api_key, lat, lon)
    except Exception as err:
        row["error"] = str(err)
        row["flags"] = "ERROR"
        return row

    coords = seg.get("coordinates", {}).get("coordinate", [])
    snap_m = min(
        (haversine_m(lat, lon, c["latitude"], c["longitude"]) for c in coords),
        default=float("nan"),
    )
    frc = seg.get("frc", "")
    freeflow = seg.get("freeFlowSpeed")

    flags = []
    if snap_m == snap_m and snap_m > 150:  # snap_m == snap_m filters NaN
        flags.append("FAR_SNAP")
    if pt["direction"] != "junction":
        expressway = pt["corridor"] in ("WEH", "EEH")
        min_ff, max_frc = (30, 2) if expressway else (15, 4)
        if freeflow is not None and freeflow < min_ff:
            flags.append("LOW_FREEFLOW")
        if frc and frc[-1].isdigit() and int(frc[-1]) > max_frc:
            flags.append("MINOR_ROAD")

    row.update(
        frc=frc,
        freeflow_kmph=freeflow,
        current_kmph=seg.get("currentSpeed"),
        snap_m=round(snap_m) if snap_m == snap_m else "",
        flags="|".join(flags),
    )
    return row


def main():
    api_key = os.environ.get("TOMTOM_API_KEY")
    if not api_key:
        sys.exit("TOMTOM_API_KEY is not set")

    session = requests.Session()
    rows = []
    for pt in load_points():
        rows.append(check_point(session, api_key, pt))
        time.sleep(0.25)

    print(f"{'point_id':<16} {'frc':<5} {'freeflow':>8} {'current':>8} {'snap_m':>7}  flags")
    for r in rows:
        print(
            f"{r['point_id']:<16} {r.get('frc', ''):<5} {str(r.get('freeflow_kmph', '')):>8} "
            f"{str(r.get('current_kmph', '')):>8} {str(r.get('snap_m', '')):>7}  "
            f"{r.get('flags', '')} {r.get('error', '')}"
        )

    with open(REPORT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    flagged = [r for r in rows if r.get("flags")]
    print(f"\n{len(flagged)}/{len(rows)} points flagged -> {REPORT.name}")
    if flagged:
        print("Fix the flagged coordinates in corridors.csv and re-run before going live.")


if __name__ == "__main__":
    main()
