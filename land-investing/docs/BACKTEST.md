# Backtest design and tech stack

How Phase 1 trains and tests the growth model. `TASKS.md` turns this into steps.

## 1. The question the backtest answers
"Standing in year T with only what was knowable in year T, could we have ranked the hexes that got built by T+5, T+10, T+15?"

Everything follows from one rule: **a feature for origin year T may only use facts dated T or earlier.**

## 2. Rebuilding the past from today's tax roll
We have one snapshot (2026 roll) with `ACT_YR_BLT`, the year of the oldest building on each parcel. That is the first-development date, which is what we want.

- A parcel counts as **built by T** if `ACT_YR_BLT <= T`.
- **Open land at T** = parcels vacant today, plus agricultural parcels, plus parcels built after T.
- **Never developable** = government, conservation, rights of way, water. Excluded at every T.

Known distortions, to state in every report:
1. **Parcel shapes are today's.** A 200-acre tract in 2015 may be 400 lots now. So work in acres and home counts per hex, never in parcel counts, and never use lot-count or lot-size features (they leak the future).
2. **Demolitions** are invisible. Small in Marion.
3. **The last one or two years are incomplete** in the roll. End all outcome windows at 2024 unless T1 shows 2025 is complete.
4. **Sales are censored.** Only the last two sales per parcel survive, so old prices exist only for parcels that rarely trade. Price results from this roll are provisional until historical rolls are loaded (T7).

## 3. Unit, sample, labels
- **Unit:** H3 resolution 8 hex (about 0.74 km2, 182 acres). Marion is about 5,800 hexes.
- **Sample at origin T:** hexes with at least 5 acres of open land at T.
- **Primary label, "takeoff":** 10 or more new homes in the hex in (T, T+h]. Report sensitivity at 5 and 25.
- **Secondary label:** new homes per km2 in the window (count model).
- **Horizons h:** 5, 10, 15 years.

## 4. Features (all as of T)
| Group | Features |
|---|---|
| Stock | homes built by T, built share of acres, open acres |
| Momentum | homes built in T-5..T and T-10..T-5, their ratio |
| Neighbors | the same three, summed over hex rings 1, 2 and 5 |
| Growth front | distance to nearest hex with 10+ homes built in T-5..T, and the change in that distance over the previous 5 years |
| Between cities | gravity score: sum over other hexes of homes(T) / distance^b, and the same with homes built T-5..T. Try b = 1 and 2 |
| Access | distance to nearest primary/secondary road and to I-75 interchanges, distance to Ocala center |
| Static | share of hex in government or conservation land. Flood and wetlands when available |

Housing stock rebuilt from year built stands in for population. It is available for any year, so no historical census is needed in v1.

**Edge effect:** The Villages, Gainesville and Lake County sit just outside Marion. Until neighbor counties are loaded (T6), gravity and front features are wrong near the border. Flag those hexes.

## 5. Splits
Time first, space second.

| Horizon | Train origins | Test origin | Test window |
|---|---|---|---|
| 5 y | 1995, 2000, 2005, 2010 | 2015 and 2019 | to 2020, to 2024 |
| 10 y | 1995, 2000 | 2014 | to 2024 |
| 15 y | 1985, 1990 | 2009 | to 2024 |

- Rule: every training label must be fully observed before the test origin (train origin + h <= test origin).
- Inside training, tune with **grouped k-fold by H3 resolution 5 parent**, so neighbors never sit on both sides of a split. Random splits overstate accuracy because nearby hexes look alike.
- Report each training period separately. 2005 to 2012 includes the crash and behaves differently.
- The 15 year test has little training data. Report it, weigh it lightly.

## 6. Models
1. **Naive baselines (must be beaten):** (a) rank by distance to growth front, (b) rank by homes built nearby in the last 5 years.
2. **Logistic regression** on standardized features. Readable, a sanity check.
3. **LightGBM** binary classifier, shallow (depth 4 to 6), strong regularization, few rounds. About 20k rows, so do not tune hard.
4. Calibrate probabilities (isotonic, fitted on training folds) so a "30%" means 30%.

## 7. Metrics
- **Lift at top 10%:** takeoff rate in the top decile of hexes divided by the overall rate. **Gate: 3x or more.**
- **Capture:** share of all new homes that landed in the top 10% and top 20% of hexes.
- **Versus naive:** the same two numbers for the baselines. **Gate: the model must beat both.**
- PR-AUC, Brier score, and a reliability chart.
- **"Not obvious" slice:** repeat the metrics only on hexes more than 2 km from the growth front at T. This is where the edge would be, since near-front land is already priced.
- **Price check (provisional):** median $/acre of vacant-land sales in top-decile hexes versus the rest, around T and around the end of the window.

## 8. Freezing predictions
Every scored run writes `predictions/<model_version>.parquet` (committed) with hex, origin, horizon, probability, model version and git SHA. Backtest runs get the suffix `-backtest`. Never overwrite one. This is the future track record.

## 9. Tech stack
All of it runs inside a Claude Code session. No servers needed for Phase 1 to 3.

| Need | Choice | Why |
|---|---|---|
| Language | Python 3 | Already in use |
| Spatial | geopandas, shapely, h3 | Standard, light |
| Tables | GeoParquet files plus pandas | 286k parcels fits in memory. No database yet |
| Models | scikit-learn, LightGBM | Good on small tabular data, quick to retrain |
| Charts | matplotlib | Reports as PNG plus markdown |
| Map | Static MapLibre page reading JSON | Already built |
| Hosting | Claude artifact now. Cloudflare Pages or GitHub Pages later | Netlify account is out of credits |
| Database | None until Phase 4. Then Supabase (Postgres + PostGIS) | Needed only when signals and history arrive |
| News (Phase 4) | Exa for search, Claude Haiku for extraction | See `docs/reference/ARCHITECTURE.md` |

Who does what: Sonnet executes `TASKS.md` one task per session. A stronger model reviews the backtest report at the gate, mainly hunting for leakage. Scheduled Claude sessions can refresh data yearly when the new tax roll lands.

Not needed now: deep learning, satellite imagery, cellular-automata simulators, a routing engine (straight-line distance is enough for v1).
