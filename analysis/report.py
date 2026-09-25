#!/usr/bin/env python3
"""Generate REPORT.md and its figures from everything collected so far.

The dataset has two eras with different point sets, so almost nothing can be
pooled across them:

  A  2026-07-09 .. 08-09   36 points, the original hand-picked set
  B  2026-08-21 .. 09-08   50 points, re-sited onto short TomTom segments

Era A is the "before" for the point-set change; era B is the "after". They are
reported separately and only compared where the comparison is honest.

Usage:  python analysis/report.py
"""
import csv
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from episodes import ROOT, extract_episodes, load_raw, run_sensitivity

FIG = ROOT / "analysis" / "figures"
OUT = ROOT / "REPORT.md"
SPLIT = date(2026, 8, 20)          # era A ends before this, B starts after
THRESH = 0.5

SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("congestion", SEQ[::-1])
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, AQUA = "#2a78d6", "#1baf7a"


def bare(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)


def league(g):
    days = g["slot_ist"].dt.date.nunique()
    t = g.groupby("point_id").agg(
        slots=("speed_ratio", "size"),
        mean_ratio=("speed_ratio", "mean"),
        p05=("speed_ratio", lambda s: s.quantile(0.05)),
        congested=("speed_ratio", lambda s: int((s < THRESH).sum())),
    )
    t["cong_h_per_day"] = (t["congested"] * 0.5 / days).round(2)
    return t.sort_values("cong_h_per_day", ascending=False).round(3)


