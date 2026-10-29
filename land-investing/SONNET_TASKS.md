# Instructions for a Sonnet worker

You are picking up a brainstorm-stage project. Read `BRAINSTORM.md` and `ARCHITECTURE.md` in this folder first.
Work only inside `land-investing/`. Keep it small and runnable. Python 3, `uv` or `pip` + `requirements.txt`.

## Ground rules
- **Verify, don't guess.** Every URL, dataset and API claim you write down must be one you actually opened. If you could not open it, write `UNVERIFIED`.
- Log every search you run and what failed in `research/LOG.md` (query, tool, result usefulness 1-5). Guido explicitly wants to know research limitations.
- Don't buy anything, sign up for paid services, or store API keys in the repo. Use env vars (`EXA_API_KEY`, etc.) and a `.env.example`.
- No em-dashes in prose (Guido's preference): use a period or a comma.
- Commit small, descriptive commits. Do not open a PR unless asked.
- If something blocks you (missing key, unknown tool), write it in `OPEN_QUESTIONS.md` and move to the next task.

## Task 0: Verify the landscape (research, ~1-2h)
Output: `research/landscape.md`
1. Find and open the Boston University land value model GitHub repo. Record: URL, license, coverage (FL/GA/AL?), resolution, year, how to download.
2. Open the IDB Urban Land Valuation tool repo. Record method + whether reusable.
3. Check SLEUTH and UrbanSim: still maintained? license? any Florida applications?
4. Look for any startup/fund doing "path of growth" land prediction (search terms: "path of growth" land AI, "land banking" analytics, "predictive land acquisition" homebuilder). List them with what they sell.
5. Verify each paper cited in `BRAINSTORM.md` section 2. Fix wrong links (the Gold Coast light rail paper link is known to be wrong). Add: Capozza & Helsley 1989 (JUE), Titman 1985, a recent paper on Florida land/housing growth if found.

## Task 1: Florida DOR data feasibility (~2h)
Output: `data/README.md` + `scripts/fetch_fl_dor.py`
1. Find the official FL Dept. of Revenue page for NAL (name-address-legal) and SDF (sales data) files. Record URL, format, years available, field dictionary link.
2. Download **one county** (Marion, county code to look up) for the latest year and one year ~10 years earlier, if available.
3. Write a script that loads NAL + SDF into a pandas/GeoPandas frame (parcel geometry may need a separate county GIS shapefile, find it).
4. Report: number of vacant parcels (DOR land use codes 000, 010, etc., confirm the codes), number of qualified vacant sales per year, median price per acre by year.
5. Do not commit raw data. Add `data/raw/` to `.gitignore`.

## Task 2: Structured growth signals for Marion County (~2h)
Output: `data/signals_structured.md` + scripts
- FDOT 5-Year Work Program: find the downloadable dataset/API. Extract projects in Marion with location, phase, funding year.
- Census Building Permits Survey: county-level monthly/annual permits. Is there sub-county (place-level) data? Yes for places, confirm.
- County permit portal: does Marion publish permit-level data with addresses? Record.
- Water/sewer: does Marion County Utilities or Ocala publish service area GIS? Record URLs.
- FEMA NFHL and USFWS NWI: download URLs for Marion.

## Task 3: Scout agent prototype (Exa only) (~3h)
Output: `scout/` package
1. `scout/taxonomy.py`: categories and stages from `ARCHITECTURE.md` as enums.
2. `scout/queries.py`: query templates per category, filled with county/city names.
3. `scout/search_exa.py`: call Exa search + contents. Use date filters (last 90 days). Handle no-key case gracefully.
4. `scout/extract.py`: LLM call (Claude Haiku/Sonnet via Anthropic API, use the latest model IDs) that returns strict JSON: title, summary, category, stage, location_text, event_date, confidence_reason. Provide a JSON schema and validate.
5. `scout/geocode.py`: Census geocoder for addresses; for intersections/roads, return `geom_precision="road"` and a best guess; never invent coordinates.
6. `scout/store.py`: append to `data/signals.geojson` with dedupe on url hash.
7. Run it for Marion County, commit 20-50 example signals (they're public news, small), and write `scout/RESULTS.md`: precision by eye on 20 samples, what failed.
- Leave hooks (`sources/muse.py`, `classify/jev.py`) as stubs raising `NotImplementedError` with a docstring: "awaiting Guido's docs".

## Task 4: Map v0 (~2h)
Output: `map/index.html` (single file, MapLibre GL via CDN, pinned version)
- Load `data/signals.geojson` and a sample of vacant parcels (or sales points) as GeoJSON.
- Signals: icon/color by category, opacity by stage.
- Click popup: title, stage, date, source link.
- Filter checkboxes by category and stage.
- Must work by opening the file locally (or `python -m http.server`). No backend.
- Don't deploy. Guido decides on hosting (Netlify is connected).

## Task 5: Baseline growth model (only after Task 1 works) (~3h)
Output: `model/` notebook or script + `model/REPORT.md`
- Label: vacant parcel in year T becomes non-vacant by T+5 (DOR land use code).
- Features: acres, distance to nearest parcel converted in T-3..T (the "growth front"), distance to major road, flood zone, wetlands if available, zoning/FLUM if available.
- Model: logistic regression then LightGBM. Spatial cross-validation (split by area, not random).
- Report AUC, calibration, and the backtest: average price-per-acre change of top-decile vs all vacant parcels.
- Be honest about leakage and survivorship.

## Definition of done for this round
- All five outputs exist, or `OPEN_QUESTIONS.md` explains why not.
- `research/LOG.md` lists every search and its usefulness.
- A short `STATUS.md` for Guido: what works, what's blocked, what you recommend next, 10 lines max.

## Updates (round 3)
- Pilot county: **Marion, FL** (fall back to Sumter or Lake on blockers).
- Hold horizon 15 years: in Task 5 build labels for 5 and 10 years (15 if data allows) and add annual carry cost (property tax, from DOR millage) to the IRR.
- Add a **price filter** to the map (Task 4): estimated value per parcel and $/acre, range sliders. Asking prices are out of scope until Guido picks a listing source.
- Task 3 additions:
  - `classify/jev.py`: implement against Jev docs at https://docs.typesafe.ai/introduction (Opus could not open it from its sandbox, read it yourself). Use Jev for relevance filter + category/stage. Keep an LLM fallback and log accuracy vs LLM labels on the same 50 items.
  - `sources/muse.py`: check the Meta announcement (https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/) for an API. If none, implement an `inbox/` ingester for text Guido exports from Muse, and write the per-county prompts he should run in `scout/muse_prompts.md`.
- Database: target **Supabase + PostGIS**. Write `db/schema.sql` from `ARCHITECTURE.md` section 1, but keep GeoJSON files as the working store until Guido creates the project.
- Exa key: read from env var `EXA_API_KEY`. Never commit it.

## Updates (round 4): history and scorekeeping
- The store is **Supabase/Postgres from the start**, not GeoJSON (GeoJSON only as map export). If Guido hasn't created the project, use local Postgres + PostGIS in Docker with the same `db/schema.sql`.
- Implement the append-only tables in `ARCHITECTURE.md` section 9 in `db/schema.sql`, plus `current_*` views.
- Task 1: load **multiple years** of FL DOR NAL for Marion into `parcel_snapshot` (as many years as available). This is the development track.
- Task 3: every signal write goes to `signal_version` with a `source_id`. Seed `source` table with each domain/newsletter/group.
- Task 5: write model outputs into `prediction` (frozen) with `model_version` and git SHA. Backtest predictions get `model_version` suffixed `-backtest`.
- New Task 6: `jobs/resolve_predictions.py`, `jobs/resolve_signals.py` (rules defined in code before running), `jobs/source_scorecard.py` -> `reports/source_scorecard.md` (hit rate, median lead time, false alarm rate).

## PRIORITY OVERRIDE (round 5): build the MVP first
Do `MVP.md` steps 1-5 before anything else above. Tasks 0-6 resume after Guido has used the map.
Task 1 (FL DOR data) overlaps with MVP step 1, reuse the work.

## PRIORITY OVERRIDE (round 6): MVP changed
Guido will use Acres.com for parcels/prices. Build **MVP v2 Growth Insights Map** in `MVP.md` (population, growth front, FDOT, permits, hex score, "Open in Acres" link). Ignore the round-5 parcel-price MVP.
