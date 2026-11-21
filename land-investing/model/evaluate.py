"""T5: backtest report and gate.

Run from land-investing/: python -m model.evaluate
Reads predictions/v1-backtest.parquet. Writes reports/05_backtest.md, reports/img/*.png and
map/data/backtest.json.

Rankings use the uncalibrated score. Hexes tied at the top-k cut-off (common for the front
baseline, where many hexes sit at distance 0) count fractionally, which equals the expected value
under random tie-breaking.
"""
import json

import h3
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss

from model.codes import MARKET_QUAL
from model.load import ROOT, load_parcels
from model.train import (BASELINES, SPLITS, feature_cols, fit_all, fit_baseline, fit_lgbm,
                         fit_lr, load_table, raw_score)

PRED = ROOT / "predictions" / "v1-backtest.parquet"
IMG = ROOT / "reports" / "img"
OUT = ROOT / "reports" / "05_backtest.md"
GATE_LIFT = 3.0
NOT_OBVIOUS_KM = 2.0
NAMES = {"base_front": "Baseline: near growth front", "base_ring2_last5": "Baseline: recent homes nearby",
         "logreg": "Logistic regression", "lgbm": "LightGBM", "lgbm_noroads": "LightGBM, no 2020 roads"}


def topk(score, y, w, k):
    """Takeoffs and new homes in the top k share, with fractional ties. Returns (n_top, y_top, w_top)."""
    s = pd.DataFrame({"s": score, "y": y, "w": w}).groupby("s", sort=True)[["y", "w"]].agg(["sum", "size"])
    s = s.iloc[::-1]
    size = s[("y", "size")].to_numpy()
    ys, ws = s[("y", "sum")].to_numpy(), s[("w", "sum")].to_numpy()
    m = k * len(score)
    before = np.concatenate([[0], np.cumsum(size)[:-1]])
    frac = np.clip((m - before) / size, 0, 1)
    return m, float((frac * ys).sum()), float((frac * ws).sum())


def metrics(g: pd.DataFrame) -> dict:
    y, w = g.takeoff.to_numpy(), g.new_homes.to_numpy()
    base = y.mean()
    r = {"hexes": len(g), "takeoffs": int(y.sum()), "base_rate": base}
    for k in (0.1, 0.2):
        m, yt, wt = topk(g.raw_score.to_numpy(), y, w, k)
        r[f"lift{int(k * 100)}"] = (yt / m) / base if base > 0 else np.nan
        r[f"capture{int(k * 100)}"] = wt / w.sum() if w.sum() > 0 else np.nan
    r["pr_auc"] = average_precision_score(y, g.raw_score) if y.sum() else np.nan
    r["brier"] = brier_score_loss(y, g.probability)
    return r


def table(pred: pd.DataFrame, by=("horizon", "origin", "model")) -> pd.DataFrame:
    rows = [{**dict(zip(by, k)), **metrics(g)} for k, g in pred.groupby(list(by))]
    return pd.DataFrame(rows)


def fmt(t: pd.DataFrame) -> str:
    t = t.copy()
    if "model" in t:
        t["model"] = t.model.map(NAMES).fillna(t.model)
    for c in t.columns:
        if c.startswith("lift"):
            t[c] = t[c].map(lambda v: f"{v:.2f}x")
        elif c.startswith(("capture", "base_rate")):
            t[c] = t[c].map(lambda v: f"{v:.1%}")
        elif c in ("pr_auc", "brier"):
            t[c] = t[c].map(lambda v: f"{v:.3f}")
    return t.to_markdown(index=False)


def per_training_period(d: pd.DataFrame) -> pd.DataFrame:
    """5 year horizon: train on one origin at a time, test on 2015 and 2019."""
    rows = []
    for t0 in SPLITS[5]["train"]:
        train = d[d["T"] == t0]
        fits = {n: fit_baseline(train, s, 5) for n, s in BASELINES.items()}
        fits["logreg"] = fit_lr(train, feature_cols(train), 5)
        fits["lgbm"] = fit_lgbm(train, feature_cols(train), 5)
        for t in SPLITS[5]["test"]:
            D = d[d["T"] == t]
            for n, f in fits.items():
                g = pd.DataFrame({"raw_score": raw_score(n, f, D), "probability": f[0](D),
                                  "takeoff": D.takeoff_5.to_numpy(), "new_homes": D.new_homes_5.to_numpy()})
                rows.append({"train origin": t0, "test origin": t, "model": n, **metrics(g)})
    return pd.DataFrame(rows)


