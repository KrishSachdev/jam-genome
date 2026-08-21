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

**Filter before selecting points.** "≤ 3 km" alone is not enough — the raw
counts include degenerate segments. Final tally of all 870:

| filter | count |
|---|---|
| freeflow = 0 km/h | 1 — `speed_ratio` would divide by zero |
| under 100 m | 13 — junction stubs, too small to monitor |
| over 3 km | 164 — too coarse |
| **clean candidates** (0.1–3 km, freeflow ≥ 10) | **692** |

By road class: FRC4 488, FRC2 82, FRC1 50, FRC3 31, FRC6 18, FRC7 16, FRC5 7.
That is ~19 usable candidates for every one of the current 36 monitoring
points — ample room to re-site the 17 points that record no congestion.

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

## Status

**COMPLETE — 2026-08-11.** All 6,327 land cells probed, 870 distinct segments found.

| date | probed | % | segments | usable ≤3 km |
|---|---|---|---|---|
| 2026-07-27 | 1,173 | 18.5% | 198 | 156 |
| 2026-08-09 | 2,169 | 34.3% | 383 | 292 |
| 2026-08-10 | 4,567 | 72.2% | 671 | 533 |
| **2026-08-11** | **6,327** | **100%** | **870** | **706** |

Days 2–4 ran in `--solo` mode with the collector deliberately paused
(2026-08-09 → 2026-08-11), which is why they reach ~2,400/day instead of ~670.
**The collector must be re-enabled once a solo sweep finishes.**

**Commit `sweep_state.json` after every run.** On 2026-08-07 the original
state was lost because it lived only in a Claude session scratchpad, which
Windows purged (~1,273 probes). It was recovered from the published map
artifact via `recover_from_map.py` — that worked only because the map embeds
the full payload. Committing the state is the habit that makes recovery
unnecessary. It reaches a few MB by the end; if that becomes a problem, split
the segment geometry into a separate file or gzip it.

## History / fixes applied

- **failed probes are no longer marked done.** In the original, a network
  outage still advanced the cursor, punching permanent invisible holes in the
  grid. A cell is now recorded only when the probe succeeds, so failures are
  retried on the next run.
- **geometry simplification** (Ramer–Douglas–Peucker, 25 m) — 28,017 → 2,181
  vertices, verified max deviation 24.90 m, i.e. invisible at map scale.
  Without it the page would pass 1 MB well before the sweep completes.
- **all page copy derives from the state file** — headline, frontier distance,
  probe count, progress bar and days-remaining. Nothing goes stale between
  runs.
