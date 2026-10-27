# Architecture (Brainstorm v2)

Three products, built in this order:
1. **Data spine**: parcels + sales + risk layers in one spatial database.
2. **Scout agent**: goes out looking for growth signals (plans, permits, rumors), turns them into geolocated, categorized "signals".
3. **Map + scorer**: shows parcels, signals and a growth score; lets you click a lot and get a buy/no-buy memo.

The core idea: **everything becomes a point or polygon on the map with a date, a type, a source and a confidence.** Parcels, sales, a funded interchange, a Facebook rumor about a Publix. The model then just asks "what signals are near this lot, how strong, how recent?"

---

## 1. Data model (the most important design decision)

```
parcel        (parcel_id, county, state, geom, acres, zoning, flum, land_use_code,
               owner, owner_type, just_value, flood_zone, wetland_pct, road_access,
               sewer_dist_m, water_dist_m, last_sale_date, last_sale_price)

sale          (parcel_id, date, price, qualified_flag, vacant_flag)   # FL DOR SDF

signal        (signal_id, geom, geom_precision [exact|parcel|road|city|county],
               category, subcategory, stage, title, summary,
               source_url, source_type, first_seen, event_date,
               confidence 0-1, raw_text_ref, dedupe_key)

signal_parcel (signal_id, parcel_id, distance_m)                      # spatial join, materialized

score         (parcel_id, model_version, as_of, p_growth_5y, est_value_now,
               est_value_5y, irr_base, irr_down, flags[])

watch         (parcel_id or polygon, note, alert_rules)               # your shortlist
```

### Signal taxonomy (categories x stages)
Category: `road`, `utility_water_sewer`, `school`, `hospital`, `retail_anchor`, `employer_industrial`,
`master_planned_community`, `subdivision_plat`, `rezoning`, `annexation`, `flum_amendment`,
`permit_cluster`, `homebuilder_land_buy`, `environmental_risk`, `insurance_risk`, `rumor`.

Stage (this is what the literature says matters most):
`rumor -> proposed -> in_plan -> approved -> funded -> under_construction -> open`

Rule of thumb from the papers: price moves at **funded / under construction / open**, not at announcement.
So the edge is finding things at `approved`/`funded` before they are `under_construction`.

---

## 2. Scout agent

### Sources
| Source | Tool | What we get |
|---|---|---|
| Web / news / gov PDFs | **Exa** (search + contents API) | Local news, county agenda PDFs, FDOT pages, press releases |
| Facebook groups | **Muse** (per Guido) | Rumors: "heard Buc-ee's bought land on SR-44" |
| Categorization | **Jev** (per Guido) | Map raw text -> taxonomy above |
| Structured gov data | direct download/API | FL DOR NAL/SDF, FDOT Work Program, Census BPS, FEMA NFHL, NWI |
| County agendas | Legistar / Granicus / CivicClerk portals (most FL counties use one) | Rezonings, annexations, plats |
| Homebuilder filings | SEC EDGAR | Lennar, D.R. Horton, Taylor Morrison land pipeline by market |
| Reddit | Reddit API or Exa with site filter | r/ocala, r/lakeland, etc. |

> NOTE: I (Claude) don't know what "Muse" and "Jev" are. Guido to provide docs/links/API keys.
> Design assumes they are callable services; if not, Exa + an LLM classifier cover both roles.

### Pipeline
```
[scheduler, daily/weekly per county]
   -> query generator   (templates x county x city, e.g. "{county} rezoning approved subdivision", "{city} new interchange")
   -> fetch             (Exa / Muse / gov feeds)
   -> dedupe            (url hash + semantic similarity of title)
   -> extract           (LLM: what, where, when, stage, who; structured JSON)
   -> categorize        (Jev or LLM with fixed taxonomy)
   -> geocode           (address/intersection/parcel id -> point; fallback road/city centroid
                         with geom_precision flag. Census geocoder free; road names need custom logic)
   -> confidence        (source type weight x stage x corroboration count)
   -> store signal      -> spatial join to parcels -> alert if hits a watched area
```

### Confidence heuristic (starter)
- Source weight: gov doc 1.0, established news 0.8, developer press release 0.7, Reddit 0.4, Facebook 0.3.
- Corroboration: +0.15 per independent source, cap 1.0.
- A rumor never moves a score by itself; it opens a **research task** (agent searches for gov confirmation).

### Agent design choices
- Use small, cheap model (Sonnet/Haiku) for extraction & classification; Opus only for the final per-lot memo.
- Keep raw text forever (`raw_text_ref`) so we can re-extract when the taxonomy changes.
- Every claim on the map links to its source. No source, no pin.

---

## 3. Map

- **Stack proposal:** PostGIS (Supabase works, has free tier) + a static web map (MapLibre GL + PMTiles/vector tiles), deploy on Netlify (already connected).
  Simpler v0: GeoJSON files + Kepler.gl or a single-page MapLibre app. No backend.
