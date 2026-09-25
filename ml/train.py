#!/usr/bin/env python3
"""Train and honestly evaluate forecasters for Mumbai speed ratio.

Predicts a monitoring point's speed ratio 30 / 60 / 90 minutes ahead.

The point of this script is the comparison, not any single model. Three
baselines are included that a learned model has to actually beat:

  persistence        tomorrow looks like today -- the hardest baseline to beat
                     at short horizons in almost every traffic paper
  historical average that point, that hour, weekday vs weekend
  seasonal naive     the same clock time yesterday

against Ridge, XGBoost and an LSTM (the LSTM mirrors the approach in the
author's Lex Localis paper, applied to a new domain).

Everything uses one temporal split: earliest 80% of slots train, latest 20%
test. Metrics are MAE / RMSE / MAPE, matching the METR-LA and PEMS-BAY
literature, plus an F1 for the practical question "will this road be congested".

Usage:  python ml/train.py [--era B] [--epochs 40]
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from dataset import build, sequences

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ml" / "results"
THRESH = 0.5
HORIZONS = [1, 2, 3]


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    mae = float(np.mean(np.abs(y - p)))
    rmse = float(np.sqrt(np.mean((y - p) ** 2)))
    mape = float(np.mean(np.abs((y - p) / np.clip(y, 0.05, None))) * 100)
    # congestion detection: does the model call the jam?
    yt, pt = y < THRESH, p < THRESH
    tp = int((yt & pt).sum()); fp = int((~yt & pt).sum()); fn = int((yt & ~pt).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape,
            "congestion_F1": f1, "precision": prec, "recall": rec,
            "n_congested": int(yt.sum())}


def seasonal_naive(sp, horizon):
    """Value at the same clock time on the previous day, per point."""
    from dataset import wide_matrix
    w = wide_matrix("B")
    preds = []
    for r in sp.meta_te.itertuples():
        tgt = r.target_slot - pd.Timedelta(days=1)
        v = np.nan
        if tgt in w.index and r.point_id in w.columns:
            v = w.at[tgt, r.point_id]
        preds.append(v)
    preds = np.asarray(preds, float)
    # fall back to persistence where yesterday is missing
    fallback = sp.Xte[:, sp.feature_names.index("lag0")]
    return np.where(np.isnan(preds), fallback, preds)


def run_lstm(era, horizon, epochs, seed=0):
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    Xtr, ytr, Xte, yte, _ = sequences(era, horizon)
    mu, sd = Xtr.reshape(-1, Xtr.shape[2]).mean(0), Xtr.reshape(-1, Xtr.shape[2]).std(0) + 1e-6
    Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd

    n_val = int(len(Xtr) * 0.15)                      # validation = the tail of train
    Xv, yv, Xt, yt = Xtr[-n_val:], ytr[-n_val:], Xtr[:-n_val], ytr[:-n_val]

    class Net(nn.Module):
        def __init__(self, f):
            super().__init__()
            self.lstm = nn.LSTM(f, 48, batch_first=True)
            self.head = nn.Sequential(nn.Linear(48, 24), nn.ReLU(), nn.Linear(24, 1))

        def forward(self, x):
            o, _ = self.lstm(x)
            return self.head(o[:, -1]).squeeze(-1)

    dev = "cpu"
    net = Net(Xtr.shape[2]).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=2e-3)
    lossf = nn.L1Loss()
    Xt_t = torch.tensor(Xt); yt_t = torch.tensor(yt)
    Xv_t = torch.tensor(Xv); yv_t = torch.tensor(yv)
    Xe_t = torch.tensor(Xte)

    best, best_state, patience = 1e9, None, 0
    bs = 256
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xt_t))
        for i in range(0, len(perm), bs):
            j = perm[i:i + bs]
            opt.zero_grad()
            loss = lossf(net(Xt_t[j]), yt_t[j])
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vl = lossf(net(Xv_t), yv_t).item()
        if vl < best - 1e-5:
            best, best_state, patience = vl, {k: v.clone() for k, v in net.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 6:
                break
    if best_state:
        net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        pred = net(Xe_t).numpy()
    return pred, ep + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--era", default="B")
    ap.add_argument("--epochs", type=int, default=40)
    args = ap.parse_args()

    from sklearn.linear_model import Ridge
    from xgboost import XGBRegressor

    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = []

    for h in HORIZONS:
        sp = build(args.era, horizon=h)
        lag0 = sp.feature_names.index("lag0")
        prof = sp.feature_names.index("hist_profile")
        print(f"\n{'='*74}\nHORIZON {h}  ({h*30} minutes ahead)   "
              f"train {sp.Xtr.shape[0]:,}  test {sp.Xte.shape[0]:,}\n{'='*74}")

        preds = {
            "persistence": sp.Xte[:, lag0],
            "historical average": sp.Xte[:, prof],
            "seasonal naive": seasonal_naive(sp, h),
        }

        t0 = time.time()
        ridge = Ridge(alpha=1.0).fit(sp.Xtr, sp.ytr)
        preds["ridge"] = ridge.predict(sp.Xte)
        t_ridge = time.time() - t0

        t0 = time.time()
        xgb = XGBRegressor(n_estimators=400, max_depth=5, learning_rate=0.05,
                           subsample=0.9, colsample_bytree=0.9,
                           reg_lambda=1.0, n_jobs=4, random_state=0)
        xgb.fit(sp.Xtr, sp.ytr)
        preds["xgboost"] = xgb.predict(sp.Xte)
        t_xgb = time.time() - t0

        t0 = time.time()
        lstm_pred, eps = run_lstm(args.era, h, args.epochs)
        preds["lstm"] = lstm_pred
        t_lstm = time.time() - t0
        print(f"  (lstm stopped after {eps} epochs, {t_lstm:.0f}s; "
              f"ridge {t_ridge:.1f}s, xgboost {t_xgb:.0f}s)")

        print(f"\n  {'model':<20}{'MAE':>8}{'RMSE':>8}{'MAPE%':>8}{'F1':>7}"
              f"{'prec':>7}{'rec':>7}")
        base_mae = None
        for name, p in preds.items():
            m = metrics(sp.yte, p)
            if name == "persistence":
                base_mae = m["MAE"]
            gain = (base_mae - m["MAE"]) / base_mae * 100 if base_mae else 0
            m.update(model=name, horizon_min=h * 30,
                     vs_persistence_pct=round(gain, 1))
            all_rows.append(m)
            star = "  <-- best so far" if m["MAE"] == min(
                r["MAE"] for r in all_rows if r["horizon_min"] == h * 30) else ""
            print(f"  {name:<20}{m['MAE']:>8.4f}{m['RMSE']:>8.4f}{m['MAPE']:>8.2f}"
                  f"{m['congestion_F1']:>7.3f}{m['precision']:>7.3f}{m['recall']:>7.3f}{star}")

        # Overall MAE flatters everyone: 97% of targets are free-flowing, and
        # "1.00 stays 1.00 at 3am" is trivially predictable. The number that
        # matters is performance during rush hour and on already-slow roads.
        ist_hour = sp.meta_te["target_slot"].dt.tz_convert("Asia/Kolkata").dt.hour
        rush = ((ist_hour.between(8, 11)) | (ist_hour.between(17, 21))).to_numpy()
        hard = (sp.yte < 0.75)
        print(f"\n  restricted to rush hours ({rush.sum():,} of {len(rush):,} test rows)"
              f" and to already-slow targets (<0.75, {hard.sum():,} rows)")
        print(f"  {'model':<20}{'rush MAE':>10}{'rush F1':>9}{'slow MAE':>10}")
        for name, p in preds.items():
            mr = metrics(sp.yte[rush], np.asarray(p)[rush])
            mh = metrics(sp.yte[hard], np.asarray(p)[hard])
            for row in all_rows:
                if row.get("model") == name and row.get("horizon_min") == h * 30:
                    row["rush_MAE"] = round(mr["MAE"], 4)
                    row["rush_F1"] = round(mr["congestion_F1"], 3)
                    row["slow_MAE"] = round(mh["MAE"], 4)
            print(f"  {name:<20}{mr['MAE']:>10.4f}{mr['congestion_F1']:>9.3f}{mh['MAE']:>10.4f}")

    res = pd.DataFrame(all_rows)[
        ["horizon_min", "model", "MAE", "RMSE", "MAPE", "congestion_F1",
         "precision", "recall", "n_congested", "vs_persistence_pct",
         "rush_MAE", "rush_F1", "slow_MAE"]]
    res.to_csv(OUT / f"results_era{args.era}.csv", index=False)
    (OUT / f"results_era{args.era}.json").write_text(
        json.dumps(all_rows, indent=1), encoding="utf-8")

    print(f"\n{'='*74}\nSUMMARY — best model per horizon (by MAE)\n{'='*74}")
    for h in HORIZONS:
        sub = res[res.horizon_min == h * 30].sort_values("MAE")
        b = sub.iloc[0]
        print(f"  {h*30:>3} min: {b.model:<20} MAE {b.MAE:.4f}  "
              f"({b.vs_persistence_pct:+.1f}% vs persistence)")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
