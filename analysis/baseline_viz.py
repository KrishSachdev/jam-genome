#!/usr/bin/env python3
"""Baseline traffic picture for the Ganeshotsav point set.

Two panels:
  left  -每 point x IST hour mean speed ratio, grouped by role (festival
          points, immersion routes, chokepoints, controls)
  right - mean hourly profile per role

This is the "before" half of the natural experiment: after 14 Sept the same
chart re-run over festival days is the comparison.

Usage:  python analysis/baseline_viz.py [--days 9]
"""
import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from episodes import ROOT, load_raw

FIG = ROOT / "analysis" / "figures"

SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("congestion", SEQ[::-1])
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"

ROLE = {"GANPATI": ("Festival / pandal roads", "#e34948"),
        "VISARJAN": ("Immersion routes", "#eb6834"),
        "CHOKE": ("Known chokepoints", "#4a3aa7"),
        "CONTROL": ("Controls (away from festival)", "#1baf7a")}


def roles():
    out = {}
    with open(ROOT / "corridors.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["point_id"]] = r["corridor"] if r["corridor"] in ROLE else "OTHER"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=9)
    args = ap.parse_args()

    df = load_raw(days=args.days)
    role = roles()
    df["role"] = df["point_id"].map(role)
    df = df[df["role"].notna()]
    df["hour"] = df["slot_ist"].dt.hour

    order = [p for r in ["GANPATI", "VISARJAN", "CHOKE", "CONTROL", "OTHER"]
             for p in sorted({k for k, v in role.items() if v == r})
             if p in set(df["point_id"])]
    pivot = df.pivot_table(index="point_id", columns="hour",
                           values="speed_ratio", aggfunc="mean").reindex(order)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(16, 9), width_ratios=[2.4, 1])
    fig.patch.set_facecolor(SURFACE)

    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap=CMAP, vmin=0.3, vmax=1.0)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_yticks(range(len(pivot)), pivot.index, fontsize=7)
    ax.set_xlabel("hour of day (IST)", color=INK2, fontsize=9)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    # bracket each role group on the RIGHT edge -- the left is occupied by the
    # point names and rotated labels there collide with them
    y = 0
    for key in ["GANPATI", "VISARJAN", "CHOKE", "CONTROL", "OTHER"]:
        n = sum(1 for p in pivot.index if role.get(p) == key)
        if not n:
            continue
        label, colour = ROLE.get(key, ("Kept from original set", "#898781"))
        ax.add_patch(plt.Rectangle((23.6, y - 0.5), 0.5, n, color=colour,
                                   clip_on=False, lw=0))
        ax.text(24.4, y + n / 2 - 0.5, label.replace(" (", "\n("), va="center",
                ha="left", color=colour, fontsize=8, fontweight="bold")
        y += n
    cb = fig.colorbar(im, ax=ax, shrink=0.5, pad=0.16)
    cb.set_label("mean speed ratio (dark = congested)", color=INK2, fontsize=8)
    cb.ax.tick_params(colors=MUTED, labelsize=7)
    cb.outline.set_visible(False)

    for key, (label, colour) in ROLE.items():
        sub = df[df["role"] == key]
        if not len(sub):
            continue
        prof = sub.groupby("hour")["speed_ratio"].mean()
        ax2.plot(prof.index, prof.to_numpy(), color=colour, lw=2.2, label=label)
    ax2.axhline(0.5, color=GRID, lw=1)
    ax2.set_xlim(0, 23)
    ax2.set_ylim(0.4, 1.02)
    ax2.grid(axis="y", color=GRID, lw=0.5)
    ax2.set_xlabel("hour of day (IST)", color=INK2, fontsize=9)
    ax2.set_ylabel("mean speed ratio", color=INK2, fontsize=9)
    ax2.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="lower left")
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.tick_params(colors=MUTED, labelsize=8)
    ax2.set_title("Average by role", color=INK, fontsize=10, loc="left")

    span = f"{df['slot_ist'].min():%d %b} - {df['slot_ist'].max():%d %b %Y}"
    fig.suptitle(f"Mumbai traffic baseline before Ganeshotsav  ({span}, {len(pivot)} points)",
                 color=INK, fontsize=13, x=0.02, ha="left", y=0.98)
    fig.tight_layout(rect=(0.02, 0, 1, 0.96))
    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / "baseline_ganpati.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")
    print(f"{len(pivot)} points, {df['slot_ist'].nunique()} slots, {span}")


if __name__ == "__main__":
    main()
