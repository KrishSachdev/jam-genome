#!/usr/bin/env python3
"""Congestion-episode extraction — shared foundation for Phase 2 EDA and
Phase 3 propagation mining.

An episode is a maximal run of consecutive 30-min slots where a point's
speed_ratio (current/freeflow) stays below a threshold, lasting at least
min_slots. PLAN.md forbids hard-coding one threshold — run_sensitivity()
sweeps it so the final choice is a documented decision, not an accident.

load_raw() returns one row per (point_id, 30-min slot): duplicate polls in
the same slot are averaged, error rows dropped, excluded points removed.
Timestamps carry both UTC and IST; jams happen in IST.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
IST = "Asia/Kolkata"

# points whose raw rows must be ignored (see README data caveats)
EXCLUDED_POINTS = {"tulsi_pipe"}


def load_raw(days=None):
    """Raw JSONL -> one row per (point_id, 30-min slot)."""
    files = sorted(RAW_DIR.glob("*.jsonl"))
    if days:
        files = files[-days:]
    df = pd.concat((pd.read_json(f, lines=True) for f in files), ignore_index=True)
    if "error" in df.columns:
        df = df[df["error"].isna()]
    df = df[~df["point_id"].isin(EXCLUDED_POINTS)].copy()
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    df["speed_ratio"] = df["current_speed"] / df["freeflow_speed"]
    df["slot"] = df["ts_utc"].dt.floor("30min")
    df = df.groupby(["point_id", "slot"], as_index=False).agg(
        speed_ratio=("speed_ratio", "mean"),
        current_speed=("current_speed", "mean"),
        freeflow_speed=("freeflow_speed", "mean"),
        closure=("closure", "max"),
    )
    df["slot_ist"] = df["slot"].dt.tz_convert(IST)
    return df


def extract_episodes(df, threshold=0.5, min_slots=2):
    """Maximal runs of consecutive slots with speed_ratio < threshold.

    A gap of more than one missing slot breaks a run — we don't bridge
    unobserved time.
    """
    episodes = []
    for point_id, g in df.sort_values("slot").groupby("point_id"):
        g = g.reset_index(drop=True)
        below = g["speed_ratio"] < threshold
        gap_break = g["slot"].diff() > pd.Timedelta(minutes=35)
        block = (below.ne(below.shift()) | gap_break).cumsum()
        for _, blk in g[below].groupby(block[below]):
            if len(blk) < min_slots:
                continue
            episodes.append(
                {
                    "point_id": point_id,
                    "start_ist": blk["slot_ist"].iloc[0],
                    "end_ist": blk["slot_ist"].iloc[-1],
                    "hours": len(blk) * 0.5,
                    "min_ratio": round(float(blk["speed_ratio"].min()), 2),
                    "mean_ratio": round(float(blk["speed_ratio"].mean()), 2),
                }
            )
    cols = ["point_id", "start_ist", "end_ist", "hours", "min_ratio", "mean_ratio"]
    return pd.DataFrame(episodes, columns=cols)


def run_sensitivity(df, thresholds=(0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7)):
    rows = []
    for t in thresholds:
        eps = extract_episodes(df, threshold=t)
        rows.append(
            {
                "threshold": t,
                "episodes": len(eps),
                "points_affected": eps["point_id"].nunique(),
                "total_hours": eps["hours"].sum(),
                "median_hours": eps["hours"].median() if len(eps) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def main():
    df = load_raw()
    print(
        f"{len(df)} point-slots | {df['point_id'].nunique()} points | "
        f"{df['slot_ist'].min():%Y-%m-%d %H:%M} .. {df['slot_ist'].max():%Y-%m-%d %H:%M} IST"
    )
    print("\nEpisode-threshold sensitivity (min 2 consecutive slots):")
    print(run_sensitivity(df).to_string(index=False))

    eps = extract_episodes(df, threshold=0.5)
    if len(eps):
        print("\nLongest episodes @ threshold 0.5:")
        top = eps.sort_values(["hours", "min_ratio"], ascending=[False, True]).head(12)
        print(top.to_string(index=False))


if __name__ == "__main__":
    main()
