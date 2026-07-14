# Jam Genome — Project Plan

**One-liner:** Collect live segment-level speed data across Mumbai's road network for weeks, mine which traffic jams *cause* which, and publish a ranked list of the chokepoints that radiate the most network damage — "the road segments that poison Mumbai."

**Why it's novel (verified July 2026):** Congestion-propagation and bottleneck-identification methods exist academically (Wuhan case studies, IEEE 2020, causal-inference variants — see CONTEXT.md) but have never been applied to Mumbai, and no city anywhere has an open, live implementation. Mumbai's open traffic data is dead (Uber Movement shut down 2023), so the collected dataset is itself a contribution.

**End deliverables:**
1. An open Mumbai corridor-speed dataset (collected via this project)
2. The propagation analysis + chokepoint ranking
3. An interactive public dashboard (GitHub Pages) — map, rankings, jam-spread animation
4. Optional: a short paper ("Congestion propagation and bottleneck ranking in Mumbai from open probe data") — Krish already has one publication (LSTM forecasting, Lex Localis 2025), so a second is a realistic goal

---

## Phase 0 — Setup (weekend 1)

- [ ] TomTom developer account → API key. Free tier: **2,500 requests/day** (verified Jul 2026). Endpoint: **Traffic API → Flow Segment Data** (`/traffic/services/4/flowSegmentData/...`) — takes a lat/lon, returns nearest segment's `currentSpeed`, `freeFlowSpeed`, `currentTravelTime`, `freeFlowTravelTime`, `confidence`, `roadClosure`.
- [x] **Budget math:** 50 monitoring points × 48 polls/day (every 30 min) = 2,400 req/day → fits free tier with headroom. Start with ~40 points, expand carefully. *(36 starter points defined = 1,728/day.)*
- [x] Define `corridors.csv`: `point_id, name, lat, lon, corridor, direction, notes`. *(Drafted + API-validated 2026-07-10 — 36 points, 0 flags from `collector/validate_points.py`; all expressway points confirmed on FRC1/FRC2 mainline.)* Starter set (expand to ~50 by driving the map):
  - **WEH (Western Express Hwy):** Dahisar toll, Borivali (National Park), Malad (Mith Chowky approach), Goregaon (Oberoi), JVLR junction, Airport/Sahar elevated approach, Vile Parle, Kherwadi junction, Kalanagar junction, Mahim end
  - **EEH (Eastern Express Hwy):** Thane (Teen Hath Naka), Mulund check naka, Bhandup, Vikhroli, Ghatkopar (Amar Mahal junction), Chembur, Sion
  - **Arterials:** LBS Marg (Mulund / Bhandup / Kurla), SV Road (Andheri / Bandra), Linking Road, JVLR (both ends), SCLR, Sion–Panvel Hwy, Ghodbunder Rd, Tulsi Pipe Rd / Senapati Bapat Marg
  - **Known chokepoints (must-have):** Kalanagar, Amar Mahal, Sion Circle, Times of India junction, Kurla (LBS×CST Rd), Sakinaka junction, Milan subway, Hindmata, King's Circle, Andheri subway
- [x] *(Drafted 2026-07-10 — `adjacency.csv`, ~46 edges; refine while validating points.)* Build a **manual adjacency table** alongside: for each point, which points are upstream/downstream neighbours (same corridor) and which connect across junctions. ~50 points → very doable by hand; this is the graph skeleton for Phase 3. Document assumptions.
- [ ] GitHub repo `jam-genome` (public from day 1).

## Phase 1 — Collector (goes live weekend 1, runs for the whole project)

- Python script `collector/poll.py`: read `corridors.csv`, hit Flow Segment Data per point, append one JSONL line per point: `{ts_utc, point_id, current_speed, freeflow_speed, current_tt, freeflow_tt, confidence, closure}`. Retries with backoff; failures logged, never crash the run.
- Output: `data/raw/YYYY-MM-DD.jsonl` (~0.5 MB/day raw → trivial; gzip monthly).
- **Scheduling: GitHub Actions cron** committing data back to the repo — free, always-on, transparent, survives the laptop being off. (Reality check 2026-07-11: Actions skipped ~75% of slots on day 1 — far worse than "a few minutes of jitter". Mitigated with 15-min cron attempts + a hard daily budget guard in poll.py. If effective cadence stays coarser than ~30 min, switch to an external pinger — e.g. cron-job.org POSTing a `workflow_dispatch` to the GitHub API with a fine-grained PAT — which makes timing deterministic. Fallback: Windows Task Scheduler on the PC.)
- API key via repo secret. Never commit the key.
- Weekly data-quality notebook: missing polls per point, confidence distribution, dead/misplaced points (a point snapping to the wrong road shows as flat freeflow forever — fix coords early).
- **Every week of monsoon+festival season data is irreplaceable — collector goes live before any analysis is written.**
- Optional (cheap, keeps options open): also log hourly rainfall for Mumbai from a free weather API into `data/weather/`. Not the project focus (rain angle explicitly declined), but one extra column preserves the ability to control for rain as a confounder in Phase 3 — a reviewer WILL ask.

