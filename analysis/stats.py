#!/usr/bin/env python3
"""Extended statistics beyond the basic league table.

Adds five things the simple report does not cover:

  1. episode duration distribution — how long a jam actually lasts
  2. morning vs evening peak per point — which peak each road suffers
  3. weekday vs weekend delta per point — which roads are commuter-driven
  4. worst hour of the week, city-wide
  5. co-occurrence — which pairs of points tend to jam at the same time.
     This is the closest thing to propagation available without the denser
     sampling the project never got to; it shows association, NOT causation
     or direction.

Usage:  python analysis/stats.py [--era B]
"""
import argparse

import pandas as pd

from episodes import ROOT, extract_episodes, load_raw

SPLIT = pd.Timestamp("2026-08-20").date()
THRESH = 0.5
OUT = ROOT / "analysis" / "outputs"


def pick_era(df, era):
    if era == "A":
        return df[df["slot_ist"].dt.date <= SPLIT]
    if era == "B":
        return df[df["slot_ist"].dt.date > SPLIT]
    return df


def episode_stats(g):
    eps = extract_episodes(g, THRESH)
    if not len(eps):
        return eps, None
    d = eps["hours"]
    summary = {
        "episodes": len(eps),
        "median_h": d.median(),
        "mean_h": d.mean(),
        "p90_h": d.quantile(0.9),
        "max_h": d.max(),
        "under_1h_pct": (d <= 1).mean() * 100,
        "over_3h_pct": (d > 3).mean() * 100,
    }
    return eps, summary


def peaks(g):
    g = g.copy()
    g["hour"] = g["slot_ist"].dt.hour
    morning = g[g["hour"].between(8, 11)].groupby("point_id")["speed_ratio"].mean()
    evening = g[g["hour"].between(17, 21)].groupby("point_id")["speed_ratio"].mean()
    t = pd.DataFrame({"morning": morning, "evening": evening})
    t["worse_peak"] = ["evening" if e < m else "morning"
                       for m, e in zip(t["morning"], t["evening"])]
    t["gap"] = (t["morning"] - t["evening"]).abs()
    return t.round(3)


def weekend_delta(g):
    g = g.copy()
    g["wd"] = g["slot_ist"].dt.dayofweek < 5
    g = g[g["slot_ist"].dt.hour.between(8, 21)]     # daytime only
    wd = g[g["wd"]].groupby("point_id")["speed_ratio"].mean()
    we = g[~g["wd"]].groupby("point_id")["speed_ratio"].mean()
    t = pd.DataFrame({"weekday": wd, "weekend": we})
    t["weekend_better_by"] = (t["weekend"] - t["weekday"]).round(3)
    return t.round(3)


def worst_hour_of_week(g):
    g = g.copy()
    g["dow"] = g["slot_ist"].dt.day_name()
    g["hour"] = g["slot_ist"].dt.hour
    t = g.groupby(["dow", "hour"])["speed_ratio"].mean().reset_index()
    return t.sort_values("speed_ratio").head(10)


def cooccurrence(g, top_n=12):
    """Correlation of per-point congestion across time slots."""
    w = g.pivot_table(index="slot", columns="point_id", values="speed_ratio")
    keep = [c for c in w.columns if (w[c] < THRESH).sum() >= 10]
    if len(keep) < 2:
        return None
    c = (w[keep] < THRESH).astype(int).corr()
    out = []
    cols = list(c.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            out.append((a, b, c.loc[a, b]))
    res = pd.DataFrame(out, columns=["point_a", "point_b", "corr"])
    return res.sort_values("corr", ascending=False).head(top_n).round(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--era", default="B", choices=["A", "B", "all"])
    args = ap.parse_args()

    df = load_raw()
    g = pick_era(df, args.era)
    days = g["slot_ist"].dt.date.nunique()
    print(f"era {args.era}: {g['point_id'].nunique()} points, {days} days, "
          f"{len(g):,} point-slots\n")

    eps, summ = episode_stats(g)
    if summ:
        print("1. EPISODE DURATION (a jam = 2+ consecutive 30-min slots below 0.5)")
        print(f"   {summ['episodes']} episodes | median {summ['median_h']:.1f} h | "
              f"mean {summ['mean_h']:.1f} h | 90th pct {summ['p90_h']:.1f} h | "
              f"longest {summ['max_h']:.1f} h")
        print(f"   {summ['under_1h_pct']:.0f}% last an hour or less; "
              f"{summ['over_3h_pct']:.0f}% run past 3 hours\n")

    pk = peaks(g)
    ev = pk[pk["worse_peak"] == "evening"]
    print("2. MORNING vs EVENING PEAK")
    print(f"   {len(ev)}/{len(pk)} points are worse in the evening")
    print("   biggest evening-skewed points:")
    for pid, r in pk[pk.worse_peak == "evening"].sort_values("gap", ascending=False).head(5).iterrows():
        print(f"     {pid:<24} morning {r.morning:.2f} -> evening {r.evening:.2f}")
    print("   points that are worse in the MORNING:")
    for pid, r in pk[pk.worse_peak == "morning"].sort_values("gap", ascending=False).head(5).iterrows():
        print(f"     {pid:<24} morning {r.morning:.2f} vs evening {r.evening:.2f}")
    print()

    wk = weekend_delta(g).dropna()
    print("3. WEEKDAY vs WEEKEND (daytime 08:00-21:00)")
    print("   most commuter-driven (weekend much freer):")
    for pid, r in wk.sort_values("weekend_better_by", ascending=False).head(5).iterrows():
        print(f"     {pid:<24} weekday {r.weekday:.2f} -> weekend {r.weekend:.2f} "
              f"(+{r.weekend_better_by:.2f})")
    worse = wk[wk["weekend_better_by"] < 0]
    print(f"   {len(worse)}/{len(wk)} points are actually WORSE at the weekend:")
    for pid, r in worse.sort_values("weekend_better_by").head(5).iterrows():
        print(f"     {pid:<24} weekday {r.weekday:.2f} -> weekend {r.weekend:.2f} "
              f"({r.weekend_better_by:.2f})")
    print()

    print("4. WORST HOURS OF THE WEEK (city-wide mean speed ratio)")
    for r in worst_hour_of_week(g).itertuples():
        print(f"     {r.dow:<10} {r.hour:02d}:00   {r.speed_ratio:.3f}")
    print()

    co = cooccurrence(g)
    if co is not None:
        print("5. POINTS THAT JAM TOGETHER (association, not causation)")
        for r in co.itertuples():
            print(f"     {r.corr:+.2f}  {r.point_a} <-> {r.point_b}")
        OUT.mkdir(parents=True, exist_ok=True)
        co.to_csv(OUT / f"cooccurrence_era{args.era}.csv", index=False)

    OUT.mkdir(parents=True, exist_ok=True)
    pk.to_csv(OUT / f"peaks_era{args.era}.csv")
    wk.to_csv(OUT / f"weekend_era{args.era}.csv")
    if len(eps):
        eps.to_csv(OUT / f"episodes_era{args.era}.csv", index=False)
    print(f"\nwrote CSVs to {OUT}")


if __name__ == "__main__":
    main()
