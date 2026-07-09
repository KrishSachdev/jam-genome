#!/usr/bin/env python3
"""Append one Mumbai weather observation to data/weather/YYYY-MM-DD.jsonl.

Uses Open-Meteo (free, no API key). Rain is NOT the project focus — this
exists only so Phase 3 can control for rain as a confounder (see PLAN.md).
Runs alongside poll.py on the same cron; never fails the run.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "weather"

URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=19.076&longitude=72.8777"
    "&current=temperature_2m,precipitation,rain"
)


def main():
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        cur = requests.get(URL, timeout=15).json()["current"]
        record = {
            "ts_utc": ts,
            "temp_c": cur.get("temperature_2m"),
            "precip_mm": cur.get("precipitation"),
            "rain_mm": cur.get("rain"),
        }
    except Exception as err:
        record = {"ts_utc": ts, "error": str(err)}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl")
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print("weather:", record)


if __name__ == "__main__":
    main()
