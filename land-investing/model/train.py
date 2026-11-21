"""T4: baselines, logistic regression and LightGBM, with isotonic calibration fitted out of fold.

Run from land-investing/: python -m model.train
Writes predictions/v1-backtest.parquet (refuses to overwrite, see docs/BACKTEST.md section 8).

Splits follow docs/BACKTEST.md section 5. Inside training, tuning and calibration use grouped
k-fold with groups = H3 resolution 5 parent, so neighbouring hexes never sit on both sides.
"""
import itertools
import subprocess
import warnings

import h3
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from model.load import PROCESSED, ROOT

warnings.filterwarnings("ignore", category=UserWarning)

VERSION = "v1"
MIN_OPEN_ACRES = 5
SPLITS = {5: {"train": [1995, 2000, 2005, 2010], "test": [2015, 2019]},
          10: {"train": [1995, 2000], "test": [2014]},
          15: {"train": [1985, 1990], "test": [2009]}}
ID_COLS = ["hex", "T"]
ROAD_COLS = ["dist_road_km", "dist_primary_km"]
COUNT_COLS = ["homes_T", "homes_last5", "homes_prev5", "momentum_ratio"]  # log1p for the LR
N_FOLDS = 5
GRID = [dict(max_depth=d, num_leaves=l, min_child_samples=c, reg_lambda=r)
        for d, l, c, r in itertools.product([4, 6], [15, 31], [30, 100], [1.0, 10.0])]  # 16 combos
SEED = 7


def load_table() -> pd.DataFrame:
    f = pd.read_parquet(PROCESSED / "features.parquet")
    p = pd.read_parquet(PROCESSED / "panel.parquet")
    labels = [c for c in p.columns if c.startswith(("takeoff_", "new_homes_"))]
    d = f.merge(p[ID_COLS + labels], on=ID_COLS, how="left", validate="one_to_one")
    d["group5"] = [h3.cell_to_parent(c, 5) for c in d.hex]
    return d[d.open_acres_T >= MIN_OPEN_ACRES].reset_index(drop=True)


def feature_cols(d: pd.DataFrame, roads: bool = True) -> list[str]:
    skip = set(ID_COLS) | {"group5"}
    cols = [c for c in d.columns if c not in skip and not c.startswith(("takeoff_", "new_homes_"))]
    return cols if roads else [c for c in cols if c not in ROAD_COLS]


def lr_matrix(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    for c in X.columns:
        if c.startswith(("homes", "grav", "open_acres", "built_acres")) or c in COUNT_COLS:
            X[c] = np.log1p(X[c].clip(lower=0))
    return X


def check_split(train: pd.DataFrame, h: int, test_origin: int) -> None:
    bad = (train["T"] + h > test_origin).sum()
    assert bad == 0, f"{bad} training rows have T + h > test origin {test_origin}"
    assert train[f"takeoff_{h}"].notna().all(), "training rows must have observed labels"


def lgb_cv(X, y, groups, params) -> tuple[float, int, np.ndarray]:
    """Grouped CV with early stopping. Returns mean logloss, mean best rounds, OOF raw scores."""
    oof = np.zeros(len(y))
    losses, rounds = [], []
    for tr, va in GroupKFold(N_FOLDS).split(X, y, groups):
        m = lgb.LGBMClassifier(n_estimators=2000, learning_rate=0.05, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.8, random_state=SEED,
                               verbose=-1, **params)
        m.fit(X.iloc[tr], y[tr], eval_set=[(X.iloc[va], y[va])], eval_metric="binary_logloss",
              callbacks=[lgb.early_stopping(50, verbose=False)])
        oof[va] = m.predict_proba(X.iloc[va], num_iteration=m.best_iteration_)[:, 1]
        losses.append(m.best_score_["valid_0"]["binary_logloss"])
        rounds.append(m.best_iteration_)
    return float(np.mean(losses)), int(np.mean(rounds)), oof


def fit_lgbm(train: pd.DataFrame, cols: list[str], h: int):
    X, y, g = train[cols], train[f"takeoff_{h}"].to_numpy().astype(int), train.group5.to_numpy()
    best = None
    for params in GRID:
        loss, n, oof = lgb_cv(X, y, g, params)
        if best is None or loss < best[0]:
            best = (loss, n, oof, params)
    loss, n, oof, params = best
    model = lgb.LGBMClassifier(n_estimators=max(n, 10), learning_rate=0.05, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.8, random_state=SEED,
                               verbose=-1, **params).fit(X, y)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(oof, y)
    info = {**params, "rounds": n, "cv_logloss": round(loss, 4)}
    return (lambda D: iso.predict(model.predict_proba(D[cols])[:, 1])), model, info


def fit_lr(train: pd.DataFrame, cols: list[str], h: int):
    X, y, g = lr_matrix(train[cols]), train[f"takeoff_{h}"].to_numpy().astype(int), train.group5
    make = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
    oof = np.zeros(len(y))
    for tr, va in GroupKFold(N_FOLDS).split(X, y, g):
        oof[va] = make().fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[va])[:, 1]
    model = make().fit(X, y)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(oof, y)
    return (lambda D: iso.predict(model.predict_proba(lr_matrix(D[cols]))[:, 1])), model, {}