def threshold_sensitivity(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for thr in (5, 25):
        for h, s in SPLITS.items():
            dd = d.copy()
            nh = dd[f"new_homes_{h}"]
            dd[f"takeoff_{h}"] = np.where(nh.notna(), (nh >= thr).astype(float), np.nan)
            train = dd[dd["T"].isin(s["train"])]
            fits = {n: fit_baseline(train, sc, h) for n, sc in BASELINES.items()}
            fits["lgbm"] = fit_lgbm(train, feature_cols(train), h)
            for t in s["test"]:
                D = dd[dd["T"] == t]
                for n, f in fits.items():
                    g = pd.DataFrame({"raw_score": raw_score(n, f, D), "probability": f[0](D),
                                      "takeoff": D[f"takeoff_{h}"].to_numpy(),
                                      "new_homes": D[f"new_homes_{h}"].to_numpy()})
                    m = metrics(g)
                    rows.append({"threshold": thr, "horizon": h, "origin": t, "model": n,
                                 "base_rate": m["base_rate"], "lift10": m["lift10"],
                                 "capture10": m["capture10"]})
    return pd.DataFrame(rows)


def leak_ablation(d: pd.DataFrame) -> str:
    """excluded_share uses 2026 codes. 009 (common areas) and 094 (rights of way) are created when
    land is subdivided, so they can mark hexes that develop after T. Size that leak."""
    from model.build_panel import allocate
    p = load_parcels()
    alloc, _ = allocate(p)
    a = alloc.join(p[["uc", "group", "acres"]], on="pidx")
    a["ac"] = a.share * a.acres
    tot = a.groupby("hex").ac.sum()
    sub = a[a.uc.isin(["009", "094"])].groupby("hex").ac.sum().reindex(tot.index, fill_value=0)
    exc = a[a.group.isin(["never_developable", "other"])].groupby("hex").ac.sum().reindex(tot.index, fill_value=0)
    d = d.copy()
    d["excl_v2"] = d.hex.map((exc - sub) / tot).fillna(0)
    share = d.hex.map(sub / tot).fillna(0)
    L = ["| Cell | Takeoff rate, hexes with > 5% of area in 009/094 | Other hexes |", "|---|---|---|"]
    for h, s in SPLITS.items():
        for t in s["test"]:
            D, sh = d[d["T"] == t], share[d["T"] == t]
            y = D[f"takeoff_{h}"]
            L.append(f"| {h}y from {t} | {y[sh > .05].mean():.1%} ({(sh > .05).sum()} hexes) | {y[sh <= .05].mean():.1%} |")
    base = [c for c in feature_cols(d) if c != "excl_v2"]
    variants = {"as frozen": base, "without excluded_share": [c for c in base if c != "excluded_share"],
                "excluded_share without 009 and 094": [c for c in base if c != "excluded_share"] + ["excl_v2"]}
    L += ["", "| LightGBM variant | " + " | ".join(f"{h}y/{t}" for h, s in SPLITS.items() for t in s["test"]) + " |",
          "|---|" + "---|" * 4]
    for name, cols in variants.items():
        cells = []
        for h, s in SPLITS.items():
            tr = d[d["T"].isin(s["train"])]
            fn, m, _ = fit_lgbm(tr, cols, h)
            for t in s["test"]:
                D = d[d["T"] == t]
                g = pd.DataFrame({"raw_score": m.predict_proba(D[cols])[:, 1], "probability": fn(D),
                                  "takeoff": D[f"takeoff_{h}"].to_numpy(), "new_homes": D[f"new_homes_{h}"].to_numpy()})
                r = metrics(g)
                cells.append(f"{r['lift10']:.2f}x / {r['capture10']:.1%}")
        L.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(L)


def reliability(pred: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
    bins = np.array([0, .02, .05, .1, .2, .3, .5, .7, 1.0001])
    for ax, h in zip(axes, SPLITS):
        for n, c in [("lgbm", "#2a6fdb"), ("logreg", "#d9822b")]:
            g = pred[(pred.horizon == h) & (pred.model == n)]
            b = pd.cut(g.probability, bins, include_lowest=True)
            r = g.groupby(b, observed=True).agg(p=("probability", "mean"), o=("takeoff", "mean"),
                                                 n=("takeoff", "size"))
            ax.plot(r.p, r.o, "o-", color=c, label=NAMES[n])
            for _, x in r.iterrows():
                ax.annotate(f"{int(x.n)}", (x.p, x.o), fontsize=7, color=c,
                            textcoords="offset points", xytext=(3, -9))
        ax.plot([0, 1], [0, 1], ":", color="gray")
        ax.set_title(f"{h}-year horizon, test origin(s) {SPLITS[h]['test']}")
        ax.set_xlabel("predicted probability (isotonic, out of fold)")
        ax.set_xlim(0, 1), ax.set_ylim(0, 1)
    axes[0].set_ylabel("observed takeoff rate")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(IMG / "reliability.png", dpi=130)
    plt.close(fig)


def importance(d: pd.DataFrame, pred: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Refit LightGBM per horizon (deterministic seed), check it reproduces the frozen predictions,
    and return gain importance."""
    imps, max_diff = [], 0.0
    for h, s in SPLITS.items():
        train = d[d["T"].isin(s["train"])]
        fn, model, _ = fit_lgbm(train, feature_cols(train), h)
        for t in s["test"]:
            D = d[d["T"] == t]
            frozen = pred[(pred.horizon == h) & (pred.origin == t) & (pred.model == "lgbm")]
            max_diff = max(max_diff, float(np.abs(frozen.probability.to_numpy() - fn(D)).max()))
        g = model.booster_.feature_importance("gain")
        imps.append(pd.Series(g / g.sum(), index=model.feature_name_, name=f"{h}y"))
    imp = pd.concat(imps, axis=1).fillna(0)
    imp = imp.loc[imp.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(8, 6))
    top = imp.head(15).iloc[::-1]
    yy = np.arange(len(top))
    for i, (c, col) in enumerate(zip(top.columns, ["#2a6fdb", "#d9822b", "#3a9e5c"])):
        ax.barh(yy + (i - 1) * 0.27, top[c], height=0.27, color=col, label=c)
    ax.set_yticks(yy, top.index)
    ax.set_xlabel("share of total gain")
    ax.set_title("LightGBM feature importance (gain), by horizon")
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG / "importance.png", dpi=130)
    plt.close(fig)
    return imp, max_diff


def lift_chart(t: pd.DataFrame) -> None:
    cells = t[["horizon", "origin"]].drop_duplicates().to_records(index=False)
    models = ["base_front", "base_ring2_last5", "logreg", "lgbm"]
    cols = ["#9aa3ad", "#c3c8ce", "#d9822b", "#2a6fdb"]
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(cells))
    for i, (m, c) in enumerate(zip(models, cols)):
        v = [t[(t.horizon == h) & (t.origin == o) & (t.model == m)].lift10.iloc[0] for h, o in cells]
        ax.bar(x + (i - 1.5) * 0.2, v, 0.2, color=c, label=NAMES[m])
    ax.axhline(GATE_LIFT, color="crimson", ls="--", lw=1, label="gate 3x")
    ax.set_xticks(x, [f"{h}y from {o}" for h, o in cells])
    ax.set_ylabel("lift at top 10%")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(IMG / "lift_top10.png", dpi=130)
    plt.close(fig)


def price_check(pred: pd.DataFrame) -> str:
    """Median $/acre of market vacant-land sales in 2025-2026 (the only sales on the roll) in
    top-decile hexes versus the rest. Only the end-of-window half of the BACKTEST check is possible."""
    p = load_parcels()
    sales = []
    for i in ("1", "2"):
        s = p[(p[f"VI_CD{i}"] == "V") & p[f"QUAL_CD{i}"].isin(MARKET_QUAL) & (p[f"SALE_PRC{i}"] > 1000)
              & (p.acres > 0.05) & p.group.isin(["vacant", "agricultural"])]
        sales.append(pd.DataFrame({"geometry": s.geometry, "ppa": s[f"SALE_PRC{i}"] / s.acres,
                                   "yr": s[f"SALE_YR{i}"]}))
    s = pd.concat(sales)
    pts = gpdpts(s)
    s["hex"] = [h3.latlng_to_cell(y, x, 8) for x, y in zip(pts.x, pts.y)]
    lines = [f"Market vacant-land sales on the roll (VI_CD = V, QUAL_CD 01 or 02, price > $1,000): "
             f"{len(s):,}, all dated {int(s.yr.min())} to {int(s.yr.max())}.", "",
             "| Prediction | Top 10% hexes: sales, median $/acre | Other hexes: sales, median $/acre | Ratio |",
             "|---|---|---|---|"]
    for (h, o), g in pred[pred.model == "lgbm"].groupby(["horizon", "origin"]):
        g = g.sort_values("raw_score", ascending=False)
        top = set(g.hex.iloc[: int(len(g) * 0.1)])
        inside = s[s.hex.isin(top)]
        rest = s[s.hex.isin(set(g.hex)) & ~s.hex.isin(top)]
        lines.append(f"| {h}y from {o} | {len(inside):,}, ${inside.ppa.median():,.0f} | "
                     f"{len(rest):,}, ${rest.ppa.median():,.0f} | {inside.ppa.median() / rest.ppa.median():.1f}x |")
    lines += ["", "This is a price at the **end** of the window, after the growth happened, so a high "
              "ratio only says the model found land that is now expensive. The **start** of window "
              "half (was it cheap at T?) needs historical sales, which this roll does not hold "
              "(see `reports/01_audit.md`). Provisional and not part of the gate."]
    return "\n".join(lines)


def gpdpts(s):
    import geopandas as gpd
    return gpd.GeoSeries(s.geometry, crs=6439).representative_point().to_crs(4326)


def map_layer(pred: pd.DataFrame) -> None:
    g = pred[pred.model == "lgbm"]
    out = {"fields": ["hex", "probability", "new_homes", "takeoff"], "sets": {}}
    for (h, o), x in g.groupby(["horizon", "origin"]):
        out["sets"][f"{h}y_{o}"] = [[r.hex, round(float(r.probability), 3), int(r.new_homes), int(r.takeoff)]
                                   for r in x.itertuples()]
    (ROOT / "map" / "data" / "backtest.json").write_text(json.dumps(out, separators=(",", ":")))


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    pred = pd.read_parquet(PRED)
    d = load_table()
    feats = d[["hex", "T", "dist_front_km", "border_flag"]].rename(columns={"T": "origin"})
    pred = pred.merge(feats, on=["hex", "origin"], how="left", validate="many_to_one")

    t = table(pred)
    obvious = table(pred[pred.dist_front_km > NOT_OBVIOUS_KM])
    border = table(pred, by=("horizon", "origin", "border_flag", "model"))
    print("main table done")
    lift_chart(t)
    reliability(pred)
    imp, max_diff = importance(d, pred)
    print(f"importance done, max refit diff {max_diff:.2e}")
    period = per_training_period(d)
    print("per-period done")
    sens = threshold_sensitivity(d)
    print("sensitivity done")
    price = price_check(pred)
    leak = leak_ablation(d)
    print("leak ablation done")
    map_layer(pred)

    # gate on the headline cell: 5 years from 2015, and every other test cell shown with it
    def cell(h, o, m):
        return t[(t.horizon == h) & (t.origin == o) & (t.model == m)].iloc[0]

    verdict_rows = []
    for h, s in SPLITS.items():
        for o in s["test"]:
            mod = cell(h, o, "lgbm")
            bases = [cell(h, o, b) for b in BASELINES]
            best = max(bases, key=lambda r: r.lift10)
            ok = (mod.lift10 >= GATE_LIFT and all(mod.lift10 > b.lift10 for b in bases)
                  and all(mod.capture10 > b.capture10 for b in bases))
            verdict_rows.append((h, o, mod, best, ok))
    h0 = [v for v in verdict_rows if v[0] == 5 and v[1] == 2015][0]
    _, _, mod, best, ok = h0
    n_pass = sum(v[4] for v in verdict_rows)

    L = ["# 05. Backtest report and gate (T5)", "",
         "## Verdict (5-year horizon, predicting from 2015, the PLAN gate cell)", "",
         f"1. **LightGBM, top 10% of hexes: lift {mod.lift10:.2f}x, capture {mod.capture10:.1%} of new homes.**",
         f"2. Best baseline ({NAMES[best.model]}), top 10%: lift {best.lift10:.2f}x, capture {best.capture10:.1%}.",
         f"3. Gate: lift >= {GATE_LIFT:.0f}x AND better than both baselines on lift and capture.",
         f"4. **{'PASS' if ok else 'FAIL'}** on the gate cell. Across all {len(verdict_rows)} test cells: "
         f"{n_pass} pass ({', '.join(f'{h}y/{o} ' + ('PASS' if k else 'FAIL') for h, o, _, _, k in verdict_rows)}).",
         "5. Caveat: past vacancy is rebuilt from the 2026 roll, so these numbers are an upper "
         "bound until checked against a historical roll (T7). Stop here for Guido's review.", "",
         "### Every test cell", "",
         "| Cell | LightGBM lift / capture top 10% | Best baseline lift / capture | Gate |",
         "|---|---|---|---|"]
    for h, o, m_, b_, k in verdict_rows:
        L.append(f"| {h}y from {o} | {m_.lift10:.2f}x / {m_.capture10:.1%} | {b_.lift10:.2f}x / "
                 f"{b_.capture10:.1%} ({NAMES[b_.model]}) | {'PASS' if k else 'FAIL'} |")
    L += ["", "![lift](img/lift_top10.png)", "",
          "## Distortions (docs/BACKTEST.md section 2)", "",
          "1. **Parcel shapes are today's.** A tract that was one parcel at T may be 400 lots now. The "
          "model works in acres and homes per hex and uses no lot-count, lot-size or value feature.",
          "2. **Demolitions are invisible.** A home torn down before 2026 never shows in the roll, so "
          "past stock is slightly undercounted. Small in Marion.",
          "3. **The last years are incomplete.** 2026 has no homes and 2025 cannot be shown complete, "
          "so every window ends at 2024 (`LAST_FULL_YEAR`).",
          "4. **Sales are censored**, worse than expected: the 2026 roll only holds 2025 and 2026 "
          "sales. No price result here is usable until historical SDF files are loaded (T7).",
          "", "Also: **roads are TIGER 2020** (a leak for early origins). The LightGBM without the two "
          "road-distance features scores the same or better (table below), so the leak is not "
          "driving the result. I-75 and the Ocala distance are fixed geography.",
          "", "## Leakage review", "",
          "Checks run before reporting, looking for anything that lets the future into a feature.", "",
          "- **As-of test passes** for every parcel-derived feature (`reports/03_features.md`).",
          "- **Roads (2020):** removing them does not hurt (see the no-roads rows below).",
          "- **`excluded_share` leaks, a little.** It uses 2026 codes, and 009 (subdivision common "
          "areas) and 094 (rights of way) appear when land is platted. Hexes with those codes took off "
          "far more often, so the feature can see future subdivisions. Removing it or rebuilding it "
          "without 009 and 094 moves top-10% lift by a few tenths and changes no gate result. The "
          "frozen v1 predictions keep it (they are never overwritten). **v2 should drop 009 and 094 "
          "from `excluded_share`.**", "",
          leak, "",
          "- **Replaced homes look new.** A mobile home replaced in 2018 carries ACT_YR_BLT 2018, so "
          "the old home is missing at T and the new one counts as growth. This inflates takeoff in "
          "old mobile-home areas, the same family of error as demolitions.",
          "- **Spatial overlap between train and test.** Test hexes are the same places as training "
          "hexes, later in time. That is the real use case (score Marion today), not a leak, but it "
          "says nothing yet about other counties (Phase 2 gate).", "",
          "## All metrics, by horizon, test origin and model", "",
          "Sample: hexes with >= 5 open acres at T. Lift and capture rank by the raw score. PR-AUC "
          "uses the raw score, Brier the calibrated probability (baselines are calibrated with "
          "isotonic on their training rows so they get a Brier too).", "",
          fmt(t), "",
          f"## \"Not obvious\" slice: hexes more than {NOT_OBVIOUS_KM:.0f} km from the growth front at T", "",
          "Lift here is relative to the slice's own base rate. This is where an edge would be, since "
          "land near the front is already priced.", "", fmt(obvious), "",
          "## Per training period (5-year horizon, one training origin at a time)", "",
          "2005 trains on the crash (2005 to 2010 windows). 2010 trains on the bottom.", "",
          fmt(period), "",
          "## Takeoff threshold sensitivity (5 and 25 new homes, primary is 10)", "",
          fmt(sens), "",
          "## Border hexes (within 10 km of the county line) versus interior", "",
          "Feature values near the border miss the neighbour counties (fixed in T6).", "",
          fmt(border), "",
          "## Calibration", "", "![reliability](img/reliability.png)", "",
          "Point labels are hex counts per bin. Calibration is isotonic, fitted on out-of-fold "
          "training predictions, so it carries the training period's base rate. When the test "
          "period's rate differs (the 2009 and 2010 crash windows, or the 2019 to 2024 boom) the "
          "probabilities are off in level even when the ranking is good.", "",
          "## Feature importance (LightGBM gain)", "",
          f"Refitting LightGBM reproduces the frozen predictions (max abs difference {max_diff:.1e}).", "",
          "![importance](img/importance.png)", "",
          imp.head(15).map(lambda v: f"{v:.1%}").to_markdown(), "",
          "## Price check (provisional)", "", price, "",
          "## Map layer", "",
          "`map/data/backtest.json`: LightGBM probability, actual new homes and takeoff per hex for "
          "each test cell (keys like `5y_2015`). Wiring it into `map/index.html` is part of T8.", ""]
    OUT.write_text("\n".join(L))
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
