#!/usr/bin/env python3
"""Correlate daily congestion with actual rainfall.

The collector's own rain log is unusable (FINDINGS.md §4 — it sampled a
15-minute window every 30 minutes and missed roughly half of all rain), so
rainfall is backfilled from the Open-Meteo ERA5 archive, which is free and
permanently available.

ERA5 is a ~9 km grid and smooths local extremes, so treat the numbers as
relative wet/dry rather than absolute millimetres.

Usage:  python analysis/rain_check.py
"""
import json
import urllib.parse
import urllib.request

import pandas as pd

from episodes import ROOT, load_raw

SPLIT = pd.Timestamp("2026-08-20").date()
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive?"


def fetch_rain(start, end):
    url = ARCHIVE + urllib.parse.urlencode({
        "latitude": 19.076, "longitude": 72.8777,
        "start_date": str(start), "end_date": str(end),
        "hourly": "rain", "timezone": "Asia/Kolkata",
    })
    with urllib.request.urlopen(url, timeout=40) as r:
        d = json.load(r)["hourly"]
    s = pd.DataFrame({"t": pd.to_datetime(d["time"]), "rain": d["rain"]})
    s["d"] = s["t"].dt.date
    return s.groupby("d")["rain"].agg(rain_mm="sum", peak_mm_h="max")


def main():
    df = load_raw()
    df["d"] = df["slot_ist"].dt.date
    daily = df.groupby("d").agg(
        cong=("speed_ratio", lambda s: (s < 0.5).mean() * 100),
        mean_ratio=("speed_ratio", "mean"),
        slots=("speed_ratio", "size"),
    )
    daily = daily[daily["slots"] > daily["slots"].max() * 0.6]   # full days only
    daily["era"] = ["A" if d <= SPLIT else "B" for d in daily.index]

    rain = fetch_rain(min(daily.index), max(daily.index))
    j = daily.join(rain).dropna(subset=["rain_mm"])
    j["weekday"] = [pd.Timestamp(d).dayofweek < 5 for d in j.index]

    print(f"{len(j)} full days matched with ERA5 rainfall\n")
    print("WETTEST DAYS")
    print(j.sort_values("rain_mm", ascending=False)
           .head(8)[["rain_mm", "peak_mm_h", "cong", "era"]].round(2).to_string())

    print("\nCORRELATION between daily rain and % of slots congested")
    for era in ("A", "B"):
        e = j[j["era"] == era]
        if len(e) < 5:
            continue
        r_all = e["rain_mm"].corr(e["cong"])
        wd = e[e["weekday"]]
        r_wd = wd["rain_mm"].corr(wd["cong"]) if len(wd) >= 5 else float("nan")
        print(f"  era {era}: all days r = {r_all:+.2f} (n={len(e)}) | "
              f"weekdays only r = {r_wd:+.2f} (n={len(wd)})")

    print("\nWET vs DRY weekdays (rain > 10 mm counts as wet)")
    for era in ("A", "B"):
        e = j[(j["era"] == era) & j["weekday"]]
        wet, dry = e[e["rain_mm"] > 10], e[e["rain_mm"] <= 10]
        if len(wet) and len(dry):
            print(f"  era {era}: wet {wet['cong'].mean():.2f}% (n={len(wet)})  vs  "
                  f"dry {dry['cong'].mean():.2f}% (n={len(dry)})")
        else:
            print(f"  era {era}: not enough of both (wet {len(wet)}, dry {len(dry)})")

    out = ROOT / "analysis" / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    j.round(3).to_csv(out / "daily_rain_congestion.csv")
    print(f"\nwrote {out / 'daily_rain_congestion.csv'}")


if __name__ == "__main__":
    main()
