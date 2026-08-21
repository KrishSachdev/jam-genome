# Findings and constraints

Hard-won facts about this project's data. **Read this before doing any
analysis or changing the point set.** Several of these were expensive to
discover and are not obvious from the code; two of them invalidate analyses
that look perfectly reasonable.

Last updated: 2026-08-11.

---

## 1. TomTom returns whole-segment readings — this is the central constraint

The Flow Segment Data API does not give you the speed *at your coordinate*.
It snaps to the nearest road **segment** and returns that segment's average.
**Segment length is therefore the real resolution limit of this project.**

Verified 2026-07-26 by probing a 2.4 km box around Kalanagar on a 260 m grid:
100 probes returned many distinct segments, several over 10 km long.

### The expressway mainlines are enormous single segments

Measured 2026-08-11 (`freeFlowSpeed x freeFlowTravelTime / 3600`):

| Corridor | Mainline segment length |
|---|---|
| WEH (Bandra → Dahisar area) | **19.7 km**, 19.0 km, 16.2 km, 15.4 km |
| EEH (Sion → Mulund area) | **13.3 km**, 12.9 km |

**Zoom does not help.** The URL contains `/absolute/{zoom}/json` and TomTom
documents zoom 0–22. Tested zoom 10, 12, 14, 16, 18 at four points: the
returned segment was byte-identical every time. There is no finer view of the
mainline available on this API.

### Consequence: duplicate points

Points sitting on the same segment return the **same number**, so they are
duplicates paying twice. Confirmed in the collected data (identical
`current_speed` in >99% of slots):

- `weh_borivali` = `weh_goregaon` = `weh_malad`
- `weh_jvlr` = `weh_vile_parle`
- `milan_subway` = `sv_bandra`

4 of 36 points were redundant — 192 wasted requests/day.

### But do NOT conclude "long segments show nothing"

`eeh_vikhroli` sits on a 12.9 km segment and recorded **111 congested slots**
in 29 days. A long segment shows congestion fine when the whole stretch
crawls. What it cannot do is tell you **which junction** caused it — and that
is exactly what propagation mining needs. The correct statement is:

> Long segments destroy *spatial* resolution, not congestion sensitivity.

### Design rule that follows

**One monitoring point per distinct TomTom segment.** Extra points on the same
segment are free duplicates. Corollary: WEH can support ~3 points total, not
10; EEH ~4. Fine-grained propagation is only observable on the **arterial and
junction network**, where short segments exist.

---

## 2. 17 of 36 points recorded zero congestion in 29 days

Measured over 2026-07-10 → 08-07 at threshold `speed_ratio < 0.5`:

Zero congested slots: `weh_kalanagar`, `eeh_amar_mahal`, `milan_subway`,
`kings_circle`, `toi_junction`, `sv_bandra`, `weh_mahim`, `jvlr_eeh`,
`sion_panvel`, `weh_vile_parle`, `weh_jvlr`, `eeh_mulund`, `sclr_kurla`,
`eeh_chembur`, `lbs_mulund`, `weh_dahisar`, `ghodbunder`.

These are famous chokepoints. **They are not uncongested — they are on
segments too long to localise a jam.** PLAN.md Phase 3 says exactly these
should top the chokepoint ranking, so the ranking is not meaningful until the
point set is fixed.

Points that DO work (and should not be moved — they have a real record):
`weh_kherwadi` 156 slots, `eeh_sion` 124, `eeh_vikhroli` 111, `eeh_teen_hath`
71, `jvlr_powai` 31, `sion_circle` 30, `eeh_bhandup` 16, `lbs_kurla` 14,
`linking_road` 13.

---

## 3. Data files are bucketed by UTC date — always group by IST

`poll.py` uses `datetime.now(timezone.utc)`, so `data/raw/YYYY-MM-DD.jsonl`
holds **05:30 IST that day → 05:30 IST the next day**. Every Mumbai night
(00:00–05:30 IST) lands in the *previous* day's file.

**Never group by filename or raw UTC date.** Convert `ts_utc` to
`Asia/Kolkata` and group on that, or an overnight jam gets split across two
files and double-counted or truncated. `analysis/episodes.py` and
`analysis/eda.py` already do this correctly (`slot_ist`). The collector stays
on UTC deliberately — nothing to fix there.

---

## 4. The weather log is broken — do not use it

