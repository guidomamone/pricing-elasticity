# PLAN: finding land in the path of growth

Source of truth for strategy. Work items live in `TASKS.md`. Model method lives in `docs/BACKTEST.md`.

## Goal
Find vacant land to buy, hold up to 15 years, and sell. Not distressed or legally troubled land. Land in areas that will urbanize, bought before the price reflects it. First for Guido's own investing. A subscription product is a later option.

Scope: Florida first (pilot: Marion County), then Georgia and Alabama.

## The idea
Score every area by how likely it is to urbanize in 5 to 15 years, compare that with what land there costs today, and buy where the probability is high and the price has not caught up.

Caveat: obvious growth is already priced (Marion Oaks lots sell around $120k/acre). The edge has to come from the 10 to 15 year band and from the gap between probability and price. A backtest has to prove that gap exists before money goes in.

## The model
| Part | Question | Method |
|---|---|---|
| 1. Growth probability | Will this hex go from open land to built within 5/10/15 years? | Logistic regression baseline, then gradient boosting |
| 2. Land price | What is land worth here today, and once built around? | Regression of sale price per acre on location and lot features |
| 3. Decision | Is it cheap for its odds? | Expected sale value by probability, minus taxes and costs, as an annual return |

Unit: H3 hexagon, resolution 8 (about 0.3 sq mi). Parcels inherit their hex score.

Features:
- **Growth front:** distance to homes built in the last 5 years, and how fast that front is moving.
- **Between cities:** for each hex, nearby housing stock and its growth, weighted by distance. Land between two growing places scores high from both sides (the Raleigh to Durham case).
- **Access:** distance to highways and interchanges.
- **Gates:** funded road projects, sewer and water reach, future land use maps (Phase 4).
- **Exclusions:** flood zones, wetlands, conservation and government land.

News is an overlay, not the base. A news item flags a hex for review and is logged with its source. It becomes a model input only after the source scorecard shows which sources were right.

## Phases and gates
| # | Phase | Output | Gate to pass |
|---|---|---|---|
| 0 | Marion map | Population, new construction by year, vacant lots with prices | **Done** |
| 1 | Prove it in Marion | Backtest report: predict from 2015, check against what got built | Top 10% of hexes get built at 3x the average rate or more, AND the model beats the naive "close to recent building" rule. Otherwise stop or rethink |
| 2 | All of Florida | Same pipeline statewide, ranking of corridors | Marion-trained model still works on other counties |
| 3 | Price and undervaluation | Map of hexes that are cheap for their odds, with the lots inside | In the backtest, "high odds, low price" land beat the county average after costs |
| 4 | News and signals | Funded roads, permits, then the search agent with source scoring | Signals improve the backtest or the review workflow |
| 5 | Invest | Shortlist 20 lots, visit, buy 1 or 2. Every prediction frozen and dated | Guido's call |
| 6 | Product | Georgia and Alabama, subscription site | Backtest plus live track record exist |

## Risks
- **Inferred history.** Past vacancy is rebuilt from today's tax roll. That can flatter the backtest. Historical tax rolls fix it (see `TASKS.md` T7).
- **Slow feedback.** Real results take years. The backtest carries the weight early.
- **Carrying cost and liquidity.** 15 years of taxes and slow lot sales can eat a good call.
- **One boom, one bust.** 2005 to 2012 was a crash. Results must be shown per period, not only averaged.

## Open decisions (Guido)
- Budget per lot. It decides between small platted lots and acreage.
