# land-investing

A model and map for finding vacant land in the path of growth. Florida first, pilot in Marion County.

## Where things are
| File | What it is | Status |
|---|---|---|
| `PLAN.md` | Strategy, phases and pass/fail gates | **Current. Source of truth** |
| `TASKS.md` | Step-by-step work list for the current phase | **Current. Execute this** |
| `STATUS.md` | What is done, what is next | **Current. Update every session** |
| `docs/BACKTEST.md` | How the model is trained and tested, and the tech stack | Current |
| `CLAUDE.md` | Rules for Claude sessions | Current |
| `docs/reference/` | Literature, existing tools, later-phase design (search agent, database) | Background only |
| `docs/archive/` | Old MVP plan and old task list | Dead. Do not execute |

## Folders
- `scripts/`: data download and map-layer builders.
- `model/`: backtest code (created in Phase 1).
- `map/`: static MapLibre map. `map/data/` holds the small committed layers.
- `data/raw/`: downloads, not committed. `data/processed/`: model tables, not committed unless small.
- `reports/`: backtest reports and charts.

## Run
```
cd land-investing
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_population.py      # Census -> map/data/population.geojson
python scripts/fetch_parcels.py         # 286k Marion parcels -> data/raw/marion_parcels.parquet (about 10 min)
python scripts/build_parcel_layers.py   # -> map/data/growth.json, vacant.json
python -m model.audit                   # T1 -> reports/01_audit.md
python -m model.build_panel             # T2 -> data/processed/panel.parquet
python -m model.features                # T3 (needs TIGER zips in data/raw/tiger/)
python -m pytest model/test_asof.py     # T3 leakage test
python -m model.train                   # T4 -> predictions/v1-backtest.parquet
python -m model.evaluate                # T5 -> reports/05_backtest.md
python -m http.server -d map 8000       # open http://localhost:8000
```
Needs internet access to www2.census.gov, services9.arcgis.com, unpkg.com, tiles.openfreemap.org.
