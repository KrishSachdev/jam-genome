# Jam Genome

Mumbai traffic project: collect TomTom segment speeds across Mumbai every 30
minutes, measure how congestion behaves, and publish an open dataset plus a
dashboard. Two headline deliverables:

1. **Ganeshotsav 2026 natural experiment** (14–25 Sept) — how Mumbai's biggest
   festival deforms city traffic, measured against control roads.
2. **Congestion-propagation mining** — which jams cause which, and a ranking of
   the chokepoints that radiate the most network damage.

## Read these first, in this order

| file | what it holds |
|---|---|
| **[FINDINGS.md](FINDINGS.md)** | **Hard constraints and gotchas. Read before any analysis — two of them silently invalidate reasonable-looking work.** |
| [PLAN.md](PLAN.md) | Build plan, phase checklists, timeline, current status |
| [CONTEXT.md](CONTEXT.md) | Origin, research references, decisions already made |
| [sweep/README.md](sweep/README.md) | The citywide segment sweep and why it exists |

Update PLAN.md checkboxes as work lands, and add anything hard-won to
FINDINGS.md.

## The three things that trip people up

1. **TomTom returns whole-segment readings, not point readings.** Segment
   length is the resolution limit. The expressways are single 13–20 km
   segments, so every point on one returns the identical number. Design rule:
   **one point per distinct segment.** (FINDINGS §1)
2. **Data files are cut on the UTC date**, which flips at 05:30 IST. Always
   convert `ts_utc` to `Asia/Kolkata` and group on that — never on filename.
   (FINDINGS §3)
3. **`data/weather/` is broken** — wrong sampling window. Backfill rain from
   the Open-Meteo archive instead. (FINDINGS §4)

## Layout

```
corridors.csv          monitoring points (the live set)
adjacency.csv          hand-built neighbour graph, for propagation mining
collector/             poll.py (the 30-min collector), validate_points.py, weather.py
analysis/              episodes.py, eda.py, data_quality.py
sweep/                 citywide segment enumeration + point-selection tooling
data/raw/              YYYY-MM-DD.jsonl, one line per point per poll (UTC-dated)
.github/workflows/     collect.yml — runs on workflow_dispatch only
```

## Conventions

- Python. Keep the collector dependency-light (requests + stdlib) — it runs on
  GitHub Actions.
- TomTom key is a secret: `.env` locally (gitignored), `TOMTOM_API_KEY` as the
  repo secret. Daily budget ≤ 2,400 of the 2,500 free-tier requests.
- **Collection is switched on/off solely by the cron-job.org job
  `jam-genome collect`** — GitHub's own cron was removed. The PAT it uses
  expires 2027-06-11.
- Commit `sweep/sweep_state.json` after every sweep run; the original was lost
  once to a purged temp folder.
- Krish drives git himself — build the files, don't run commit/push unasked,
  and never add `Co-Authored-By` lines.
- Owner: Krish Sachdev (krishsachdev18@gmail.com, github.com/KrishSachdev).
  Portfolio site at `..\new website` gets a link once the dashboard ships.
