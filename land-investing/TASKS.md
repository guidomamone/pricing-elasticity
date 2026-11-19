# TASKS: Phase 1, prove it in Marion

Work list for a Sonnet session. Read `CLAUDE.md` and `docs/BACKTEST.md` first.

## How to work
- Do tasks in order. One task per session is fine. Start with the first task marked `todo` in `STATUS.md`.
- Each task has **Output** and **Check**. A task is done only when the check passes and you have printed the evidence.
- After each task: update `STATUS.md` (status, date, one-line note), commit, push.
- If blocked (network 403, missing data), write the blocker in `STATUS.md`, and move to the next task that does not depend on it. Do not invent data.
- Do not tune until the gate passes. Report what you got.
- Input for everything: `data/raw/marion_parcels.parquet`. If missing, run `python scripts/fetch_parcels.py` (about 10 minutes).

Parcel columns: `PARCEL_ID, DOR_UC, JV, LND_VAL, LND_SQFOOT, ACT_YR_BLT, EFF_YR_BLT, NO_BULDNG, NO_RES_UNT, SALE_PRC1, SALE_YR1, SALE_MO1, QUAL_CD1, VI_CD1, SALE_PRC2, SALE_YR2, SALE_MO2, QUAL_CD2, VI_CD2, PHY_ADDR1, geometry`. Areas: project to EPSG:6439 (meters), acres = m2 / 4046.86.

---

