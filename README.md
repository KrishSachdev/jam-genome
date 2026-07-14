# Jam Genome

**Which traffic jams cause which?** This project collects live segment-level
speeds across ~36 (growing to ~50) points on Mumbai's road network every 30
minutes, mines how congestion propagates between them, and ranks the
chokepoints that radiate the most network damage — *the road segments that
poison Mumbai*.

Congestion-propagation methods exist academically but have never been applied
to Mumbai, and no city anywhere has an open live implementation. Mumbai's
open traffic data died with Uber Movement (2023), so the collected dataset is
itself a contribution. Full background in [CONTEXT.md](CONTEXT.md), build plan
in [PLAN.md](PLAN.md).

## Repo layout

```
corridors.csv            monitoring points (id, name, lat/lon, corridor)
adjacency.csv            hand-built neighbour graph between points
collector/
  poll.py                polls TomTom Flow Segment Data -> data/raw/*.jsonl
  validate_points.py     one-shot check that every point snapped to the right road
  weather.py             hourly rain log (Open-Meteo) -> data/weather/*.jsonl
analysis/
  data_quality.py        weekly missing-polls / dead-point report
data/raw/                YYYY-MM-DD.jsonl, one line per point per poll
data/weather/            YYYY-MM-DD.jsonl, one line per poll
.github/workflows/
  collect.yml            cron every 30 min, commits data back to the repo
```

## Data schema (`data/raw/*.jsonl`)

```json
{"ts_utc": "2026-07-12T08:07:31+00:00", "point_id": "weh_kalanagar",
 "current_speed": 23, "freeflow_speed": 58, "current_tt": 210,
 "freeflow_tt": 83, "confidence": 0.95, "closure": false, "frc": "FRC1"}
```

Speeds are km/h, travel times are seconds (TomTom's segment, not a fixed
length). Failed polls keep `ts_utc`/`point_id` and carry an `error` field.

**Data caveats:** `tulsi_pipe` rows from 2026-07-09 to 2026-07-13 should be
ignored — the whole Tulsi Pipe Rd corridor is flagged `closure: true` in
TomTom (bridge works), so its readings are meaningless. Replaced by
`annie_besant_worli` on 2026-07-13.

## Going live (weekend-1 checklist)

1. **TomTom API key** — free account at
   [developer.tomtom.com](https://developer.tomtom.com); free tier is 2,500
   requests/day. The workflow *attempts* a run every 15 minutes because
   GitHub's shared cron skips most slots (observed ~25% fire rate,
   2026-07-11); `poll.py` hard-caps at **2,376 requests/day** (66 runs × 36
   points) so over-firing can never exceed the quota.
2. **Validate the points** — all 36 were API-validated on 2026-07-10 with
   zero flags (`validation_report.csv` is the record). Re-run whenever you
   edit or add points:
   ```
   set TOMTOM_API_KEY=...          (PowerShell: $env:TOMTOM_API_KEY="...")
   python collector/validate_points.py
   ```
   Note: the API snaps to the *nearest* segment, so on divided highways the
   coordinate decides which carriageway you're measuring; be deliberate.
3. **Test one poll locally:** `python collector/poll.py` → check
   `data/raw/<today>.jsonl`.
4. **Create the GitHub repo** (`jam-genome`, public) and push this folder.
5. **Add the repo secret** `TOMTOM_API_KEY` (Settings → Secrets → Actions).
   The workflow starts collecting on the next half-hour; kick a manual run
   from the Actions tab to confirm.
6. **Week 1–2:** run `python analysis/data_quality.py` every few days and fix
   bad points early — every lost week of monsoon-season data is irreplaceable.

## Adjacency semantics

`adjacency.csv` lists undirected neighbour *pairs* (`corridor` = consecutive
points on the same road, `connector` = linked across a junction). Phase 3
tests propagation in both directions per pair — congestion usually spills
*backwards* against travel direction, so don't read `from_id → to_id` as a
causal claim; it's just geographic ordering.

## Licence & data-publication caveat

Code is MIT. **Before publishing collected raw data publicly, check TomTom's
licence terms on storing/redistributing API responses** (PLAN.md, Risks) —
derived analytics and the dashboard are almost certainly fine; raw-response
redistribution may not be. Plan B is publishing derived per-hour aggregates
only.