def fit_baseline(train: pd.DataFrame, score, h: int):
    """A ranking rule. Isotonic on the training rows turns its score into a probability, which
    keeps its ranking and lets Brier and reliability be reported for it too."""
    y = train[f"takeoff_{h}"].to_numpy().astype(int)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(score(train), y)
    return (lambda D: iso.predict(score(D))), None, {}


BASELINES = {"base_front": lambda D: -D["dist_front_km"].to_numpy(),
             "base_ring2_last5": lambda D: D["homes_last5_r2"].to_numpy()}


def fit_all(train: pd.DataFrame, h: int) -> dict:
    """Returns model name -> (predict_fn, fitted_model, info). Raw score kept for ranking."""
    out = {name: fit_baseline(train, s, h) for name, s in BASELINES.items()}
    out["logreg"] = fit_lr(train, feature_cols(train), h)
    out["lgbm"] = fit_lgbm(train, feature_cols(train), h)
    out["lgbm_noroads"] = fit_lgbm(train, feature_cols(train, roads=False), h)
    return out


def raw_score(name: str, fitted, D: pd.DataFrame) -> np.ndarray:
    """Uncalibrated score, used to break ties in rankings (isotonic output has many ties)."""
    fn, model, _ = fitted
    if name in BASELINES:
        return BASELINES[name](D)
    if name == "logreg":
        return model.predict_proba(lr_matrix(D[model.feature_names_in_]))[:, 1]
    return model.predict_proba(D[model.feature_name_])[:, 1]


def git_sha() -> str:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                         cwd=ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "model"], capture_output=True,
                           text=True, cwd=ROOT).stdout.strip()
    return sha + ("-dirty" if dirty else "")


def main() -> None:
    out_path = ROOT / "predictions" / f"{VERSION}-backtest.parquet"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists. Predictions are never overwritten; bump VERSION.")
    d = load_table()
    sha = git_sha()
    rows, infos = [], []
    for h, s in SPLITS.items():
        train = d[d["T"].isin(s["train"])]
        for t in s["test"]:
            check_split(train, h, t)
        print(f"h={h}: train origins {sorted(train['T'].unique())} ({len(train):,} rows, "
              f"base rate {train[f'takeoff_{h}'].mean():.3f}), test origins {s['test']}, "
              f"max train T+h = {train['T'].max() + h}")
        fitted = fit_all(train, h)
        for name, f in fitted.items():
            if f[2]:
                infos.append({"h": h, "model": name, **f[2]})
            for t in s["test"]:
                D = d[d["T"] == t]
                rows.append(pd.DataFrame({
                    "hex": D.hex.to_numpy(), "origin": t, "horizon": h, "model": name,
                    "probability": f[0](D), "raw_score": raw_score(name, f, D),
                    "takeoff": D[f"takeoff_{h}"].to_numpy(), "new_homes": D[f"new_homes_{h}"].to_numpy(),
                    "model_version": f"{VERSION}-backtest", "git_sha": sha}))
    pred = pd.concat(rows, ignore_index=True)
    out_path.parent.mkdir(exist_ok=True)
    pred.to_parquet(out_path, index=False)
    pd.DataFrame(infos).to_csv(ROOT / "reports" / "04_tuning.csv", index=False)
    print(pd.DataFrame(infos).to_string(index=False))
    print(f"wrote {len(pred):,} rows -> {out_path} (git {sha})")


if __name__ == "__main__":
    main()