`data/weather/*.jsonl` (from `collector/weather.py`) is **unreliable**.
Verified 2026-07-27 against Open-Meteo's own hourly series: it missed half of
the wettest day (23 Jul: 67.7 mm actual vs 32 mm logged) and inflated a nearly
dry day fourfold (25 Jul: 5.3 mm actual vs 24 mm logged).

**Cause:** it reads Open-Meteo's `current` block, whose `interval` is **900 s
— rain in the last 15 minutes, not the hour**. Polling every 30 minutes
observes only ~50% of elapsed time, and Mumbai monsoon rain arrives in bursts
that mostly land in the unobserved half.

**Fix:** rain does not need live collection — unlike traffic, weather is
permanently archived. Backfill any date range from
`https://archive-api.open-meteo.com/v1/archive?latitude=19.076&longitude=72.8777&hourly=rain&timezone=Asia/Kolkata`
(free, no key, ~5-day lag, ERA5). Caveat: ERA5 is a ~9 km grid and smooths
local extremes (it gave 626 mm for 1–9 Jul 2026 where the IMD Santacruz gauge
recorded 1,146 mm), so use it for relative wet/dry, not absolute mm.

**Withdrawn claim:** an earlier session concluded "rain has no measurable
effect on congestion once you control for hour of day." That was computed from
this broken series and is **unsupported**.

The TomTom traffic data itself was separately validated and IS reliable:
confidence mean 0.993, no frozen points, stable free-flow denominator,
textbook weekday/weekend rush-hour separation.

---

## 5. Dead and relocated points

- `tulsi_pipe` reported `closure: true` on **every poll** from 2026-07-09 to
  07-14 — the whole Tulsi Pipe Rd corridor is flagged closed in TomTom
  (bridge works). Its rows are junk. Replaced by `annie_besant_worli`.
- Points snapping to service lanes were corrected 2026-07-10 by probing rings
  around each coordinate; 17 of 36 originals were on the wrong road.

---

## 6. Congestion threshold: 0.50, chosen by sweep not assumption

`speed_ratio = current_speed / freeflow_speed`; an episode is ≥2 consecutive
30-min slots below threshold. Sensitivity over 29 days:

| threshold | episodes | points affected |
|---|---|---|
| 0.40 | 21 | 5 |
| 0.45 | 67 | 8 |
| **0.50** | **129** | **12** |
| 0.55 | 260 | 24 |
| 0.60 | 463 | 28 |
| 0.65 | 802 | 34 |
| 0.70 | 1,089 | 35 |

0.50 is selective enough to mean something and loose enough to have signal.
0.40 is too sparse; 0.65+ flags nearly every point. **Report the sweep, not
just the chosen number** — a reviewer will ask.

---

## 7. The citywide sweep (complete)

`sweep/` enumerates every distinct TomTom segment in Greater Mumbai on a 260 m
grid. **Completed 2026-08-11**: all 6,327 land cells probed, **870 segments**
found, **692 clean candidates**.

"Clean" means `0.1 km ≤ length ≤ 3 km AND freeflow ≥ 10 km/h`. Filtering on
length alone is not enough — the raw set contains 1 segment with freeflow
0 km/h (divides by zero in `speed_ratio`) and 13 under 100 m (junction stubs).

Resolution is uniform across the city (70–84% usable per zone); the northern
suburbs are marginally best, Bandra/BKC worst. An early reading that "South
Mumbai is uniquely rich" was a sampling artefact of having only swept the
south at the time.

**Commit `sweep/sweep_state.json` after every run.** The original state was
lost when a Claude scratchpad was purged, and was only recovered because the
published map artifact embedded the payload (`sweep/recover_from_map.py`).

---

## 8. Collection infrastructure

- Driven **only** by a cron-job.org job (`jam-genome collect`) firing
  `workflow_dispatch` at :12 and :42. GitHub's own `schedule:` cron was
  removed from `collect.yml` because it fired unreliably (~25% of slots) and
  its duplicate runs wasted budget. **That cron-job.org toggle is the single
  on/off switch for all collection.**
- Auth: a fine-grained GitHub PAT (expires **2027-06-11**) in the cron-job.org
  job's `Authorization: Bearer` header. When it expires, collection stops
  silently — cron-job.org emails on failure.
- `poll.py` guards: hard cap 2,376 lines/day, and a 22-minute spacing guard so
  near-duplicate runs become no-ops.
- A failed probe must **never** be marked done. The sweep originally had this
  bug: network errors advanced the cursor and punched permanent invisible
  holes in the grid. Fixed; verified on real failures 2026-08-10.
