# Citywide segment sweep

## Why this exists

TomTom's Flow Segment Data API returns a reading for a whole **road segment**,
not for the coordinate you asked about. Segment length is therefore the real
resolution limit of this project — a point dropped on a 20 km segment reports
the average of an entire highway, and can never show a junction jam.

That is why `weh_kalanagar` logs almost no congested slots despite being one of
Mumbai's worst chokepoints: the probe lands on a long mainline segment.

This sweep enumerates every distinct TomTom segment across Greater Mumbai
(Colaba → Dahisar) on a 260 m grid, and classifies each by length:

| length | verdict |
|---|---|
| ≤ 3 km | **usable** — can measure a single junction |
| 3–10 km | coarse |
| > 10 km | unusable blob |

The output is the shortlist of segments worth monitoring, which should drive
the next revision of `corridors.csv`.

## Scripts

| file | what it does |
|---|---|
| `sweep.py` | the citywide sweep. Budget-aware, resumable. **This is the daily driver.** |
| `build_sweep_map.py` | renders `sweep_state.json` → `sweep_map.html` (progress map) |
| `gridscan.py` | the original 100-probe Kalanagar resolution study → `segments.json` |
| `build_map.py` | renders `segments.json` → `segment_map.html` (the study map) |
| `scan.py` | WEH transect + Kalanagar micro-grid; how segment boundaries were first found |

Run a sweep batch (any time after 05:30 IST, when the UTC budget day rolls):

```bash
python sweep/sweep.py --plan     # show allowance, make no API calls
python sweep/sweep.py            # run the batch
```

## Budget safety

The collector always has priority — its data is irreplaceable, this sweep is
not. Every run recomputes its allowance live:

```
2,500 (TomTom daily ceiling)
  − collector requests already written today (read from GitHub)
  − sweep requests already spent today
  − 36 × collector runs still to come before 00:00 UTC
  − 100 safety margin
  = this run's allowance
```

## Status as of 2026-08-07

**The sweep state was lost.** `sweep_state.json` lived only in a Claude
session scratchpad, which Windows purged. Last known progress (31 Jul 2026):

- 1,273 of 6,327 grid cells probed (20.1%)
- 220 distinct segments found, 176 usable (≤ 3 km)
- ~1,273 API requests spent

Unless that file is recovered, `sweep.py` restarts from cell 0. Nothing is
permanently damaged — it costs roughly two more budget-days to catch up.

**Commit `sweep_state.json` to this repo after every run.** That is the whole
reason the previous state was lost, and it is the one habit that prevents it
happening again. It grows to ~3 MB; if that becomes a problem, split the
segment geometry into a separate file written once at the end, or gzip it.

## Known gaps in these recovered copies

`build_sweep_map.py` is the **day-1** version. Three later improvements were
made in the original session and are not in this copy:

1. **geometry simplification** (25 m tolerance) — halved the payload from
   22,210 to 10,891 vertices with no visible change at map scale. Without it
   the page passes 1 MB around day 6.
2. **self-updating copy** — headline, distance, day count and progress bar
   should read from the sweep state; this copy still hardcodes
   `537 probes` and `day 1 of ~10`.
3. minor: `el.style.stroke` / `el.style.strokeWidth` instead of `setAttribute`
   (already applied here).

One fix **is** applied here: in the original, a failed probe was still marked
done, so network errors punched permanent invisible holes in the grid. In this
copy a cell is only recorded when the probe actually succeeds.