## Phase 2 — Exploratory analysis (after ~1–2 weeks of data)

- Congestion metric: `speed_ratio = current/freeflow`; congestion episode = ratio below threshold (start 0.5) for ≥2 consecutive polls. Run sensitivity analysis on the threshold — don't hard-code one number.
- Deliverables: corridor heatmaps (hour-of-day × point), weekday/weekend profiles, "congestion-hours per day" league table, episode duration distributions.
- *(Tooling built 2026-07-14: `analysis/episodes.py` (episode extraction + threshold sensitivity, reused by Phase 3) and `analysis/eda.py` (league table CSV, heatmap, weekday/weekend profiles). First 4-day read: EEH Vikhroli is the early league leader with a recurring weekday-evening jam; conclusions still need the full 2 weeks.)*
- This alone is publishable content: "Mumbai's slowest corridors, measured every 30 minutes for a month."

## Phase 3 — Propagation mining (the core, weeks 5–8)

Methods, simplest-first (references in CONTEXT.md):
1. **Episode extraction:** onset/offset timestamps per point.
2. **Pairwise propagation evidence:** for each adjacency-table edge A→B, compute P(B onset within Δt after A onset) vs B's base onset rate — a lift/conditional-probability score. Sweep Δt (15–90 min). This is interpretable and defensible; it's the Markov-style approach from the IEEE 2020 paper.
3. **Propagation graph:** directed edges weighted by lift × frequency; prune weak edges.
4. **Chokepoint ranking:** score each node by radiated damage — outbreak frequency × downstream congestion-hours attributable to it (weighted out-reach / Katz-style centrality on the propagation graph). **This ranking is the headline result.**
5. Stretch (only if 2–4 land): Granger causality or transfer entropy per edge as robustness check; control for time-of-day and rain (both cause spurious correlation — everything jams at 6 pm; dedicate real care to this confounder).
6. **Validation:** famous chokepoints (Kalanagar, Amar Mahal, Sakinaka) should surface near the top — if they don't, debug before believing anything; deep-dive 3–4 specific evenings as case studies with timelines.

## Phase 4 — Dashboard + writeup (weeks 8–10)

- Static site on GitHub Pages (fits existing skills: vanilla HTML/CSS/JS): MapLibre/Leaflet map of points coloured by chokepoint score, ranking table, per-point profile popovers, and one **animated replay of a real jam propagating** (the money visual).
- Blog-style writeup of method + findings on the same page.
- Add to portfolio site (`Personal Projects\new website`, index.html work list) — row exists as "in development" first, arrow + link when the dashboard ships.
- Optional paper draft after dashboard: methods are standard, the application + open dataset are the contribution.

## Phase 5 — Stretch ideas (post-launch)

- **Event shockwaves overlay:** Ganesh Chaturthi processions (Sept 2026) and Wankhede match days observed through the propagation graph — was the runner-up project idea and composes perfectly with this one.
- Nowcasting: predict downstream congestion 30–60 min ahead from upstream state (gradient-boosting baseline → temporal GNN if justified).
- Expand point set / second city comparison.

## Risks & honest notes

- **TomTom ToS:** before publishing the raw dataset publicly, check licence terms on storing/redistributing API responses. Derived analytics and the dashboard are almost certainly fine; raw-data redistribution may not be. Check early, not at launch. (Plan B: publish derived per-hour aggregates only.)
- Free-tier terms can change; keep the collector's daily budget at ~2,400 with headroom, monitor for HTTP 429.
- Point placement errors are the #1 silent data killer — validate every point's returned `freeFlowSpeed`/road name in week 1.
- Time-of-day confounding is the #1 analysis killer — everything correlates at rush hour. The lift-vs-baseline design in Phase 3.2 exists precisely for this; don't skip it.
- Timeline assumes the Maexadata internship continues — phases 2–4 are deliberately notebook-sized chunks.

## Timeline snapshot

| When | What |
|------|------|
| Weekend 1 | TomTom key, corridors.csv, collector live on GitHub Actions |
| Weeks 2–5 | Passive collection; EDA notebook; fix bad points |
| Weeks 5–8 | Propagation mining + ranking |
| Weeks 8–10 | Dashboard, writeup, portfolio link |
| Ongoing | Collector keeps running; stretch ideas |