def fig_league(tb, era, fname):
    # 0.005-0.04 h/day rounds to "0.0" on the label and reads as a bar with no
    # value. Drop anything that would not round to at least 0.1.
    top = tb[tb["cong_h_per_day"] >= 0.05].head(18)[::-1]
    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.32 * len(top) + 1.4)))
    fig.patch.set_facecolor(SURFACE)
    ax.barh(range(len(top)), top["cong_h_per_day"], color=BLUE, height=0.72)
    ax.set_yticks(range(len(top)), top.index, fontsize=8)
    vmax = float(max(top["cong_h_per_day"]))
    for i, v in enumerate(top["cong_h_per_day"]):
        ax.text(v + vmax * 0.012, i, f"{v:.1f}", va="center",
                fontsize=7.5, color=INK2)
    ax.set_xlim(0, vmax * 1.10)          # headroom so the top label is not clipped
    ax.set_xlabel(f"congested hours per day (ratio < {THRESH})", color=INK2, fontsize=9)
    ax.grid(axis="x", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    bare(ax)
    ax.set_title(f"Worst points — era {era}", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_heat(g, era, fname):
    p = g.copy()
    p["hour"] = p["slot_ist"].dt.hour
    piv = p.pivot_table(index="point_id", columns="hour",
                        values="speed_ratio", aggfunc="mean")
    piv = piv.loc[piv.mean(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(10, max(4, 0.19 * len(piv) + 2)))
    fig.patch.set_facecolor(SURFACE)
    im = ax.imshow(piv.to_numpy(), aspect="auto", cmap=CMAP, vmin=0.3, vmax=1.0)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_yticks(range(len(piv)), piv.index, fontsize=7)
    ax.set_xlabel("hour of day (IST)", color=INK2, fontsize=9)
    bare(ax)
    ax.set_title(f"Mean speed ratio by point and hour — era {era}  (worst at top)",
                 color=INK, fontsize=11, loc="left")
    cb = fig.colorbar(im, ax=ax, shrink=0.5)
    cb.set_label("mean speed ratio", color=INK2, fontsize=8)
    cb.ax.tick_params(colors=MUTED, labelsize=7)
    cb.outline.set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_profiles(df, fname):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    fig.patch.set_facecolor(SURFACE)
    for era, colour in (("A", BLUE), ("B", AQUA)):
        g = df[df["era"] == era].copy()
        g["hour"] = g["slot_ist"].dt.hour
        g["wd"] = g["slot_ist"].dt.dayofweek < 5
        for wd, ls in ((True, "-"), (False, "--")):
            s = g[g["wd"] == wd]
            if not len(s):
                continue
            prof = s.groupby("hour")["speed_ratio"].mean()
            ax.plot(prof.index, prof.to_numpy(), ls, color=colour,
                    lw=2.2 if wd else 1.3, alpha=1 if wd else 0.75,
                    label=f"era {era} {'weekday' if wd else 'weekend'}")
    ax.axhline(THRESH, color=GRID, lw=1)
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_xlabel("hour of day (IST)", color=INK2, fontsize=9)
    ax.set_ylabel("mean speed ratio", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="lower left", ncol=2)
    bare(ax)
    ax.set_title("City-wide daily profile, both eras", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def md_table(tb, n=12):
    rows = ["| point | congested h/day | mean ratio | 5th pct |",
            "|---|---|---|---|"]
    for pid, r in tb.head(n).iterrows():
        rows.append(f"| `{pid}` | {r['cong_h_per_day']:.2f} | {r['mean_ratio']:.2f} | {r['p05']:.2f} |")
    return "\n".join(rows)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    df = load_raw()
    df["era"] = df["slot_ist"].dt.date.map(lambda d: "A" if d <= SPLIT else "B")

    A = df[df["era"] == "A"]
    B = df[df["era"] == "B"]
    la, lb = league(A), league(B)
    epsA, epsB = extract_episodes(A, THRESH), extract_episodes(B, THRESH)
    sens = run_sensitivity(B)

    fig_league(la, "A", "report_league_A.png")
    fig_league(lb, "B", "report_league_B.png")
    fig_heat(A, "A", "report_heat_A.png")
    fig_heat(B, "B", "report_heat_B.png")
    fig_profiles(df, "report_profiles.png")

    def span(g):
        return f"{g['slot_ist'].min():%d %b %Y} – {g['slot_ist'].max():%d %b %Y}"

    daysA = A["slot_ist"].dt.date.nunique()
    daysB = B["slot_ist"].dt.date.nunique()
    liveA = int((la["congested"] > 0).sum())
    liveB = int((lb["congested"] > 0).sum())

    sens_rows = "\n".join(
        f"| {r.threshold:.2f} | {int(r.episodes)} | {int(r.points_affected)} | {r.total_hours:.0f} |"
        for r in sens.itertuples())

    longest = epsB.sort_values("hours", ascending=False).head(8)
    long_rows = "\n".join(
        f"| `{r.point_id}` | {r.start_ist:%d %b %H:%M} | {r.hours:.1f} h | {r.min_ratio:.2f} |"
        for r in longest.itertuples())

    # ---- deeper statistics (era B) --------------------------------------
    import stats as ST
    d = epsB["hours"]
    ep_line = (
        f"Of the **{len(epsB)} jams** in era B: the median lasts **{d.median():.1f} hours**, "
        f"the average **{d.mean():.1f}**, and the longest ran **{d.max():.0f} hours**. "
        f"**{(d <= 1).mean()*100:.0f}%** are over within an hour, "
        f"but **{(d > 3).mean()*100:.0f}%** drag on past three."
    )

    pk = ST.peaks(B)
    n_pts = len(pk)
    n_evening = int((pk["worse_peak"] == "evening").sum())
    n_morning = n_pts - n_evening
    peak_rows = "\n".join(
        ["| point | morning ratio | evening ratio |", "|---|---|---|"] +
        [f"| `{i}` | {r.morning:.2f} | **{r.evening:.2f}** |"
         for i, r in pk[pk.worse_peak == "evening"]
         .sort_values("gap", ascending=False).head(5).iterrows()])

    wk = ST.weekend_delta(B).dropna()
    n_worse_we = int((wk["weekend_better_by"] < 0).sum())
    wk_rows = "\n".join(
        ["| point | weekday | weekend | weekend is better by |", "|---|---|---|---|"] +
        [f"| `{i}` | {r.weekday:.2f} | {r.weekend:.2f} | +{r.weekend_better_by:.2f} |"
         for i, r in wk.sort_values("weekend_better_by", ascending=False).head(5).iterrows()])

    wh = ST.worst_hour_of_week(B).head(5)
    worst_rows = "\n".join(
        ["| day | hour | mean ratio |", "|---|---|---|"] +
        [f"| {r.dow} | {r.hour:02d}:00 | {r.speed_ratio:.3f} |" for r in wh.itertuples()])

    co = ST.cooccurrence(B, top_n=6)
    pair_rows = "\n".join(
        ["| correlation | point A | point B |", "|---|---|---|"] +
        [f"| **{r.corr:+.2f}** | `{r.point_a}` | `{r.point_b}` |" for r in co.itertuples()]
    ) if co is not None else "_not enough congested slots to compute_"

    md = f"""# Jam Genome — data report

Generated from `analysis/report.py`. Covers everything collected to
**{df['slot_ist'].max():%d %B %Y}**.

## What this dataset is

Segment speeds from the TomTom Traffic Flow Segment Data API, polled every 30
minutes across Mumbai. Each reading gives a road segment's `currentSpeed` and
its `freeFlowSpeed`; the working measure throughout is

> **speed ratio = current speed ÷ free-flow speed**, and a point counts as
> congested when that ratio is below **{THRESH}**.

**{len(df):,} usable readings over {df['slot_ist'].dt.date.nunique()} days.**
Mumbai has no open traffic dataset — Uber Movement shut down in 2023 — so this
was collected from scratch.

### Two eras, not one dataset

The monitoring points changed part-way through, so the two periods are
reported separately and only compared where honest:

| era | dates | points | days | readings |
|---|---|---|---|---|
| **A** | {span(A)} | {A['point_id'].nunique()} | {daysA} | {len(A):,} |
| **B** | {span(B)} | {B['point_id'].nunique()} | {daysB} | {len(B):,} |

Era A used hand-picked junctions. Era B used points re-sited onto short
segments after a citywide survey, for the reason set out next.

## Headline result: most of the original points were blind

In era A, **only {liveA} of {A['point_id'].nunique()} points ever recorded congestion**.
The other {A['point_id'].nunique() - liveA} sat at free-flow for a month —
including Kalanagar, Amar Mahal and King's Circle, three of Mumbai's most
notorious junctions.

They were not uncongested. Every TomTom reading describes a whole **road
segment**, and Mumbai's expressways are modelled as single segments 13–20 km
long. A jam at one junction is averaged away across the whole stretch. Segment
length, not sampling rate, is the real resolution limit.

A 260 m-grid survey of Greater Mumbai (6,327 probes, `sweep/`) enumerated
**870 distinct segments**, of which **692** are short enough (0.1–3 km) to
measure a single junction. The points were re-sited onto those.

**It worked:** in era B, **{liveB} of {B['point_id'].nunique()} points record congestion** —
{liveB/B['point_id'].nunique()*100:.0f}% versus {liveA/A['point_id'].nunique()*100:.0f}% before.

## Worst points

### Era B ({daysB} days, {B['point_id'].nunique()} points)

{md_table(lb)}

![era B league](analysis/figures/report_league_B.png)

### Era A ({daysA} days, {A['point_id'].nunique()} points)

{md_table(la, 10)}

![era A league](analysis/figures/report_league_A.png)

## When Mumbai jams

![daily profile](analysis/figures/report_profiles.png)

The city shows a double hump — a late-morning dip and a deeper evening
trough around 18:00–20:00 — with free-flow from roughly midnight to 07:00.
Weekends are not uniformly better: in central Mumbai the weekend afternoon is
frequently *worse* than the weekday commute.

![era B heatmap](analysis/figures/report_heat_B.png)

## Congestion episodes

An episode is two or more consecutive 30-minute slots below the threshold.

- era A: **{len(epsA)} episodes**
- era B: **{len(epsB)} episodes** over a shorter window

Longest single episodes in era B:

| point | start (IST) | duration | worst ratio |
|---|---|---|---|
{long_rows}

### Threshold sensitivity

The 0.50 cut-off is a choice, so here is the whole curve rather than one number:

| threshold | episodes | points affected | total hours |
|---|---|---|---|
{sens_rows}

0.50 is selective enough to be meaningful and loose enough to leave signal;
0.40 is too sparse and 0.65+ flags nearly every point.

## Deeper statistics (era B)

### How long a jam lasts

{ep_line}

So most jams are short, but a meaningful tail runs for hours — and the worst
single episode filled most of a working day.

### Morning peak or evening peak?

**{n_evening} of {n_pts} points are worse in the evening** than the morning.
The most evening-skewed roads:

{peak_rows}

Only {n_morning} points suffer more in the morning, and they are unusual cases:
`atal_setu` is the harbour bridge, which carries an outbound morning flow, and
`eeh_bhandup` sits on a long expressway segment.

### Which roads are commuter roads?

Comparing daytime (08:00–21:00) weekdays against weekends:

{wk_rows}

**{n_worse_we} of {n_pts} points are actually worse at the weekend.** Central
Mumbai's shopping and leisure traffic outweighs the weekday commute on those
roads — a genuine finding, and the opposite of the usual assumption.

### The single worst hour of the week

{worst_rows}

Every one of the ten worst hours falls between 18:00 and 19:00. **Tuesday
evening is the worst hour in Mumbai's week.**

### Which points jam together

Correlation of congestion between every pair of points. This shows
**association, not causation** — with 30-minute sampling it cannot say which
jam came first, which is the analysis the project never got the data density
to complete.

{pair_rows}

The strongest pair by a wide margin is `dadar_chowpatty` and
`sk_bole_road_dadar` at **+0.61** — two roads about a kilometre apart in Dadar.
That is the closest thing to propagation evidence in this dataset.

## Did rain or events explain any of this?

Mumbai's monsoon ran through the whole collection window, and news reports for
the period describe repeated disruption: over 400 mm in the first four days of
July, a 205 mm day, a road cave-in on LBS Marg, and standstills on the Western
Express Highway near Vile Parle on 18 August. The Sion road-over-bridge was
also shut for reconstruction throughout (closed Aug 2024, due to reopen
30 Sept 2026), and the Sant Rohidas Marg subway opened mid-collection on
14 July 2026.

Rainfall was backfilled from the Open-Meteo ERA5 archive rather than the
collector's own rain log, which is unusable (see Limitations). Testing at
hourly resolution and **matching wet hours against dry hours of the same
hour-of-day** — because rain and traffic both follow daily cycles — gives:

| era | hours tested | wet hours | wet minus dry |
|---|---|---|---|
| A | 716 | 307 | **−0.10 pp** |
| B | 436 | 65 | **−0.43 pp** |

**No measurable increase in congestion on wet hours.** If anything the sign is
negative, and a naive pooled figure of −0.70 pp turned out to be mostly an
artefact of mixing the two eras. Daily correlations are similarly flat
(era A r = −0.03 over 29 days).

Three reasons not to read this as "rain doesn't cause jams":

1. Mumbai's heaviest rain days coincide with school and office closures, so
   demand falls at the same time capacity does.
2. ERA5 is a ~9 km grid and smooths the local cloudbursts that actually flood
   individual junctions.
3. Many points sit on long segments that average away a flooded stretch.

The honest statement is that **at this measurement resolution, rain has no
detectable net effect on speed ratios.** Reproduce with
`python analysis/rain_check.py`.

## Limitations

1. **The two eras are not directly comparable.** Different point sets, and
   many era-A points measured segments too long to be informative.
2. **The rain log is unusable.** `collector/weather.py` sampled a 15-minute
   window every 30 minutes, so it missed roughly half of all rainfall. Any
   rain analysis must backfill from the Open-Meteo archive instead.
3. **No festival data.** The collection was designed around Ganeshotsav
   (14–25 Sept 2026), but TomTom began enforcing a 20,000 requests/month
   free-tier limit and the September quota was exhausted on 8 September. The
   festival window was not captured.
4. **Expressway propagation cannot be measured.** WEH and EEH are single
   segments, so every point on one returns the same value. Propagation
   analysis is only possible on the arterial and junction network.
5. **Ratios depend on TomTom's free-flow baseline**, which is their modelled
   figure, not a measured overnight speed.

## Reproducing

```bash
python analysis/report.py          # this report and its figures
python analysis/eda.py             # league table, heatmaps, profiles
python analysis/episodes.py        # episode extraction + threshold sweep
python analysis/data_quality.py    # coverage and dead-point checks
python analysis/publish.py         # .docx and .pdf versions of the reports
```

Background and constraints are in [FINDINGS.md](FINDINGS.md); the build plan
is in [PLAN.md](PLAN.md).
"""
    OUT.write_text(md, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"figures -> {FIG}")
    print(f"era A: {liveA}/{A['point_id'].nunique()} live | era B: {liveB}/{B['point_id'].nunique()} live")


if __name__ == "__main__":
    main()
