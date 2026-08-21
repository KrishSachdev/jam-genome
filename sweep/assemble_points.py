#!/usr/bin/env python3
"""Build the Ganeshotsav-2026 monitoring set as a new corridors.csv.

Combines three groups, then deduplicates by TomTom segment -- two points on
one segment return the identical number, so the second is wasted budget:

  KEEP    existing points with a proven congestion record (never moved, and
          their point_id is preserved so 29 days of data stay joinable)
  EVENT   pandals, procession roads and immersion points for 14-25 Sept 2026
  CONTROL arterials far from any pandal or immersion route, so the festival
          effect can be separated from "September was just busier"

Writes corridors_ganpati.csv. Review, then copy over corridors.csv and run
collector/validate_points.py before collecting.

Usage:  python sweep/assemble_points.py
"""
import csv
import json
import math
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent

# points with a real congestion record over 29 days -- keep verbatim
PROVEN_MIN_SLOTS = 10


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_segments():
    st = json.loads((SP / "sweep_state.json").read_text())
    return [{"id": k, **v} for k, v in st["segments"].items() if v["geom"]]


def segment_at(lat, lon, segs):
    """Which segment does this coordinate actually sit on?"""
    best, bd = None, float("inf")
    for s in segs:
        for a, b in s["geom"]:
            d = haversine_m(lat, lon, a, b)
            if d < bd:
                best, bd = s, d
    return best, bd


def slug(label):
    out = label.lower()
    for a, b in ((" ", "_"), ("(", ""), (")", ""), ("/", "_"), ("-", "_"), (".", "")):
        out = out.replace(a, b)
    return out.replace("control_", "ctl_").strip("_")[:24]


def main():
    segs = load_segments()

    jams = {}
    lt = ROOT / "analysis" / "outputs" / "league_table.csv"
    if lt.exists():
        jams = {r["point_id"]: int(r["congested_slots"])
                for r in csv.DictReader(lt.open(encoding="utf-8"))}

    rows, seen_seg = [], {}

    def add(pid, name, lat, lon, corridor, direction, note):
        s, d = segment_at(float(lat), float(lon), segs)
        sid = s["id"] if s else None
        if sid in seen_seg:
            print(f"  SKIP {pid:<26} duplicate of {seen_seg[sid]} (same segment {sid[:6]})")
            return
        if sid:
            seen_seg[sid] = pid
        km = f"{s['km']:.2f}km {s['frc']}" if s else "?"
        rows.append({"point_id": pid, "name": name, "lat": lat, "lon": lon,
                     "corridor": corridor, "direction": direction,
                     "notes": f"{note} [seg {sid[:6] if sid else '?'} {km}]"})

    # ---- 1. proven performers, verbatim ----------------------------------
    print("KEEP - existing points with a congestion record:")
    for pt in csv.DictReader((ROOT / "corridors.csv").open(encoding="utf-8")):
        n = jams.get(pt["point_id"], 0)
        if n >= PROVEN_MIN_SLOTS:
            print(f"  {pt['point_id']:<26} {n} congested slots")
            add(pt["point_id"], pt["name"], pt["lat"], pt["lon"],
                pt["corridor"], pt["direction"], f"KEEP proven {n} slots")

    # ---- 2. event + control points from the Ganpati match ----------------
    print("\nEVENT / CONTROL points from ganpati_candidates.csv:")
    src = SP / "ganpati_candidates.csv"
    if not src.exists():
        raise SystemExit("run ganpati_points.py --csv first")
    for r in csv.DictReader(src.open(encoding="utf-8")):
        if r["quality"] == "NO SEGMENT" or not r["lat"]:
            print(f"  SKIP {r['label']:<26} no usable segment")
            continue
        cat = r["category"]
        corridor = {"pandal": "GANPATI", "procession road": "GANPATI",
                    "immersion": "VISARJAN", "control": "CONTROL"}[cat]
        add(slug(r["label"]), r["label"], r["lat"], r["lon"], corridor,
            "event", f"{cat} 2026 Ganeshotsav")

    dest = SP / "corridors_ganpati.csv"
    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["point_id", "name", "lat", "lon",
                                          "corridor", "direction", "notes"])
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    by = Counter(r["corridor"] for r in rows)
    print(f"\n{'-'*66}")
    print(f"final set: {len(rows)} points, all on distinct segments")
    for k, v in by.most_common():
        print(f"   {v:>2}  {k}")
    print(f"daily cost: {len(rows)} x 48 = {len(rows)*48:,} requests (free tier 2,500)")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