## T1. Audit the data and fix the code lists
**Do**
1. Find the official Florida DOR NAL user guide (land use codes and sale qualification codes). Record the URL.
2. Write `model/codes.py` with three sets of `DOR_UC` codes: `VACANT`, `AGRICULTURAL`, `NEVER_DEVELOPABLE` (government, conservation, rights of way, water, utilities), and `MARKET_QUAL` (arm's-length sale codes).
3. Write `model/audit.py` that prints: parcels and acres per code group, share of improved parcels with missing or zero `ACT_YR_BLT`, homes built per year 1980 to 2026.
4. Decide the last complete year (the year before the count drops off sharply). Save it as `LAST_FULL_YEAR` in `model/codes.py`.

**Output:** `model/codes.py`, `model/audit.py`, `reports/01_audit.md` with the tables and the DOR guide URL.
**Check:** total parcels = 286,275. Code groups cover at least 99% of acres. If the guide could not be opened, codes are marked `UNVERIFIED` in the report.

## T2. Hex panel
**Do** in `model/build_panel.py`:
1. Assign each parcel to an H3 resolution 8 hex by its representative point. For parcels larger than 100 acres, split area across hexes by polygon intersection instead (otherwise big tracts land in one hex).
2. For each origin year T in `[1985, 1990, 1995, 2000, 2005, 2009, 2010, 2014, 2015, 2019]` and each hex, compute: `homes_T` (sum of `NO_RES_UNT`, minimum 1 for residential parcels, with `ACT_YR_BLT <= T`), `built_acres_T`, `open_acres_T`, `excluded_acres`, `homes_last5`, `homes_prev5`.
3. For each horizon h in `[5, 10, 15]` where `T + h <= LAST_FULL_YEAR`: `new_homes_h`, and `takeoff_h = new_homes_h >= 10`.

**Output:** `data/processed/panel.parquet` (one row per hex and origin), `reports/02_panel.md` with row counts and takeoff base rate per origin and horizon.
**Check:** sum of `homes_T` at the latest origin is within 2% of the audit's home count for that year. No label column is filled where `T + h > LAST_FULL_YEAR`.

## T3. Features
**Do** in `model/features.py`, strictly following the as-of rule in `docs/BACKTEST.md` section 1:
1. Neighbor sums over H3 rings 1, 2, 5 for `homes_T`, `homes_last5`, `open_acres_T`.
2. `dist_front_km`: distance to the nearest hex with `homes_last5 >= 10` at T. `front_move_km`: that distance at T-5 minus at T.
3. Gravity: `sum(homes_T_j / d_ij^b)` and `sum(homes_last5_j / d_ij^b)` over hexes within 40 km, b in {1, 2}, d in km with a 1 km floor.
4. Roads: download TIGER 2020 primary and secondary roads for Florida from `www2.census.gov/geo/tiger/TIGER2020/PRISECROADS/`. Compute distance to nearest road and to I-75. Distance to downtown Ocala (29.187, -82.140).
5. `border_flag`: hex centroid within 10 km of the county boundary.
6. Do **not** add lot-count, lot-size, assessed-value or any feature built from today's parcel shapes or values.

**Output:** `data/processed/features.parquet`, `reports/03_features.md` listing each feature, its definition, and the latest data year it touches.
**Check:** a test in `model/test_asof.py` that recomputes features for T=2000 after deleting every parcel built after 2000, and asserts they are identical. Run it and show it passing.

## T4. Baselines and models
**Do** in `model/train.py`, using the split table in `docs/BACKTEST.md` section 5:
1. Sample: hexes with `open_acres_T >= 5`.
2. Baselines: rank by `-dist_front_km`, and rank by ring-2 `homes_last5`.
3. Logistic regression (standardized, L2).
4. LightGBM classifier: `max_depth` 4 to 6, `num_leaves <= 31`, `min_child_samples >= 30`, `learning_rate` 0.05, early stopping on grouped folds. Groups = H3 resolution 5 parent. At most 20 parameter combinations.
5. Isotonic calibration fitted out-of-fold.
6. Write frozen predictions per `docs/BACKTEST.md` section 8.

**Output:** `model/train.py`, `predictions/v1-backtest.parquet`.
**Check:** no training row has `T + h > test origin`. Print the origins used for each split.

## T5. Backtest report and gate
**Do** in `model/evaluate.py`: every metric in `docs/BACKTEST.md` section 7, for each horizon and test origin, for both baselines and both models. Include the "not obvious" slice, a per-training-period table, a reliability chart, feature importance, and a map layer `map/data/backtest.json` (hex, probability, actual new homes) so Guido can see hits and misses.

**Output:** `reports/05_backtest.md`, charts in `reports/img/`.
**Check and gate:** the report opens with a five-line verdict: lift at top 10%, capture at top 10%, the same for the best baseline, and PASS or FAIL against the gate in `PLAN.md` (3x lift AND better than both baselines). State all four distortions from `docs/BACKTEST.md` section 2. **Stop here and report to Guido.** Do not continue to T6 before he answers, except T7, which is independent.

## T6. Fix the border (after T5)
Load neighbor counties for features only: Sumter, Lake, Alachua, Citrus, Levy, Putnam, Volusia. Add a `--county` argument to `scripts/fetch_parcels.py`. Look up each `CO_NO` by querying the layer for one known city per county, do not guess. Recompute T3 features with neighbors, rerun T4 and T5, and report the change in metrics for `border_flag` hexes.
**Output:** `reports/06_border.md`. **Check:** metrics before and after, side by side.

## T7. Historical tax rolls (research, independent)
Find out whether Florida DOR publishes past years of NAL (parcel) and SDF (sales) files for Marion, how far back, and how to download them. If available, download the earliest year, 2015, and the latest, and report: how many parcels were vacant in 2015 by the real roll versus by our reconstruction, and how many vacant-land sales per year the SDF files give versus the current roll.
**Output:** `reports/07_historical_rolls.md`, and `scripts/fetch_dor_history.py` if the files exist. **Check:** every URL in the report was opened, or is marked `UNVERIFIED`.

## T8. Show it on the map (after T5 passes)
Add a "Growth score" layer to `map/index.html`: hexes colored by the 10-year probability from the latest origin (train on all origins, score today). Popup: probability, top three reasons, open acres, vacant lots in the hex. Write `predictions/v1.parquet` (live, not backtest).
**Output:** updated map. **Check:** screenshot with the layer on, and the existing layers still working.

---
## After Phase 1
Do not start Phase 2 from this file. Guido reviews the T5 verdict, then `PLAN.md` and this file get rewritten for the next phase.
