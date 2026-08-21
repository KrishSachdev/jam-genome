#!/usr/bin/env python3
"""Rank clean sweep segments as monitoring points, for maximum Phase 3 impact.

The headline deliverable of this project is a *propagation* ranking -- which
jam causes which. That constrains point choice more than "where is traffic
bad" does:

  * a point on a road nobody uses contributes nothing;
  * a point with no neighbour 1-3 km away can never show propagation, because
    there is nothing for a jam to spread to or from;
  * a point on a slow local road has little headroom -- if free-flow is
    15 km/h, congestion cannot express itself as a big speed drop;
  * two points 200 m apart are one point wearing two hats, and cost double.

So each clean candidate is scored on:

  class    FRC1/2 arterials carry the traffic whose jams propagate      x3
  headroom free-flow speed -- room for the ratio to actually fall       x2
  size     0.5-2.5 km is the sweet spot: specific, but a real corridor  x2
  network  clean neighbours 0.8-3 km away, i.e. propagation is visible  x3

then selected greedily with a minimum spacing so the set spreads over the
city instead of clustering in whichever district scores best.

IMPORTANT: the sweep never recorded live speeds, so this is a *structural*
ranking, not evidence of congestion. The only congestion evidence available
is the 29 days already collected at the existing 36 points -- those with a
proven jam record are pinned into the set regardless of score.

Usage:
    python sweep/select_points.py --n 46
    python sweep/select_points.py --n 46 --csv     # write proposed_corridors.csv
"""
import argparse
import csv
import json
import math
from pathlib import Path

import analyse  # zone definitions live there, single source of truth

SP = Path(__file__).resolve().parent
ROOT = SP.parent

FRC_WEIGHT = {"FRC0": 1.0, "FRC1": 1.0, "FRC2": 0.9, "FRC3": 0.65,
              "FRC4": 0.45, "FRC5": 0.25, "FRC6": 0.15, "FRC7": 0.1}
MIN_SPACING_M = 700          # below this, two points measure the same jam
NEIGHBOUR_LO, NEIGHBOUR_HI = 800, 3000   # propagation-visible range, metres


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def centroid(geom):
    return (sum(p[0] for p in geom) / len(geom), sum(p[1] for p in geom) / len(geom))


def load_candidates():
    st = json.loads((SP / "sweep_state.json").read_text())
    out = []
    for sid, s in st["segments"].items():
        if not s["geom"] or not s["ff"]:
            continue
        if not (0.1 <= s["km"] <= 3 and s["ff"] >= 10):
            continue
        la, lo = centroid(s["geom"])
        out.append({"id": sid, "lat": la, "lon": lo, "km": s["km"],
                    "frc": s["frc"] or "FRC7", "ff": s["ff"], "geom": s["geom"],
                    "zone": analyse.zone_of(la, lo)})
    return out


def size_score(km):
    """Peaks across 0.5-2.5 km, falls off outside it."""
    if km < 0.5:
        return km / 0.5
    if km <= 2.5:
        return 1.0
    return max(0.0, 1 - (km - 2.5) / 1.0)


def score_all(cands):
    for c in cands:
        n = 0
        for o in cands:
            if o is c:
                continue
            d = haversine_m(c["lat"], c["lon"], o["lat"], o["lon"])
            if NEIGHBOUR_LO <= d <= NEIGHBOUR_HI:
                n += 1
        c["neighbours"] = n
    max_n = max((c["neighbours"] for c in cands), default=1) or 1
    for c in cands:
        cls = FRC_WEIGHT.get(c["frc"], 0.1)
        headroom = min(c["ff"], 60) / 60
        c["score"] = round(
            3 * cls + 2 * headroom + 2 * size_score(c["km"]) + 3 * (c["neighbours"] / max_n), 3
        )
    return cands


def greedy_spread(cands, n, pinned, quotas=None):
    """Highest score first, rejecting anything too close to an accepted point.

    With quotas, each zone may contribute only its allotted share. Without
    them the selection collapses into whichever district has the densest
    street grid -- South Mumbai wins on the neighbour term and starves the
    northern corridors, which is where this project's jams actually are.
    """
    chosen = list(pinned)
    taken = {z: 0 for z in (quotas or {})}
    for c in sorted(cands, key=lambda c: -c["score"]):
        if len(chosen) >= n:
            break
        if quotas is not None:
            z = c["zone"]
            if taken.get(z, 0) >= quotas.get(z, 0):
                continue
        if any(haversine_m(c["lat"], c["lon"], k["lat"], k["lon"]) < MIN_SPACING_M
               for k in chosen):
            continue
        chosen.append(c)
        if quotas is not None:
            taken[c["zone"]] = taken.get(c["zone"], 0) + 1
    return chosen


