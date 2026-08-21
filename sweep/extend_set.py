#!/usr/bin/env python3
"""Extend the monitoring set to the full daily budget, verifying every point.

Adds named locations that matter for the Ganeshotsav experiment and for
propagation mining: famous chokepoints that the sweep can now fix, more
procession roads named in Mumbai Traffic Police advisories, more immersion
approaches, and more controls.

For each: geocode -> pick the nearest clean segment -> aim at that segment's
MIDPOINT (endpoints sit at junctions where snapping is ambiguous) -> probe the
live API to confirm what actually comes back -> reject if it is a long segment
or duplicates a point already in the set.

Nothing is written unverified.

Usage:  python sweep/extend_set.py [--target 50]
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
SRC = SP / "corridors_ganpati.csv"
DEST = SP / "corridors_final.csv"

sys.path.insert(0, str(SP))
from verify_set import load_key, probe          # noqa: E402

# (point_id, geocode query, corridor tag, why)
WANTED = [
    # --- famous chokepoints the sweep can now place properly --------------
    ("kalanagar",        "Kalanagar Junction, Bandra East, Mumbai",   "CHOKE",  "top chokepoint, blind until now"),
    ("sakinaka",         "Sakinaka Junction, Andheri East, Mumbai",   "CHOKE",  "famous chokepoint"),
    ("amar_mahal",       "Amar Mahal Junction, Chembur, Mumbai",      "CHOKE",  "famous chokepoint"),
    ("mahim_junction",   "Mahim Junction, Mumbai",                    "CHOKE",  "WEH south end"),
    ("andheri_subway",   "Andheri Subway, Mumbai",                    "CHOKE",  "famous chokepoint"),
    # --- more Ganeshotsav procession geography ---------------------------
    ("byculla_ba_road",  "Byculla, Dr Ambedkar Road, Mumbai",         "GANPATI", "Dr B.A. Rd procession route"),
    ("acharya_donde",    "Acharya Donde Marg, Parel, Mumbai",         "GANPATI", "named in police diversions"),
    ("tardeo",           "Tardeo Junction, Mumbai",                   "GANPATI", "heavy diversion area"),
    ("chembur_naka",     "Chembur Naka, Mumbai",                      "GANPATI", "big eastern celebrations"),
    ("worli_naka",       "Worli Naka, Mumbai",                        "GANPATI", "procession corridor"),
    ("wadala",           "Wadala, Mumbai",                            "GANPATI", "central processions"),
    # --- immersion approaches --------------------------------------------
    ("charni_road",      "Charni Road, Girgaon, Mumbai",              "VISARJAN", "Chowpatty approach"),
    ("opera_house",      "Opera House, Girgaon, Mumbai",              "VISARJAN", "Chowpatty approach"),
    ("sewri",            "Sewri, Mumbai",                             "VISARJAN", "eastern immersion route"),
    # --- more controls, spread north and east -----------------------------
    ("ctl_goregaon",     "Goregaon East, Mumbai",                     "CONTROL", "control"),
    ("ctl_jogeshwari",   "Jogeshwari West, Mumbai",                   "CONTROL", "control"),
    ("ctl_bhandup",      "Bhandup West, Mumbai",                      "CONTROL", "control"),
    ("ctl_kanjurmarg",   "Kanjurmarg, Mumbai",                        "CONTROL", "control"),
    ("ctl_santacruz",    "Santacruz East, Mumbai",                    "CONTROL", "control"),
    ("ctl_dahisar",      "Dahisar East, Mumbai",                      "CONTROL", "control"),
]

MAX_MOVE_M = 900


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode(key, query):
    url = ("https://api.tomtom.com/search/2/geocode/" + urllib.parse.quote(query)
           + ".json?" + urllib.parse.urlencode(
               {"key": key, "limit": 1, "countrySet": "IN",
                "topLeft": "19.32,72.74", "btmRight": "18.87,73.02"}))
    with urllib.request.urlopen(url, timeout=20) as r:
        res = json.load(r).get("results") or []
    if not res:
        return None
    p = res[0]["position"]
    return p["lat"], p["lon"]


def clean_segments():
    st = json.loads((SP / "sweep_state.json").read_text())
    out = []
    for sid, s in st["segments"].items():
        if not s["geom"] or not s["ff"]:
            continue
        if 0.1 <= s["km"] <= 3 and s["ff"] >= 10:
            out.append((sid, s))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50)
    args = ap.parse_args()

    key = load_key()
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    segs = clean_segments()

    # segment fingerprint of everything already in the set
    print(f"fingerprinting the existing {len(rows)} points...")
    taken = {}
    for r in rows:
        try:
            seg, *_ = probe(key, r["lat"], r["lon"])
            taken[seg] = r["point_id"]
        except Exception as e:
            print(f"  warn: {r['point_id']} probe failed ({e})")
        time.sleep(0.22)

    added = 0
    print(f"\nadding up to {args.target - len(rows)} points\n")
    print(f"{'point_id':<20}{'km':>7}{'frc':>6}{'ff':>5}{'moved':>8}  result")
    print("-" * 74)

    for pid, query, tag, why in WANTED:
        if len(rows) >= args.target:
            break
        pos = geocode(key, query)
        time.sleep(0.22)
        if pos is None:
            print(f"{pid:<20}{'':>26}  geocode failed")
            continue
        la, lo = pos

        near = []
        for sid, s in segs:
            d = min(haversine_m(la, lo, a, b) for a, b in s["geom"])
            if d <= MAX_MOVE_M:
                near.append((d, sid, s))
        near.sort(key=lambda t: t[0])

        placed = False
        for d, sid, s in near[:5]:
            mla, mlo = s["geom"][len(s["geom"]) // 2]
            try:
                seg, km, frc, ff = probe(key, f"{mla:.5f}", f"{mlo:.5f}")
            except Exception:
                continue
            time.sleep(0.22)
            if km > 3:
                continue
            if seg in taken:
                continue
            moved = haversine_m(la, lo, mla, mlo)
            taken[seg] = pid
            rows.append({"point_id": pid, "name": query.split(",")[0],
                         "lat": f"{mla:.5f}", "lon": f"{mlo:.5f}",
                         "corridor": tag, "direction": "event",
                         "notes": f"{why} [verified {seg[:6]} {km:.2f}km {frc} ff{ff}, "
                                  f"{moved:.0f}m from geocode]"})
            print(f"{pid:<20}{km:>7.2f}{frc:>6}{ff:>5}{moved:>7.0f}m  added")
            added += 1
            placed = True
            break
        if not placed:
            print(f"{pid:<20}{'':>26}  no distinct short segment nearby - skipped")

    with DEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["point_id", "name", "lat", "lon",
                                          "corridor", "direction", "notes"])
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    print("-" * 74)
    print(f"added {added}; final set {len(rows)} points = {len(rows)*48:,} req/day")
    for k, v in Counter(r["corridor"] for r in rows).most_common():
        print(f"   {v:>2}  {k}")
    print(f"wrote {DEST}")


if __name__ == "__main__":
    main()
