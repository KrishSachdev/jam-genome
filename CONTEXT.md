# Context — how this project came to be

Written 2026-07-10, carried over from a Claude Code session that was otherwise about Krish's portfolio website. This file exists so future sessions (or future Krish) have the background without that chat.

## Who's building this

Krish Sachdev — 5th year (of 6) B.Tech Integrated Data Science, MPSTME NMIMS Mumbai. Python/TensorFlow/LangChain, one published paper (Enhanced LSTM Models for Short-Horizon Forecasting, Lex Localis 2025 — https://lex-localis.org/index.php/LexLocalis/article/view/801693), currently AI/ML intern at Maexadata Solutions (May 2026–ongoing, JD-CV matching). Portfolio site: `C:\Users\Krish\SynologyDrive\Personal Projects\new website` (this project should get a work-row there once live). GitHub: github.com/KrishSachdev.

## Origin of the idea

Krish wanted a portfolio project and hates Mumbai traffic. Research request: "check web, check research papers, check github — something new."

Ideas researched and their verdicts (July 2026 web research):

| Idea | Verdict |
|------|---------|
| Rain tax (monsoon × travel time) | Open gap, but Krish declined — "not inclined to the rain factor". Fallback option. |
| **Jam genome (congestion propagation / bottleneck ranking)** | **CHOSEN.** Methods exist in papers; zero Mumbai application; no open live implementation anywhere. |
| Event shockwaves (cricket/concerts/Ganpati) | Open for Mumbai; generic papers exist. Runner-up — planned as a stretch overlay on the jam genome. |
| Megaproject audit (Atal Setu, Coastal Road before/after) | Only RTI journalism exists, but historical baselines are paywalled; prospective-only. Parked. |
| Google Maps ETA audit for Mumbai | Partial prior work in Europe; medium novelty. Parked. |
| Pothole detection | Saturated in India (PotSense etc.). Rejected. |
| RL traffic signals (SUMO) | Extremely saturated; Bengaluru already done. Rejected. |

## Key research references

Methods to adapt for Phase 3 (propagation mining):
- Congestion Propagation Based Bottleneck Identification in Urban Road Networks — IEEE, 2020: https://ieeexplore.ieee.org/document/9043588/ (congestion propagation graphs, Markov-style transfer probabilities — closest template)
- Identifying Traffic Bottleneck in Urban Road Networks via Causal Inference: https://www.researchgate.net/publication/349134779
- Urban road network congestion bottlenecks identification and diffusion analysis (2026, GT-Eclat + Congestion Radiation Index): https://www.tandfonline.com/doi/abs/10.1080/03081060.2026.2636041
- Turn-level bottleneck identification from trajectories: https://www.sciencedirect.com/science/article/abs/pii/S0968090X22001450
- Survey of the broader field: https://doi.org/10.3390/vehicles7040142

Data sources:
- TomTom Traffic API — Flow Segment Data endpoint; free tier 2,500 req/day (verified via https://developer.tomtom.com/pricing, Jul 2026). QPS limit ~5. 429 on overage.
- Uber Movement is DEAD (shut 2023) — why no open Mumbai travel-time data exists; the dataset this project collects has standalone value.
- IIT-B mumbaiflood.in — live rain gauges + water levels, if rain is ever logged as a confounder control (optional; rain is explicitly NOT the project focus).
- TomTom Mumbai congestion ranking (for framing/intro): https://www.tomtom.com/traffic-index/city/mumbai/

Existing Mumbai traffic GitHub work (to differentiate from, all toy-scale):
- https://github.com/VedantBandre/Traffic-Flow-Predictor-Project (37 streets near one Wadala college)
- Uber-Movement-based analyses (unreproducible since dataset shutdown)

## Decisions already made

1. Project = jam genome; rain angle declined but a cheap optional rain log is allowed as a confounder control (PLAN.md Phase 1).
2. Collector-first strategy: data can't be collected retroactively; monsoon + Ganesh Chaturthi (Sept 2026) season is the most interesting window and it is NOW.
3. Everything lives in this folder; repo name suggestion: `jam-genome`, public from day 1.
4. Headline output framing agreed in chat: "the N road segments that poison Mumbai."
