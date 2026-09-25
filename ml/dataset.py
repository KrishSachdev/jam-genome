#!/usr/bin/env python3
"""Turn the collected traffic series into supervised forecasting data.

Task: given a point's recent history, predict its speed ratio H steps ahead
(1 step = 30 minutes).

Two things matter more here than model choice:

* **Temporal split.** Train on the earliest days, test on the latest. A random
  split leaks the future into training and inflates every score.
* **Honest gap handling.** Collection paused 10-21 Aug and died on 8 Sept, so
  the series is not continuous. A sample is only built when its whole input
  window and its target are inside one unbroken run of 30-minute slots.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from episodes import load_raw          # noqa: E402

SPLIT_ERA = pd.Timestamp("2026-08-20").date()
STEP = pd.Timedelta(minutes=30)
LOOKBACK = 6          # 3 hours of history
TEST_FRAC = 0.2


@dataclass
class Split:
    Xtr: np.ndarray
    ytr: np.ndarray
    Xte: np.ndarray
    yte: np.ndarray
    meta_te: pd.DataFrame        # point_id / slot for every test row
    feature_names: list


def wide_matrix(era="B"):
    """timesteps x points matrix of speed ratio, on a regular 30-min index."""
    df = load_raw()
    d = df["slot_ist"].dt.date
    df = df[d > SPLIT_ERA] if era == "B" else df[d <= SPLIT_ERA]
    w = df.pivot_table(index="slot", columns="point_id", values="speed_ratio")
    w = w.sort_index()
    full = pd.date_range(w.index.min(), w.index.max(), freq="30min", tz=w.index.tz)
    return w.reindex(full)


def _runs(index_present):
    """Contiguous stretches of observed slots, as (start, end) positions."""
    runs, start = [], None
    for i, ok in enumerate(index_present):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(index_present)))
    return runs


def build(era="B", horizon=1, lookback=LOOKBACK, neighbours=True):
    """Feature matrix for all points pooled into one global model."""
    w = wide_matrix(era)
    idx = w.index
    hours = idx.hour.to_numpy()
    dows = idx.dayofweek.to_numpy()

    # historical profile: mean ratio per point x hour x weekday-flag, computed
    # on the TRAIN portion only and then applied everywhere, so the test rows
    # never see their own statistics.
    n_t = len(idx)
    cut = int(n_t * (1 - TEST_FRAC))

    long = w.iloc[:cut].stack().rename("r").reset_index()
    long.columns = ["slot", "point_id", "r"]
    long["hour"] = long["slot"].dt.hour
    long["wd"] = long["slot"].dt.dayofweek < 5
    profile = long.groupby(["point_id", "hour", "wd"])["r"].mean()
    global_prof = long.groupby(["hour", "wd"])["r"].mean()

    nb = _neighbour_map(list(w.columns)) if neighbours else {}

    rows, ys, meta = [], [], []
    for pid in w.columns:
        s = w[pid].to_numpy(dtype=float)
        present = ~np.isnan(s)
        for a, b in _runs(present):
            for t in range(a + lookback - 1, b - horizon):
                win = s[t - lookback + 1: t + 1]
                target = s[t + horizon]
                if np.isnan(win).any() or np.isnan(target):
                    continue
                h, dw = hours[t], dows[t]
                wd = dw < 5
                prof = profile.get((pid, hours[t + horizon], wd),
                                   global_prof.get((hours[t + horizon], wd), np.nan))
                if np.isnan(prof):
                    prof = float(np.nanmean(s[:cut])) if cut else 0.9
                feat = list(win) + [
                    float(np.mean(win)), float(np.min(win)), win[-1] - win[0],
                    np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24),
                    1.0 if wd else 0.0,
                    prof,
                ]
                if neighbours:
                    ns = nb.get(pid, [])
                    vals = [w[o].to_numpy()[t] for o in ns if o in w.columns]
                    vals = [v for v in vals if not np.isnan(v)]
                    feat.append(float(np.mean(vals)) if vals else float(win[-1]))
                rows.append(feat)
                ys.append(target)
                meta.append((pid, idx[t], idx[t + horizon], t))

    X = np.asarray(rows, dtype=np.float32)
    y = np.asarray(ys, dtype=np.float32)
    m = pd.DataFrame(meta, columns=["point_id", "t_slot", "target_slot", "t_pos"])

    train_mask = (m["t_pos"] < cut).to_numpy()
    names = ([f"lag{lookback-1-i}" for i in range(lookback)] +
             ["win_mean", "win_min", "win_trend", "hour_sin", "hour_cos",
              "is_weekday", "hist_profile"] +
             (["neighbour_mean"] if neighbours else []))

    return Split(X[train_mask], y[train_mask], X[~train_mask], y[~train_mask],
                 m[~train_mask].reset_index(drop=True), names)


def _neighbour_map(points):
    """point -> neighbours, from adjacency.csv (pairs within 3 km)."""
    import csv
    p = Path(__file__).resolve().parents[1] / "adjacency.csv"
    nb = {}
    if not p.exists():
        return nb
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            a, b = r.get("from_id"), r.get("to_id")
            if a in points and b in points:
                nb.setdefault(a, []).append(b)
                nb.setdefault(b, []).append(a)
    return nb


def sequences(era="B", horizon=1, lookback=LOOKBACK):
    """Same split, shaped (samples, lookback, features) for the LSTM."""
    sp = build(era, horizon, lookback, neighbours=False)
    n_lag = lookback

    def reshape(X):
        lags = X[:, :n_lag]                       # the raw window
        extra = X[:, n_lag:]                      # calendar / profile features
        seq = np.repeat(extra[:, None, :], n_lag, axis=1)
        return np.concatenate([lags[:, :, None], seq], axis=2).astype(np.float32)

    return (reshape(sp.Xtr), sp.ytr, reshape(sp.Xte), sp.yte, sp.meta_te)


if __name__ == "__main__":
    for h in (1, 2, 3):
        sp = build(horizon=h)
        print(f"horizon {h} ({h*30} min): train {sp.Xtr.shape}  test {sp.Xte.shape}  "
              f"| {len(sp.feature_names)} features")
    print("\nfeatures:", ", ".join(build(horizon=1).feature_names))
