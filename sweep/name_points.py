#!/usr/bin/env python3
"""Put real street names on the proposed monitoring points.

Reads proposed_corridors.csv, reverse-geocodes each coordinate with TomTom's
Reverse Geocoding API (same key, same free tier), and rewrites the file with
a human-readable name so the proposal can actually be reviewed.

Usage:  python sweep/name_points.py
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent
SRC = SP / "proposed_corridors.csv"

URL = "https://api.tomtom.com/search/2/reverseGeocode/{lat},{lon}.json?{q}"


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TOMTOM_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("no TOMTOM_API_KEY in .env")


def describe(key, lat, lon):
    q = urllib.parse.urlencode({"key": key, "radius": 120})
    url = URL.format(lat=lat, lon=lon, q=q)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.load(r)
    except Exception as e:
        return f"(lookup failed: {e})"
    addrs = data.get("addresses") or []
    if not addrs:
        return "(no address found)"
    a = addrs[0].get("address", {})
    street = a.get("streetName") or ""
    area = (a.get("municipalitySubdivision") or a.get("municipality") or "").split(",")[0]
    if street and area:
        return f"{street}, {area}"
    return street or area or "(unnamed road)"


def main():
    if not SRC.exists():
        sys.exit(f"{SRC} not found -- run select_points.py --csv first")
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    key = load_key()

    print(f"naming {len(rows)} points ({len(rows)} API requests)...\n")
    for r in rows:
        if r["notes"].startswith("existing point"):
            continue          # already named and pinned
        r["name"] = describe(key, r["lat"], r["lon"])
        print(f"  {r['point_id']:<14} {r['lat']},{r['lon']}  ->  {r['name']}")
        time.sleep(0.25)

    with SRC.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nrewrote {SRC}")


if __name__ == "__main__":
    main()