def build_quotas(cands, n_new):
    """Share out the new points by each zone's share of the road network."""
    from collections import Counter
    per_zone = Counter(c["zone"] for c in cands)
    total = sum(per_zone.values())
    quotas, acc = {}, 0.0
    for z, cnt in per_zone.items():
        exact = cnt / total * n_new
        quotas[z] = int(exact)
        acc += exact - int(exact)
    # hand out the rounding remainder to the largest zones
    for z, _ in sorted(per_zone.items(), key=lambda kv: -kv[1])[:round(acc)]:
        quotas[z] += 1
    return quotas


def proven_jam_points():
    """Existing points with a real congestion record over the 29 days collected."""
    path = ROOT / "analysis" / "outputs" / "league_table.csv"
    if not path.exists():
        return {}
    keep = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["congested_slots"]) >= 10:
                keep[row["point_id"]] = int(row["congested_slots"])
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=46, help="total points to select")
    ap.add_argument("--csv", action="store_true", help="write proposed_corridors.csv")
    args = ap.parse_args()

    cands = score_all(load_candidates())
    proven = proven_jam_points()

    # pin existing points that have actually recorded jams -- 29 days of
    # evidence beats any structural score, and moving them breaks continuity
    pins = []
    with open(ROOT / "corridors.csv", newline="", encoding="utf-8") as f:
        for pt in csv.DictReader(f):
            if pt["point_id"] in proven:
                pins.append({"id": pt["point_id"], "lat": float(pt["lat"]),
                             "lon": float(pt["lon"]), "km": None, "frc": "kept",
                             "ff": None, "score": None, "neighbours": None,
                             "pinned": True, "geom": None})
    print(f"{len(cands)} clean candidates | pinning {len(pins)} points with a proven jam record:")
    for p in pins:
        print(f"   {p['id']} ({proven[p['id']]} congested slots)")

    quotas = build_quotas(cands, args.n - len(pins))
    print("\nzone quotas for the new points (by share of road network):")
    for z, q in sorted(quotas.items(), key=lambda kv: -kv[1]):
        print(f"   {q:>2}  {z}")

    chosen = greedy_spread(cands, args.n, pins, quotas)
    new = [c for c in chosen if not c.get("pinned")]

    print(f"\nselected {len(chosen)} points = {len(pins)} pinned + {len(new)} new")
    print(f"daily API cost: {len(chosen)} x 48 = {len(chosen)*48:,} requests "
          f"(free tier 2,500)\n")

    print(f"{'rank':>4} {'segment':<10}{'frc':<6}{'km':>6}{'ff':>5}{'nbrs':>6}{'score':>7}  lat,lon")
    for i, c in enumerate(sorted(new, key=lambda c: -c["score"]), 1):
        print(f"{i:>4} {c['id']:<10}{c['frc']:<6}{c['km']:>6.2f}{c['ff']:>5}"
              f"{c['neighbours']:>6}{c['score']:>7.2f}  {c['lat']:.5f},{c['lon']:.5f}")

    from collections import Counter
    print("\nby road class:", dict(Counter(c["frc"] for c in new).most_common()))
    print("\nfinal spread (pinned + new):")
    allsel = Counter(c.get("zone") or analyse.zone_of(c["lat"], c["lon"]) for c in chosen)
    for z, k in sorted(allsel.items(), key=lambda kv: -kv[1]):
        print(f"   {k:>2}  {z}")

    if args.csv:
        out = SP / "proposed_corridors.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["point_id", "name", "lat", "lon", "corridor", "direction", "notes"])
            for p in pins:
                w.writerow([p["id"], f"(kept) {p['id']}", f"{p['lat']:.5f}", f"{p['lon']:.5f}",
                            "", "", "existing point with proven jam record - do not move"])
            for c in sorted(new, key=lambda c: -c["score"]):
                w.writerow([f"seg_{c['id'][:6]}", f"segment {c['id'][:6]}",
                            f"{c['lat']:.5f}", f"{c['lon']:.5f}", "", "",
                            f"sweep candidate {c['frc']} {c['km']:.2f}km ff{c['ff']} "
                            f"score{c['score']:.2f} - NAME AND VERIFY BEFORE USE"])
        print(f"\nwrote {out}")
        print("Next: name the points, sanity-check on a map, run validate_points.py.")


if __name__ == "__main__":
    main()
