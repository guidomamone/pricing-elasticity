# MVP v2: Growth Insights Map (pairs with Acres.com)

## Decision (round 6)
Guido tested the market: **Acres.com** is the best parcel + price + sold-land + listings map (see Acres+ tier),
but it has **no population or growth insights**. So we don't rebuild parcels and prices. We build the layer Acres lacks:
**"where is growth coming?"**, and link out to Acres for any spot's parcel and comps.

Workflow: see a hot area on our map -> click "Open in Acres" (lat/lon) -> check parcels, sold land, listings there.

(Previous parcel-price MVP plan is superseded. Keep it in git history; revive only if Acres data proves insufficient.)

## What the map shows (Marion County first, layers built so they extend statewide)
1. **Population growth**: Census block groups / tracts, colored by
   - % change 2010 -> 2020 (decennial), and latest ACS 5-year estimate vs 2020.
   - Absolute people added per sq mi (small % on big base matters).
   - Toggle: population density now.
2. **Building permits / new construction**: where new homes are going.
   - Preferred: county permit records with addresses, as points or hex heatmap by year.
   - Fallback: parcels that switched vacant -> built per year, from FL DOR yearly roll (land use code + year built). This is the "growth front".
3. **Growth front animation**: time slider 2010 -> today, new construction appearing by year. The single most useful view.
4. **Infrastructure pipeline**: FDOT 5-Year Work Program projects (lines/points, colored by phase: design/ROW/construction).
5. **Utilities**: water/sewer service areas (county + city of Ocala), if published.
6. **Planning**: Future Land Use Map, urban growth boundary / urban service area, recent rezonings and annexations (stretch).
7. **Risk**: FEMA flood zones, wetlands (stretch, Acres may already show these).
8. **Price context (light)**: median vacant-land sale $/acre per hex from FL DOR sales file, so growth vs price is visible at a glance.
   "Growing fast but still cheap" hexes = what we look for.

Click anywhere -> panel: block group stats (pop 2010/2020/now, growth %, median income, median home value),
permits in 1/3 mi last 3 yrs, nearest FDOT project + phase + year, in/out of sewer area, flood zone,
median land $/acre nearby, **"Open in Acres"** link.

## Simple growth score (v0, transparent, not ML)
Per H3 hex (res 8, ~0.7 km2):
```
score = z(pop_growth_rate) + z(permits_per_km2_last3y) + z(growth_front_proximity)
        + funded_road_bonus + sewer_bonus - flood_penalty
```
Shown as its own layer with the components visible on click. Weights in a config file. ML comes later (ARCHITECTURE sec. 4).

## Data (free; worker verifies each)
| Layer | Source |
|---|---|
| Population | Census API: decennial 2010 + 2020 (P1), ACS 5-yr latest (B01003, B19013, B25077); TIGER block group shapes. Note 2010->2020 boundary changes: use NHGIS crosswalks or tract-level. |
| Population estimates (annual) | Census PEP (county/city), FL BEBR estimates & projections (county/city) |
| Permits | Census BPS (county/place, annual); Marion County permit portal (address-level, check exports) |
| Growth front | FL DOR NAL yearly files (land use, year built, parcel centroid via county GIS) |
| Roads | FDOT Work Program GIS (open data portal) |
| Utilities | Marion County Utilities / City of Ocala GIS |
| Planning | Marion County GIS (FLUM, urban growth boundary) |
| Flood | FEMA NFHL |
| Land prices | FL DOR SDF sales, vacant + qualified only |

## Tech
- `scripts/` Python (geopandas, h3, censusdata/requests) builds GeoJSON/PMTiles per layer.
- `map/index.html` MapLibre GL, layer toggles, time slider, click panel. Static on Netlify.
- Acres deep link: confirm URL format that opens at lat/lon (inspect Acres URLs manually). Fallback: copy coords button (Acres search accepts coordinates).
- No backend yet. Supabase arrives with the history/scorekeeping work (ARCHITECTURE sec. 9).

## Steps
1. Recon: confirm sources + Acres deep link format. `data/README.md`.
2. Population layer (block groups, 2010/2020/ACS) + map shell with click panel and Acres link. **Ship this first, it's useful alone.**
3. Growth front from DOR yearly files + time slider.
4. FDOT projects + permits.
5. Hex growth score + price-per-acre hex layer.
6. Guido uses it alongside Acres for 2 weeks -> decide on v3 (signals agent, history, ML).

## Acceptance
- Population numbers match data.census.gov for 5 spot-checked block groups.
- "Open in Acres" lands on the clicked location.
- Loads <3s on phone. Footer lists data vintages and sources.

## Open questions for Guido
- Acres+ subscribed? Does its Export give CSV of sold land? If yes, we can pull sold comps into our price layer instead of DOR.
- County-only for MVP is fine, or whole Central FL corridor (Marion, Sumter, Lake, Citrus, Levy) from the start? Population layer is cheap statewide.
