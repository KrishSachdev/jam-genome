#!/usr/bin/env python3
"""Probe every proposed point and report the segment TomTom ACTUALLY returns.

Matching a coordinate to a segment offline is not enough: at a junction
several segments share a vertex, and TomTom decides which one a probe snaps
to. The only ground truth is to call the API at the exact coordinate the
collector will use.

Flags:
  LONG SEGMENT   > 3 km -- cannot localise a jam to this junction
  DUPLICATE      another point in the set snaps to the same segment

Usage:  python sweep/verify_set.py [file.csv]
"""
import csv
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else SP / "corridors_ganpati.csv"


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TOMTOM_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("no TOMTOM_API_KEY in .env")


def probe(key, lat, lon):
    url = ("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?"
           + urllib.parse.urlencode({"point": f"{lat},{lon}", "unit": "KMPH", "key": key}))
    with urllib.request.urlopen(url, timeout=20) as r:
        s = json.load(r)["flowSegmentData"]
    co = [(round(c["latitude"], 5), round(c["longitude"], 5))
          for c in s.get("coordinates", {}).get("coordinate", [])]
    sig = f"{co[0]}|{co[-1]}|{len(co)}" if co else f"{s['freeFlowTravelTime']}|{s['freeFlowSpeed']}"
    seg = hashlib.md5(sig.encode()).hexdigest()[:8]
    km = s["freeFlowSpeed"] * s["freeFlowTravelTime"] / 3600
    return seg, km, s.get("frc"), s.get("freeFlowSpeed")


def main():
    key = load_key()
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    seen, results = {}, []

    print(f"probing {len(rows)} points ({len(rows)} requests)\n")
    print(f"{'point_id':<26}{'seg':<10}{'km':>7}{'frc':>6}{'ff':>5}  flags")
    print("-" * 74)
    for r in rows:
        try:
            seg, km, frc, ff = probe(key, r["lat"], r["lon"])
        except Exception as e:
            print(f"{r['point_id']:<26}ERROR {e}")
            continue
        flags = []
        if km > 3:
            flags.append("LONG SEGMENT")
        if seg in seen:
            flags.append(f"DUPLICATE of {seen[seg]}")
        else:
            seen[seg] = r["point_id"]
        results.append((r, seg, km, frc, ff, flags))
        print(f"{r['point_id']:<26}{seg:<10}{km:>7.2f}{frc or '?':>6}{ff:>5}  {' | '.join(flags)}")
        time.sleep(0.25)

    bad = [x for x in results if x[5]]
    print("-" * 74)
    print(f"{len(results)-len(bad)}/{len(results)} points OK; {len(bad)} need attention")
    if bad:
        print("\nProblems:")
        for r, seg, km, frc, ff, flags in bad:
            print(f"  {r['point_id']:<26}{km:>7.2f} km  {' | '.join(flags)}")


if __name__ == "__main__":
    main()
