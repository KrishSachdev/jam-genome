#!/usr/bin/env python3
"""Phase 2 exploratory analysis.

Outputs (regenerated on every run; gitignored):
  analysis/outputs/league_table.csv        congestion league table
  analysis/figures/heatmap_hour_ist.png    point x IST-hour mean speed ratio
  analysis/figures/profiles_top6.png       hourly profiles, 6 most congested points

Times are IST; that's when Mumbai jams.
"""

import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from episodes import ROOT, load_raw

FIG_DIR = ROOT / "analysis" / "figures"
OUT_DIR = ROOT / "analysis" / "outputs"

# palette: sequential blue ramp + chart chrome (validated reference palette)
SEQ_BLUES = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]
SERIES_WEEKEND = "#2a78d6"  # categorical slot 1 (blue)
SERIES_WEEKDAY = "#1baf7a"  # categorical slot 2 (aqua)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"

# ramp runs dark->light so LOW speed ratio (congested) renders dark
CMAP = LinearSegmentedColormap.from_list("congestion", SEQ_BLUES[::-1])


def point_order():
    with open(ROOT / "corridors.csv", newline="", encoding="utf-8") as f:
        return [r["point_id"] for r in csv.DictReader(f)]


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)


def league_table(df):
    days = df.groupby("point_id")["slot_ist"].apply(lambda s: s.dt.date.nunique())
    per = df.groupby("point_id").agg(
        slots=("speed_ratio", "size"),
        congested_slots=("speed_ratio", lambda s: int((s < 0.5).sum())),
        mean_ratio=("speed_ratio", "mean"),
        p05_ratio=("speed_ratio", lambda s: s.quantile(0.05)),
    )
    per["congested_pct"] = per["congested_slots"] / per["slots"] * 100
    per["congested_h_per_day"] = per["congested_slots"] * 0.5 / days
    per = per.sort_values(["congested_h_per_day", "mean_ratio"], ascending=[False, True]).round(2)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per.to_csv(OUT_DIR / "league_table.csv")
    return per


def heatmap(df):
    df = df.copy()
    df["hour"] = df["slot_ist"].dt.hour
    pivot = df.pivot_table(index="point_id", columns="hour", values="speed_ratio", aggfunc="mean")
    pivot = pivot.reindex([p for p in point_order() if p in pivot.index])

    fig, ax = plt.subplots(figsize=(11, 9))
    fig.patch.set_facecolor(SURFACE)
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap=CMAP, vmin=0.3, vmax=1.0)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_yticks(range(len(pivot)), pivot.index)
    style_axes(ax)
    dates = f"{df['slot_ist'].min():%d %b} - {df['slot_ist'].max():%d %b %Y}"
    ax.set_title(
        f"Mean speed ratio by point and IST hour ({dates})",
        color=INK, fontsize=11, loc="left", pad=12,
    )
    ax.set_xlabel("hour of day (IST)", color=INK_2, fontsize=9)
    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label("mean speed ratio (dark = congested)", color=INK_2, fontsize=8)
    cbar.ax.tick_params(colors=MUTED, labelsize=8)
    cbar.outline.set_visible(False)
    fig.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "heatmap_hour_ist.png", dpi=160)
    plt.close(fig)


def profiles(df, league):
    worst = league.head(6).index.tolist()
    df = df.copy()
    df["hour"] = df["slot_ist"].dt.hour
    df["is_weekday"] = df["slot_ist"].dt.dayofweek < 5

    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5), sharex=True, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, pid in zip(axes.flat, worst):
        g = df[df["point_id"] == pid]
        for is_wd, color, label in (
            (False, SERIES_WEEKEND, "weekend"),
            (True, SERIES_WEEKDAY, "weekday"),
        ):
            prof = g[g["is_weekday"] == is_wd].groupby("hour")["speed_ratio"].mean()
            ax.plot(prof.index, prof.to_numpy(), color=color, linewidth=2, label=label)
        ax.axhline(0.5, color=GRID, linewidth=1)
        ax.set_title(pid, color=INK, fontsize=9, loc="left")
        ax.grid(axis="y", color=GRID, linewidth=0.5)
        style_axes(ax)
        ax.set_ylim(0.2, 1.05)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", frameon=False, labelcolor=INK_2, fontsize=9)
    fig.suptitle(
        "Hourly speed-ratio profiles - 6 most congested points (IST)",
        color=INK, fontsize=11, x=0.01, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG_DIR / "profiles_top6.png", dpi=160)
    plt.close(fig)


def main():
    df = load_raw()
    league = league_table(df)
    print("Congestion league table (share of 30-min slots with ratio < 0.5):")
    print(league.head(15).to_string())
    heatmap(df)
    profiles(df, league)
    print(f"\nfigures -> {FIG_DIR}")
    print(f"table   -> {OUT_DIR / 'league_table.csv'}")


if __name__ == "__main__":
    main()