- Layers: parcels colored by score, recent vacant sales (price/acre), signals as icons by category, stage as color,
  flood zones, wetlands, sewer service areas, growth front (permits heatmap by year, animated).
- Click parcel -> panel: comps, nearby signals with links, score, IRR cases, "generate memo" button.
- Timeline slider: see how the growth front moved 2010 -> today. This alone is a great learning tool for "getting to know the places".

---

## 4. Scoring model (more detail than v1)

**Value now**: hedonic regression / gradient boosting on FL DOR vacant sales:
`log(price_per_acre) ~ log(acres) + zoning + flood + wetland + road_access + dist_sewer + dist_growth_front + county_year FE`

**Growth probability**: label = parcel became improved (DOR land use code changed vacant -> residential/commercial) within N years.
Train on historical snapshots (FL DOR NAL files exist yearly back many years). Features at time t, outcome at t+5.
This is the cleanest label we have, and it is free.

**Signal features**: counts/strength of signals by category & stage within 1/3/5/10 km, time-decayed.
Historical signals are harder (need backfilling news archives). v1 can use only structured signals (permits, FDOT work program history, plats).

**Backtest**: "if in 2015 we bought the top-100 scored lots in Marion County, what was the return by 2022?" vs random lots. This is the go/no-go for the whole project.

**Decision**: IRR base / downside, include: property tax (FL non-homestead, ~1.5-2% of assessed), closing both sides,
selling cost (agent 6-10% on land or listing sites), time-to-sell (DOR shows days between sales poorly; use listing data), hurdle 12-15%.

---

## 5. Risks / things that kill land deals in FL
- Supply glut in pre-platted lot subdivisions (Cape Coral, Lehigh Acres, Palm Bay, Citrus Springs, Poinciana, Rainbow Lakes).
- Wetland / scrub jay / gopher tortoise permitting (relocation cost per tortoise is real money).
- Septic restrictions near springs (Basin Management Action Plans in Marion/Alachua etc.).
- Insurance market + flood maps changing.
- Impact fees spike when a county decides to slow growth.
- Survivorship bias in backtest: places that grew are easy to find after the fact.

## 6. Unknowns for Guido
- What exactly are Muse and Jev (links/keys)?
- Budget for paid data (Regrid ~ $ per county or nationwide; Land Insights subscription)?
- Pilot county? My suggestion: **Marion (Ocala)** or **Sumter/Lake** in FL, which have strong I-75 / Villages growth, lots of vacant land, varied prices. Second: **Baldwin County, AL**.

---

## 7. Decisions (round 3, from Guido)

- **Hold horizon: up to 15 years.** Changes the model: the 5-year "becomes built" label is too short. Use 5/10/15y labels
  (FL DOR files go back far enough for 10y; 15y may need older county data). Long holds favor
  *real-option* thinking: cheap carry (low property tax, no HOA) matters as much as upside. Add carry cost to the scorer.
- **Pilot: Florida, county open.** Default to **Marion County** unless the worker finds a data blocker, then fall back to Sumter or Lake.
- **Price filter required.** Two different "prices" exist, keep both:
  1. *Estimated value* (our model, every parcel).
  2. *Asking price* (only parcels for sale). Needs listing data: LandWatch / Lands of America / Zillow / Realtor
     have no clean public API and scraping violates ToS. Options: Land Insights or Regrid exports, MLS access via an agent,
     or Exa searches restricted to listing sites as a light feed. Decide later; build the filter on estimated value first.
- **Muse** (Meta, Sept 2026): personal AI agent strong at the Meta ecosystem, used for Facebook group rumor search.
  Open question: is there a developer API, or is it consumer-app only? If app-only, workflow is semi-manual:
  Guido runs saved Muse prompts per county, pastes/exports results into `inbox/`, the pipeline ingests them.
- **Jev** (typesafe.ai): non-LLM model for very cheap decisions. Use it for the high-volume, repetitive steps:
  - signal category + stage classification,
  - "is this article relevant to land growth in county X?" filter before any LLM call,
  - dedupe "same event?" decisions.
  LLM stays for structured extraction (location, dates) and the final per-lot memo.
  Plan: label ~300 signals with an LLM first, use them to train/configure Jev, compare accuracy and cost.

## 8. Platform recommendation

Don't start with a platform. Start with:
- **Supabase** (Postgres + PostGIS, auth, REST API, free tier then ~$25/mo). One database for parcels, sales, signals, scores.
  Price/acreage/score filters become SQL; the map calls it.
- **Map front end**: MapLibre GL app on **Netlify** (already connected). Filters: price range, acres, score, flood, signal category/stage.
- **Agents**: scheduled jobs (GitHub Actions cron or Supabase Edge Functions / a small worker) running the scout.

Buy vs build checkpoint after the backtest:
- If the model doesn't beat random lots, stop and just use Land Insights for flipping-style comps.
- If it does, this becomes its own repo + app. Felt or ArcGIS Online are options if you want a hosted map without code,
  but they're weaker at custom scoring.
