"""Colaba -> Dahisar full segment sweep.

Probes Greater Mumbai on a 260 m grid and enumerates every distinct TomTom
road segment. Runs across several days because the daily API budget is shared
with the live collector, which ALWAYS has priority -- the collector's data is
irreplaceable, this sweep is not.

Why this exists: every reading TomTom returns belongs to a whole *road
segment*, not to the coordinate you asked about. Segment length is therefore
the real resolution limit. A point dropped on a 20 km segment reports the
average of an entire highway. This sweep enumerates which segments are short
enough (<= 3 km) to measure a single junction.

Safety model
  * hard ceiling 2,500 req/day (TomTom free tier)
  * subtract what the collector has already written today
  * subtract a reserve for every collector run still to come before 00:00 UTC
  * subtract a 100-request safety margin
  * whatever remains is this run's allowance

State lives in sweep_state.json so the sweep resumes exactly where it stopped.

Usage:  python sweep/sweep.py [--plan] [--max N]
"""
import argparse
import hashlib
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SP = Path(__file__).resolve().parent
STATE = SP / "sweep_state.json"
ROOT = SP.parent                      # the jam genome repo root (holds .env)

DAILY_CEILING = 2500
SAFETY_MARGIN = 100
POINTS_PER_RUN = 36           # collector polls 36 points per run
RUN_EVERY_MIN = 30
GRID_M = 260

# ---------------------------------------------------------------- land mask
# Approximate outline of Greater Mumbai (Colaba -> Dahisar), clockwise.
# Deliberately generous at the edges; the cost of a stray sea probe is one
# request, the cost of clipping a real road is a missing segment.
MUMBAI = [
    (18.892, 72.813), (18.918, 72.796), (18.945, 72.793), (18.975, 72.805),
    (19.005, 72.810), (19.043, 72.818), (19.075, 72.822), (19.108, 72.820),
    (19.135, 72.810), (19.160, 72.795), (19.190, 72.790), (19.225, 72.780),
    (19.252, 72.800), (19.264, 72.862), (19.258, 72.906), (19.232, 72.948),
    (19.196, 72.962), (19.160, 72.957), (19.125, 72.947), (19.090, 72.937),
    (19.060, 72.942), (19.030, 72.930), (19.000, 72.905), (18.985, 72.875),
    (18.960, 72.855), (18.935, 72.845), (18.910, 72.830),
]
# Sanjay Gandhi National Park core -- forest, effectively no road network.
SGNP = (19.160, 19.245, 72.890, 72.940)   # lat0, lat1, lon0, lon1


