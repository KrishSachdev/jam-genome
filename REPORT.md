# Jam Genome — data report

Generated from `analysis/report.py`. Covers everything collected to
**09 September 2026**.

## What this dataset is

Segment speeds from the TomTom Traffic Flow Segment Data API, polled every 30
minutes across Mumbai. Each reading gives a road segment's `currentSpeed` and
its `freeFlowSpeed`; the working measure throughout is

> **speed ratio = current speed ÷ free-flow speed**, and a point counts as
> congested when that ratio is below **0.5**.

**93,839 usable readings over 51 days.**
Mumbai has no open traffic dataset — Uber Movement shut down in 2023 — so this
was collected from scratch.

### Two eras, not one dataset

The monitoring points changed part-way through, so the two periods are
reported separately and only compared where honest:

| era | dates | points | days | readings |
|---|---|---|---|---|
| **A** | 10 Jul 2026 – 10 Aug 2026 | 36 | 32 | 50,453 |
| **B** | 22 Aug 2026 – 09 Sep 2026 | 50 | 19 | 43,386 |

Era A used hand-picked junctions. Era B used points re-sited onto short
segments after a citywide survey, for the reason set out next.

## Headline result: most of the original points were blind

In era A, **only 19 of 36 points ever recorded congestion**.
The other 17 sat at free-flow for a month —
including Kalanagar, Amar Mahal and King's Circle, three of Mumbai's most
notorious junctions.

They were not uncongested. Every TomTom reading describes a whole **road
segment**, and Mumbai's expressways are modelled as single segments 13–20 km
long. A jam at one junction is averaged away across the whole stretch. Segment
length, not sampling rate, is the real resolution limit.

A 260 m-grid survey of Greater Mumbai (6,327 probes, `sweep/`) enumerated
**870 distinct segments**, of which **692** are short enough (0.1–3 km) to
measure a single junction. The points were re-sited onto those.

**It worked:** in era B, **42 of 50 points record congestion** —
84% versus 53% before.

## Worst points

### Era B (19 days, 50 points)

| point | congested h/day | mean ratio | 5th pct |
|---|---|---|---|
| `sk_bole_road_dadar` | 8.63 | 0.67 | 0.23 |
| `dadar_chowpatty` | 5.76 | 0.74 | 0.30 |
| `weh_kherwadi` | 2.74 | 0.83 | 0.37 |
| `opera_house` | 2.37 | 0.79 | 0.42 |
| `eeh_sion` | 1.92 | 0.80 | 0.46 |
| `hindmata_junction` | 1.87 | 0.77 | 0.46 |
| `eeh_vikhroli` | 1.18 | 0.89 | 0.49 |
| `eeh_teen_hath` | 1.16 | 0.79 | 0.48 |
| `sion_circle` | 1.03 | 0.87 | 0.51 |
| `atal_setu` | 0.84 | 0.95 | 0.66 |
| `chintamani_chinchpokli` | 0.71 | 0.77 | 0.50 |
| `bandra_bandstand` | 0.68 | 0.87 | 0.53 |

![era B league](analysis/figures/report_league_B.png)

### Era A (32 days, 36 points)

| point | congested h/day | mean ratio | 5th pct |
|---|---|---|---|
| `weh_kherwadi` | 2.66 | 0.81 | 0.39 |
| `eeh_sion` | 2.08 | 0.79 | 0.46 |
| `eeh_vikhroli` | 1.73 | 0.88 | 0.44 |
| `eeh_teen_hath` | 1.22 | 0.79 | 0.47 |
| `jvlr_powai` | 0.48 | 0.88 | 0.56 |
| `sion_circle` | 0.47 | 0.89 | 0.57 |
| `eeh_bhandup` | 0.25 | 0.90 | 0.63 |
| `lbs_kurla` | 0.22 | 0.92 | 0.62 |
| `linking_road` | 0.22 | 0.82 | 0.55 |
| `hindmata` | 0.09 | 0.93 | 0.67 |

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

- era A: **134 episodes**
- era B: **215 episodes** over a shorter window

Longest single episodes in era B:

| point | start (IST) | duration | worst ratio |
|---|---|---|---|
| `sk_bole_road_dadar` | 22 Aug 12:00 | 12.0 h | 0.15 |
| `sk_bole_road_dadar` | 25 Aug 11:00 | 11.0 h | 0.26 |
| `sk_bole_road_dadar` | 01 Sep 11:00 | 11.0 h | 0.15 |
| `sk_bole_road_dadar` | 29 Aug 12:00 | 10.5 h | 0.15 |
| `sk_bole_road_dadar` | 06 Sep 12:00 | 10.0 h | 0.09 |
| `sk_bole_road_dadar` | 02 Sep 13:00 | 9.0 h | 0.11 |
| `acharya_donde` | 29 Aug 10:30 | 9.0 h | 0.05 |
| `sk_bole_road_dadar` | 03 Sep 10:30 | 9.0 h | 0.15 |

### Threshold sensitivity

The 0.50 cut-off is a choice, so here is the whole curve rather than one number:

| threshold | episodes | points affected | total hours |
|---|---|---|---|
| 0.40 | 101 | 18 | 216 |
| 0.45 | 153 | 23 | 340 |
| 0.50 | 215 | 30 | 476 |
| 0.55 | 389 | 36 | 812 |
| 0.60 | 590 | 43 | 1322 |
| 0.65 | 850 | 45 | 2087 |
| 0.70 | 1042 | 47 | 2935 |

0.50 is selective enough to be meaningful and loose enough to leave signal;
0.40 is too sparse and 0.65+ flags nearly every point.

## Deeper statistics (era B)

### How long a jam lasts

Of the **215 jams** in era B: the median lasts **1.5 hours**, the average **2.2**, and the longest ran **12 hours**. **41%** are over within an hour, but **15%** drag on past three.

So most jams are short, but a meaningful tail runs for hours — and the worst
single episode filled most of a working day.

### Morning peak or evening peak?

**48 of 50 points are worse in the evening** than the morning.
The most evening-skewed roads:

| point | morning ratio | evening ratio |
|---|---|---|
| `dadar_chowpatty` | 0.87 | **0.48** |
| `sk_bole_road_dadar` | 0.73 | **0.36** |
| `sion_circle` | 0.97 | **0.66** |
| `eeh_vikhroli` | 0.96 | **0.65** |
| `ctl_jogeshwari` | 0.93 | **0.63** |

Only 2 points suffer more in the morning, and they are unusual cases:
`atal_setu` is the harbour bridge, which carries an outbound morning flow, and
`eeh_bhandup` sits on a long expressway segment.

### Which roads are commuter roads?

Comparing daytime (08:00–21:00) weekdays against weekends:

| point | weekday | weekend | weekend is better by |
|---|---|---|---|
| `eeh_vikhroli` | 0.78 | 0.93 | +0.15 |
| `weh_kherwadi` | 0.68 | 0.82 | +0.15 |
| `jvlr_powai` | 0.77 | 0.91 | +0.14 |
| `marine_drive_approach` | 0.82 | 0.94 | +0.12 |
| `opera_house` | 0.63 | 0.74 | +0.11 |

**13 of 50 points are actually worse at the weekend.** Central
Mumbai's shopping and leisure traffic outweighs the weekday commute on those
roads — a genuine finding, and the opposite of the usual assumption.

### The single worst hour of the week

| day | hour | mean ratio |
|---|---|---|
| Tuesday | 19:00 | 0.701 |
| Friday | 19:00 | 0.707 |
| Monday | 19:00 | 0.720 |
| Wednesday | 18:00 | 0.720 |
| Tuesday | 18:00 | 0.721 |

Every one of the ten worst hours falls between 18:00 and 19:00. **Tuesday
evening is the worst hour in Mumbai's week.**

### Which points jam together

Correlation of congestion between every pair of points. This shows
**association, not causation** — with 30-minute sampling it cannot say which
jam came first, which is the analysis the project never got the data density
to complete.

| correlation | point A | point B |
|---|---|---|
| **+0.61** | `dadar_chowpatty` | `sk_bole_road_dadar` |
| **+0.39** | `sk_bole_road_dadar` | `weh_kherwadi` |
| **+0.30** | `opera_house` | `sk_bole_road_dadar` |
| **+0.29** | `eeh_vikhroli` | `opera_house` |
| **+0.29** | `eeh_vikhroli` | `sk_bole_road_dadar` |
| **+0.29** | `dadar_chowpatty` | `eeh_teen_hath` |

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
```

Background and constraints are in [FINDINGS.md](FINDINGS.md); the build plan
is in [PLAN.md](PLAN.md).
