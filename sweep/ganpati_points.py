#!/usr/bin/env python3
"""Match Ganeshotsav hotspots to usable segments from the sweep.

For the 2026 festival (14-25 Sept) the interesting places are the big pandals,
the immersion beaches, the roads Mumbai Traffic Police close for processions --
plus control roads far from any of it, so the effect can be shown to be the
festival rather than "September was busier".

Each location is geocoded with TomTom (so coordinates are theirs, not my
guesses), then matched to the nearest swept segment. A location is only
monitorable if a short segment (<= 3 km) sits close to it.

Usage:  python sweep/ganpati_points.py [--csv]
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

# (label, geocode query, category)
PLACES = [
    # --- Lalbaug / Parel core: the epicentre -------------------------------
    ("Lalbaugcha Raja", "Lalbaugcha Raja, Lalbaug, Mumbai", "pandal"),
    ("Mumbaicha Raja (Ganesh Galli)", "Ganesh Galli, Lalbaug, Mumbai", "pandal"),
    ("Chintamani Chinchpokli", "Chinchpokli, Mumbai", "pandal"),
    ("Hindmata Junction", "Hindmata, Dadar East, Mumbai", "procession road"),
    ("Bharatmata Junction", "Bharatmata Cinema, Lalbaug, Mumbai", "procession road"),
    ("Parel TT", "Parel TT Circle, Mumbai", "procession road"),
    ("Kalachowki", "Kalachowki, Mumbai", "procession road"),
    ("NM Joshi Marg", "N M Joshi Marg, Mumbai", "procession road"),
    ("GD Ambekar Marg", "G D Ambekar Marg, Parel, Mumbai", "procession road"),
    ("SK Bole Road Dadar", "S K Bole Road, Dadar West, Mumbai", "procession road"),
    # --- other big pandals -------------------------------------------------
    ("GSB Seva Mandal", "King's Circle, Matunga, Mumbai", "pandal"),
    ("Andhericha Raja", "Azad Nagar, Andheri West, Mumbai", "pandal"),
    ("Khetwadi Ganraj", "Khetwadi, Girgaon, Mumbai", "pandal"),
    # --- immersion points --------------------------------------------------
    ("Girgaon Chowpatty", "Girgaon Chowpatty, Mumbai", "immersion"),
    ("Marine Drive (approach)", "Marine Drive, Mumbai", "immersion"),
    ("Dadar Chowpatty", "Dadar Chowpatty, Shivaji Park, Mumbai", "immersion"),
    ("Juhu Beach", "Juhu Beach, Mumbai", "immersion"),
    ("Versova Beach", "Versova Beach, Mumbai", "immersion"),
    ("Powai Lake", "Powai Lake, Mumbai", "immersion"),
    ("Bandra Bandstand", "Bandstand, Bandra West, Mumbai", "immersion"),
    ("Talao Pali Thane", "Talao Pali, Thane", "immersion"),
    # --- controls: far from any pandal or immersion route ------------------
    # Kept inside the swept area -- Thane and Navi Mumbai sit at/outside the
    # sweep mask, so no segment data exists for them.
    ("CONTROL Mulund EEH", "Mulund Check Naka, Mumbai", "control"),
    ("CONTROL Borivali WEH", "Borivali East, Mumbai", "control"),
    ("CONTROL Kandivali", "Kandivali East, Mumbai", "control"),
    ("CONTROL Malad", "Malad East, Mumbai", "control"),
    ("CONTROL Ghatkopar", "Ghatkopar East, Mumbai", "control"),
    ("CONTROL Vikhroli", "Vikhroli West, Mumbai", "control"),
]


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TOMTOM_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("no TOMTOM_API_KEY in .env")


def geocode(key, query):
    # countrySet alone is not enough -- "Juhu Beach" resolved to Chennai.
    # Bound the search to the Mumbai/Thane box.
    url = ("https://api.tomtom.com/search/2/geocode/"
           + urllib.parse.quote(query) + ".json?"
           + urllib.parse.urlencode({"key": key, "limit": 1, "countrySet": "IN",
                                     "topLeft": "19.32,72.74", "btmRight": "18.87,73.02"}))
    with urllib.request.urlopen(url, timeout=20) as r:
        res = json.load(r).get("results") or []
    if not res:
        return None, "(not found)"
    p = res[0]["position"]
    addr = res[0].get("address", {}).get("freeformAddress", "")
    return (p["lat"], p["lon"]), addr


def load_segments():
    st = json.loads((SP / "sweep_state.json").read_text())
    return [{"id": k, **v} for k, v in st["segments"].items() if v["geom"] and v["ff"]]


def rate(km):
    if km <= 1.5:
        return "EXCELLENT"
    if km <= 3:
        return "good"
    if km <= 10:
        return "coarse"
    return "UNUSABLE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    key = load_key()
    segs = load_segments()
    rows = []

    print(f"{'location':<30}{'dist':>6}{'seg km':>8}{'frc':>6}{'ff':>4}  quality")
    print("-" * 78)
    for label, query, cat in PLACES:
        pos, addr = geocode(key, query)
        time.sleep(0.25)
        if pos is None:
            print(f"{label:<30}  geocode failed")
            continue
        la, lo = pos

        best = None
        for s in segs:
            if not (0.1 <= s["km"] <= 3 and s["ff"] >= 10):
                continue
            for a, b in s["geom"]:
                d = haversine_m(la, lo, a, b)
                if best is None or d < best[2]:
                    best = (s, (a, b), d)

        if best is None or best[2] > 800:
            print(f"{label:<30}{'--':>6}   no usable segment within 800 m")
            rows.append([label, cat, f"{la:.5f}", f"{lo:.5f}", "", "", "", "", "NO SEGMENT", addr])
            continue

        s, (vla, vlo), d = best
        q = rate(s["km"])
        print(f"{label:<30}{d:>5.0f}m{s['km']:>8.2f}{s['frc']:>6}{s['ff']:>4}  {q}")
        rows.append([label, cat, f"{vla:.5f}", f"{vlo:.5f}", s["id"][:8], s["km"],
                     s["frc"], s["ff"], q, addr])

    if args.csv:
        out = SP / "ganpati_candidates.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["label", "category", "lat", "lon", "segment_id", "seg_km",
                        "frc", "freeflow", "quality", "geocoded_address"])
            w.writerows(rows)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
