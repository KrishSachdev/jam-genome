"""Rebuild sweep_state.json from a saved copy of the sweep map artifact.

The original sweep_state.json was lost with a purged Claude scratchpad
(2026-08-07). The published map artifact, however, embeds the whole payload
as `const D = {...}` -- every probe coordinate and every segment. This script
inverts the map's projection and reconstructs a working state file, so the
sweep resumes instead of restarting from cell 0.

What is recovered exactly : the `done` list (the expensive part -- one API
                            request per cell)
What is recovered lossily : segment geometry, if the map was built with the
                            25 m simplification; segment ids are the map's
                            6-char prefix rather than the original 8-char
                            md5. Neither affects resumption or segment
                            selection -- length, class and free-flow are exact.

Usage:
    1. Open the artifact URL in the browser logged into the account that owns
       it, then Ctrl+S (or View Source) and save the page as, say,
       sweep/sweep_map_saved.html
    2. python sweep/recover_from_map.py sweep/sweep_map_saved.html
"""
import json
import math
import re
import sys
from pathlib import Path

import sweep as SW

SP = Path(__file__).resolve().parent
STATE = SP / "sweep_state.json"

# must match build_sweep_map.py exactly
LAT0, LON0 = 19.080, 72.870
KM_LAT = 110.57
KM_LON = 111.32 * math.cos(math.radians(19.08))


def unproj(x, y):
    return (LAT0 - y / KM_LAT, LON0 + x / KM_LON)


def extract_payload(html):
    m = re.search(r"const\s+D\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        sys.exit("could not find `const D = {...}` in that file -- is it the sweep map page?")
    return json.loads(m.group(1))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    if not src.exists():
        sys.exit(f"no such file: {src}")

    D = extract_payload(src.read_text(encoding="utf-8", errors="replace"))
    print(f"payload: {len(D.get('probes', []))} probes, {len(D.get('segs', []))} segments")

    # Snap each recovered coordinate to the nearest real grid cell. The map
    # stores km rounded to 3 dp (~1 m), so a direct inverse can land a hair
    # off the 5-dp grid values; snapping guarantees exact set-membership.
    grid = SW.build_grid()
    by_lat = {}
    for la, lo in grid:
        by_lat.setdefault(round(la, 5), []).append(lo)
    lats = sorted(by_lat)

    def snap(lat, lon):
        la = min(lats, key=lambda v: abs(v - lat))
        lo = min(by_lat[la], key=lambda v: abs(v - lon))
        if abs(la - lat) > 0.0015 or abs(lo - lon) > 0.0015:
            return None
        return [la, lo]

    done, misses = [], 0
    seen = set()
    for x, y in D.get("probes", []):
        cell = snap(*unproj(x, y))
        if cell is None:
            misses += 1
            continue
        key = (cell[0], cell[1])
        if key in seen:
            continue
        seen.add(key)
        done.append(cell)

    segments = {}
    for s in D.get("segs", []):
        ff = s.get("ff") or 0
        km = s.get("km") or 0
        segments[s["id"]] = {
            "frc": s.get("frc"),
            "ff": ff,
            "ff_tt": round(km * 3600 / ff) if ff else None,
            "km": km,
            "geom": [list(map(lambda v: round(v, 5), unproj(px, py))) for px, py in s.get("pts", [])],
            "hits": s.get("hits", 1),
        }

    state = {"done": done, "segments": segments, "used_by_day": {}, "started": None}

    if STATE.exists():
        backup = STATE.with_suffix(".json.bak")
        backup.write_text(STATE.read_text())
        print(f"existing state backed up -> {backup.name}")

    STATE.write_text(json.dumps(state, separators=(",", ":")))
    short = sum(1 for v in segments.values() if v["km"] <= 3)
    print(f"\nrecovered {len(done):,} probed cells ({misses} could not be snapped)")
    print(f"recovered {len(segments):,} segments ({short:,} usable <=3 km)")
    print(f"grid progress: {len(done):,}/{len(grid):,} ({len(done)/len(grid)*100:.1f}%)")
    print(f"\nwrote {STATE}")
    print("verify with:  python sweep/sweep.py --plan")


if __name__ == "__main__":
    main()
