#!/usr/bin/env python3
"""Detailed pre-festival baseline report, stacked vertically.

Four panels, read top to bottom:
  1. hourly speed-ratio profile per role, weekday vs weekend
  2. every point x hour of day, grouped by role (names colour-coded)
  3. congestion-hours per day, worst points first
  4. day-by-day means, to show the baseline is stable before 14 Sept

Roles come from the `corridor` column of corridors.csv, which encodes each
point's job in the Ganeshotsav experiment.

Usage:  python analysis/baseline_report.py [--days 9] [--out NAME.png]
"""
import argparse
import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

from episodes import ROOT, load_raw

FIG = ROOT / "analysis" / "figures"

SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("congestion", SEQ[::-1])
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"

ROLES = [("GANPATI", "Festival / pandal roads", "#e34948"),
         ("VISARJAN", "Immersion routes", "#eb6834"),
         ("CHOKE", "Known chokepoints", "#4a3aa7"),
         ("CONTROL", "Controls (away from festival)", "#1baf7a"),
         ("OTHER", "Kept from original set", "#767674")]
LABEL = {k: v for k, v, _ in ROLES}
COLOUR = {k: c for k, _, c in ROLES}
THRESHOLD = 0.5


def load_roles():
    known = {k for k, _, _ in ROLES}
    out = {}
    with open(ROOT / "corridors.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["point_id"]] = r["corridor"] if r["corridor"] in known else "OTHER"
    return out


def bare(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=9)
    ap.add_argument("--out", default="baseline_report.png")
    args = ap.parse_args()

    df = load_raw(days=args.days)
    role = load_roles()
    df["role"] = df["point_id"].map(role)
    df = df[df["role"].notna()].copy()
    df["hour"] = df["slot_ist"].dt.hour
    df["date"] = df["slot_ist"].dt.date
    df["weekday"] = df["slot_ist"].dt.dayofweek < 5

    order = [p for k, _, _ in ROLES
             for p in sorted({q for q, v in role.items() if v == k})
             if p in set(df["point_id"])]

    fig = plt.figure(figsize=(13.5, 21))
    fig.patch.set_facecolor(SURFACE)
    gs = fig.add_gridspec(4, 1, height_ratios=[3.0, 8.0, 4.4, 2.4], hspace=0.30,
                          left=0.20, right=0.95, top=0.955, bottom=0.035)

    # ---- 1. hourly profile per role, weekday vs weekend ------------------
    ax1 = fig.add_subplot(gs[0])
    for key, label, colour in ROLES:
        sub = df[df["role"] == key]
        if not len(sub):
            continue
        for wd, style in ((True, "-"), (False, "--")):
            s = sub[sub["weekday"] == wd]
            if not len(s):
                continue
            prof = s.groupby("hour")["speed_ratio"].mean()
            ax1.plot(prof.index, prof.to_numpy(), style, color=colour,
                     lw=2.2 if wd else 1.4, alpha=1.0 if wd else 0.75)
    ax1.axhline(THRESHOLD, color=GRID, lw=1)
    ax1.set_xlim(0, 23)
    ax1.set_xticks(range(0, 24, 2))
    ax1.grid(axis="y", color=GRID, lw=0.5)
    ax1.set_ylabel("mean speed ratio", color=INK2, fontsize=9)
    ax1.set_xlabel("hour of day (IST)", color=INK2, fontsize=9)
    bare(ax1)
    ax1.set_title("1 — How each group's day looks now   (solid = weekday, dashed = weekend)",
                  color=INK, fontsize=11, loc="left", pad=8)
    handles = [Line2D([], [], color=c, lw=2.4, label=l) for _, l, c in ROLES]
    ax1.legend(handles=handles, frameon=False, fontsize=8.5, labelcolor=INK2,
               loc="lower left", ncol=2)

    # ---- 2. heatmap ------------------------------------------------------
    ax2 = fig.add_subplot(gs[1])
    pivot = df.pivot_table(index="point_id", columns="hour",
                           values="speed_ratio", aggfunc="mean").reindex(order)
    im = ax2.imshow(pivot.to_numpy(), aspect="auto", cmap=CMAP, vmin=0.3, vmax=1.0)
    ax2.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax2.set_yticks(range(len(pivot)), pivot.index, fontsize=7.5)
    # colour the point names by role -- no side bar to collide with anything
    for tick, pid in zip(ax2.get_yticklabels(), pivot.index):
        tick.set_color(COLOUR[role[pid]])
    # hairlines between role groups
    y = 0
    for key, _, _ in ROLES:
        n = sum(1 for p in pivot.index if role[p] == key)
        if not n:
            continue
        y += n
        if y < len(pivot):
            ax2.axhline(y - 0.5, color=SURFACE, lw=2.5)
    ax2.set_xlabel("hour of day (IST)", color=INK2, fontsize=9)
    bare(ax2)
    ax2.set_title("2 — Every point, hour by hour   (point names coloured by group)",
                  color=INK, fontsize=11, loc="left", pad=8)
    cb = fig.colorbar(im, ax=ax2, shrink=0.45, pad=0.02)
    cb.set_label("mean speed ratio (dark = congested)", color=INK2, fontsize=8)
    cb.ax.tick_params(colors=MUTED, labelsize=7)
    cb.outline.set_visible(False)

    # ---- 3. congestion hours per day ------------------------------------
    ax3 = fig.add_subplot(gs[2])
    ndays = df["date"].nunique()
    cong = (df[df["speed_ratio"] < THRESHOLD].groupby("point_id").size() * 0.5 / ndays)
    cong = cong.reindex([p for p in order]).fillna(0).sort_values(ascending=True)
    cong = cong[cong > 0].tail(22)
    ax3.barh(range(len(cong)), cong.to_numpy(),
             color=[COLOUR[role[p]] for p in cong.index], height=0.72)
    ax3.set_yticks(range(len(cong)), cong.index, fontsize=7.5)
    for tick, pid in zip(ax3.get_yticklabels(), cong.index):
        tick.set_color(COLOUR[role[pid]])
    for i, v in enumerate(cong.to_numpy()):
        ax3.text(v + 0.04, i, f"{v:.1f}", va="center", fontsize=7, color=INK2)
    ax3.set_xlabel(f"hours per day below ratio {THRESHOLD}", color=INK2, fontsize=9)
    ax3.grid(axis="x", color=GRID, lw=0.5)
    ax3.set_axisbelow(True)
    bare(ax3)
    ax3.set_title(f"3 — Which points actually jam   (mean congested hours/day over {ndays} days)",
                  color=INK, fontsize=11, loc="left", pad=8)

    # ---- 4. day by day ---------------------------------------------------
    ax4 = fig.add_subplot(gs[3])
    for key, label, colour in ROLES:
        sub = df[df["role"] == key]
        if not len(sub):
            continue
        daily = sub.groupby("date")["speed_ratio"].mean()
        ax4.plot(range(len(daily)), daily.to_numpy(), "o-", color=colour, lw=1.8, ms=4)
    days = sorted(df["date"].unique())
    ax4.set_xticks(range(len(days)), [d.strftime("%d %b") for d in days], fontsize=8)
    ax4.grid(axis="y", color=GRID, lw=0.5)
    ax4.set_ylabel("daily mean ratio", color=INK2, fontsize=9)
    bare(ax4)
    ax4.set_title("4 — Day-to-day stability   (flat lines = a trustworthy baseline)",
                  color=INK, fontsize=11, loc="left", pad=8)

    span = f"{df['slot_ist'].min():%d %b} – {df['slot_ist'].max():%d %b %Y}"
    fig.suptitle(f"Mumbai traffic baseline before Ganeshotsav\n{span}  ·  {len(pivot)} points  ·  "
                 f"{df['slot_ist'].nunique()} half-hour slots",
                 color=INK, fontsize=15, x=0.02, ha="left", y=0.988)

    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / args.out
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {out}")
    print(f"{len(pivot)} points | {ndays} days | {span}")


if __name__ == "__main__":
    main()
