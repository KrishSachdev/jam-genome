#!/usr/bin/env python3
"""Data-quality report over data/raw/*.jsonl.

Per point: polls received vs expected 30-min slots, error count, confidence,
closures, and the two silent data killers —
  flat_freeflow : freeflow never changes AND the point never congests
                  -> point probably snapped to a road TomTom barely models
  high missing% : polls not landing -> API errors or a dead point

Run weekly during weeks 1-2, then whenever a point looks dead. Fix bad
points early: every lost week of monsoon data is irreplaceable.

Usage:  python analysis/data_quality.py [--days 7]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def load(days):
    files = sorted(RAW_DIR.glob("*.jsonl"))[-days:]
    if not files:
        sys.exit(f"no data in {RAW_DIR}")
    print(f"reading {len(files)} file(s): {files[0].name} .. {files[-1].name}")
    return pd.concat((pd.read_json(f, lines=True) for f in files), ignore_index=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="most recent N daily files")
    args = parser.parse_args()

    df = load(args.days)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"])
    if "error" not in df.columns:
        df["error"] = pd.NA
    slots = df["ts_utc"].dt.floor("30min").nunique()

    good = df[df["error"].isna()].copy()
    good["speed_ratio"] = good["current_speed"] / good["freeflow_speed"]

    report = good.groupby("point_id").agg(
        polls=("ts_utc", "count"),
        mean_conf=("confidence", "mean"),
        closures=("closure", "sum"),
        freeflow_nunique=("freeflow_speed", "nunique"),
        min_ratio=("speed_ratio", "min"),
        p05_ratio=("speed_ratio", lambda s: s.quantile(0.05)),
    )

    all_ids = pd.Index(df["point_id"].unique(), name="point_id")
    report = report.reindex(all_ids)
    report["errors"] = (
        df[df["error"].notna()].groupby("point_id").size().reindex(all_ids).fillna(0).astype(int)
    )
    report["missing_pct"] = (1 - report["polls"].fillna(0) / slots) * 100
    report["flat_freeflow"] = (report["freeflow_nunique"] <= 1) & (report["min_ratio"] > 0.95)
    report = report.sort_values("missing_pct", ascending=False)

    pd.set_option("display.width", 160)
    print(f"\n{slots} expected 30-min slots\n")
    print(report.round(2).to_string())

    flagged = report[(report["missing_pct"] > 10) | report["flat_freeflow"].fillna(True)]
    if len(flagged):
        print(f"\nATTENTION — {len(flagged)} point(s) need a look:")
        print("  " + ", ".join(flagged.index))
    else:
        print("\nAll points healthy.")


if __name__ == "__main__":
    main()