def in_poly(lat, lon, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        y1, x1 = poly[i]
        y2, x2 = poly[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            xint = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < xint:
                inside = not inside
    return inside


def on_land(lat, lon):
    if SGNP[0] <= lat <= SGNP[1] and SGNP[2] <= lon <= SGNP[3]:
        return False
    return in_poly(lat, lon, MUMBAI)


# ---------------------------------------------------------------- grid
LAT0, LAT1 = 18.890, 19.266
LON0, LON1 = 72.775, 72.975
DLAT = GRID_M / 1000 / 110.57
DLON = GRID_M / 1000 / (111.32 * math.cos(math.radians(19.07)))


def build_grid():
    cells = []
    nlat = int((LAT1 - LAT0) / DLAT) + 1
    nlon = int((LON1 - LON0) / DLON) + 1
    for i in range(nlat):                      # south -> north
        lat = LAT0 + i * DLAT
        for j in range(nlon):
            lon = LON0 + j * DLON
            if on_land(lat, lon):
                cells.append((round(lat, 5), round(lon, 5)))
    return cells


# ---------------------------------------------------------------- budget
def collector_used_today():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"https://raw.githubusercontent.com/KrishSachdev/jam-genome/main/data/raw/{day}.jsonl"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return sum(1 for _ in r), day
    except Exception:
        return 0, day


def budget(state, solo=False):
    """Requests this run may spend.

    Normally a reserve is held back for every collector run still to come
    today -- the collector's data is irreplaceable and always has priority.
    With solo=True (collector paused) that reserve is released, which roughly
    quadruples the sweep's daily allowance.
    """
    used, day = collector_used_today()
    now = datetime.now(timezone.utc)
    mins_left = (24 * 60) - (now.hour * 60 + now.minute)
    runs_left = 0 if solo else math.ceil(mins_left / RUN_EVERY_MIN)
    reserve = runs_left * POINTS_PER_RUN
    mine = state.get("used_by_day", {}).get(day, 0)
    avail = DAILY_CEILING - used - mine - reserve - SAFETY_MARGIN
    return max(0, avail), dict(day=day, collector=used, mine=mine,
                               runs_left=runs_left, reserve=reserve, solo=solo)


# ---------------------------------------------------------------- probe
def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TOMTOM_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("no TOMTOM_API_KEY in .env")


def probe(key, lat, lon):
    url = ("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?"
           + urllib.parse.urlencode({"point": f"{lat:.5f},{lon:.5f}", "unit": "KMPH", "key": key}))
    with urllib.request.urlopen(url, timeout=20) as r:
        s = json.load(r)["flowSegmentData"]
    co = [(round(c["latitude"], 5), round(c["longitude"], 5))
          for c in s.get("coordinates", {}).get("coordinate", [])]
    sig = f"{co[0]}|{co[-1]}|{len(co)}" if co else f"{s['freeFlowTravelTime']}|{s['freeFlowSpeed']}"
    return hashlib.md5(sig.encode()).hexdigest()[:8], s, co


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"done": [], "segments": {}, "used_by_day": {}, "started": None}


def save_state(st):
    STATE.write_text(json.dumps(st, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="show plan, make no calls")
    ap.add_argument("--max", type=int, default=None, help="cap probes this run")
    ap.add_argument("--solo", action="store_true",
                    help="collector is PAUSED -- release its reserve and use the full budget. "
                         "Only pass this once the collector really is stopped, or the sweep "
                         "will eat the requests the collector needs.")
    args = ap.parse_args()

    grid = build_grid()
    st = load_state()
    done = set(tuple(c) for c in st["done"])
    todo = [c for c in grid if c not in done]

    avail, info = budget(st, solo=args.solo)
    if args.max is not None:
        avail = min(avail, args.max)

    print(f"grid cells on land : {len(grid):,}")
    print(f"already probed     : {len(done):,}  ({len(done)/len(grid)*100:.1f}%)")
    print(f"remaining          : {len(todo):,}")
    print(f"segments so far    : {len(st['segments']):,}")
    print(f"\nbudget for {info['day']}")
    print(f"  collector used   : {info['collector']:,}")
    print(f"  sweep used today : {info['mine']:,}")
    if info["solo"]:
        print("  collector reserve: 0  (SOLO MODE - collector assumed paused)")
    else:
        print(f"  collector reserve: {info['reserve']:,}  ({info['runs_left']} runs left today)")
    print(f"  safety margin    : {SAFETY_MARGIN}")
    print(f"  -> allowance     : {avail:,}")
    if todo and avail:
        print(f"\nat this rate: ~{math.ceil(len(todo)/max(avail,1))} more day(s)")
    if args.plan:
        return

    if avail <= 0:
        print("\nno allowance left today - collector has priority. Re-run tomorrow.")
        return
    if not todo:
        print("\nsweep COMPLETE.")
        return

    key = load_key()
    st["started"] = st["started"] or datetime.now(timezone.utc).isoformat()
    n = ok = err = 0
    new_segs = 0
    t0 = time.time()
    for (lat, lon) in todo[:avail]:
        try:
            seg, s, co = probe(key, lat, lon)
        except Exception as e:
            # A failed probe must NOT be marked done, or the cell is skipped
            # forever and leaves a permanent invisible hole in the grid.
            err += 1
            if err <= 3:
                print(f"  probe error at {lat},{lon}: {e}")
            if err > 25:
                print("  too many errors - stopping early")
                break
            continue
        ok += 1
        if seg not in st["segments"]:
            st["segments"][seg] = {
                "frc": s.get("frc"), "ff": s.get("freeFlowSpeed"),
                "ff_tt": s.get("freeFlowTravelTime"),
                "km": round(s["freeFlowSpeed"] * s["freeFlowTravelTime"] / 3600, 3),
                "geom": co, "hits": 0,
            }
            new_segs += 1
        st["segments"][seg]["hits"] += 1
        st["done"].append([lat, lon])
        n += 1
        st["used_by_day"][info["day"]] = st["used_by_day"].get(info["day"], 0) + 1
        if n % 100 == 0:
            save_state(st)
            print(f"  {n}/{min(len(todo),avail)} probed | {len(st['segments'])} segments "
                  f"| {time.time()-t0:.0f}s")
        time.sleep(0.25)

    save_state(st)
    total = len(st["segments"])
    short = sum(1 for v in st["segments"].values() if v["km"] <= 3)
    print(f"\nbatch done: {n} probes ({ok} ok, {err} errors) in {time.time()-t0:.0f}s")
    print(f"new segments this batch : {new_segs}")
    print(f"total distinct segments : {total:,}  ({short:,} usable <=3 km)")
    print(f"grid progress           : {len(st['done']):,}/{len(grid):,} "
          f"({len(st['done'])/len(grid)*100:.1f}%)")


if __name__ == "__main__":
    main()
