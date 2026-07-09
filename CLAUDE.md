# Jam Genome

Mumbai traffic congestion-propagation project: collect TomTom segment speeds across ~50 Mumbai corridor points, mine which jams cause which, rank the chokepoints that radiate the most network damage, publish an open dashboard.

**Start every session by reading `PLAN.md` (the build plan and current phase checklist) and `CONTEXT.md` (research background, references, decisions already made).** Update PLAN.md checkboxes as work lands.

Conventions:
- Python for collector + analysis; keep the collector dependency-light (requests + stdlib) since it runs on GitHub Actions cron.
- Data layout: `data/raw/YYYY-MM-DD.jsonl` (one line per point per poll), `corridors.csv` and the adjacency table at repo root.
- TomTom API key is a secret — env var / GitHub secret, never committed. Daily budget ≤ 2,400 requests (free tier 2,500).
- Owner: Krish Sachdev (krishsachdev18@gmail.com, github.com/KrishSachdev). His portfolio site lives at `..\new website` — this project gets linked there once the dashboard is live.
