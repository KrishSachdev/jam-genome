#!/usr/bin/env python3
"""Poll TomTom Flow Segment Data for every point in corridors.csv.

Appends one JSON line per point to data/raw/YYYY-MM-DD.jsonl (UTC date).

Dependency-light on purpose (requests + stdlib): this runs on a GitHub
Actions cron every 30 minutes. It must never crash the run — per-point
failures are logged as JSONL lines with an "error" field and the script
still exits 0. Only a missing API key is fatal.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CORRIDORS = ROOT / "corridors.csv"
RAW_DIR = ROOT / "data" / "raw"

API_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
MAX_TRIES = 3
INTER_POINT_SLEEP = 0.25  # TomTom free tier allows ~5 QPS; stay far below it

# Hard daily budget guard (TomTom free tier: 2,500 req/day). The cron
# attempts every 15 min because GitHub skips most slots; if it ever fires
# them all, this cap (66 runs x 36 points = 2,376) keeps us under quota.
MAX_LINES_PER_DAY = 2376


def load_points():
    with open(CORRIDORS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_segment(session, api_key, lat, lon):
    """Return the flowSegmentData dict for the road segment nearest (lat, lon).

    Retries with backoff; raises the last error if all tries fail.
    """
    params = {"point": f"{lat},{lon}", "unit": "KMPH", "key": api_key}
    last_err = None
    for attempt in range(MAX_TRIES):
        try:
            resp = session.get(API_URL, params=params, timeout=15)
            if resp.status_code == 429:  # daily budget or QPS exceeded
                last_err = RuntimeError("HTTP 429 (rate limited)")
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()["flowSegmentData"]
        except Exception as err:
            last_err = err
            time.sleep(2**attempt)
    raise last_err


def main():
    api_key = os.environ.get("TOMTOM_API_KEY")
    if not api_key:
        sys.exit("TOMTOM_API_KEY is not set")

    points = load_points()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl")

    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            lines_today = sum(1 for _ in f)
        if lines_today + len(points) > MAX_LINES_PER_DAY:
            print(f"budget guard: {lines_today} lines already today, skipping run")
            return

    ok = failed = 0
    session = requests.Session()
    with open(out_path, "a", encoding="utf-8") as out:
        for pt in points:
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            record = {"ts_utc": ts, "point_id": pt["point_id"]}
            try:
                seg = fetch_segment(session, api_key, pt["lat"], pt["lon"])
                record.update(
                    current_speed=seg.get("currentSpeed"),
                    freeflow_speed=seg.get("freeFlowSpeed"),
                    current_tt=seg.get("currentTravelTime"),
                    freeflow_tt=seg.get("freeFlowTravelTime"),
                    confidence=seg.get("confidence"),
                    closure=seg.get("roadClosure"),
                    frc=seg.get("frc"),
                )
                ok += 1
            except Exception as err:
                record["error"] = str(err)
                failed += 1
            out.write(json.dumps(record) + "\n")
            time.sleep(INTER_POINT_SLEEP)

    print(f"{ok} ok, {failed} failed -> {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
