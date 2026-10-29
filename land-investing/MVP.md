# MVP: Parcel map with price info (Marion County, FL)

## Goal
A web map Guido can open on laptop or phone, zoom into Marion County, see **every parcel outlined**, colored by price,
click one and see its price facts. Filter to "vacant lots, 0.25-5 acres, under $X". Nothing else.

Out of scope for MVP: scout agent, signals, growth model, Supabase, listings/asking prices, other counties.
(The history tables from ARCHITECTURE section 9 come right after, the MVP data loader is written so it can feed them.)

## What the user sees
- Base map (streets + satellite toggle).
- Parcel polygons (visible from ~zoom 13), colored by chosen metric:
  - last sale price, last sale $/acre, assessed (just) value, just value $/acre.
- Below zoom 13: a heat/dot layer of vacant sale $/acre so the county overview still says something.
- Filter panel:
  - Land use: vacant residential / vacant commercial / agricultural / all.
  - Acres range.
  - Price range (sale price or just value, user picks).
  - Last sale year range.
  - Exclude: in FEMA flood zone A/V (stretch, if layer is easy).
- Click parcel -> popup: parcel ID, address, acres, land use, zoning (if available), just value, last 2 sales (date, price, $/acre),
  owner type (individual / LLC / gov), link to the Marion County Property Appraiser page for that parcel.
- "Comps" button in popup (stretch): highlight the 10 nearest vacant sales in last 24 months with similar acreage, show median $/acre.
- Search box: parcel ID or address.

## Data (all free, all to verify by the worker)
| Need | Source | Notes |
|---|---|---|
| Parcel polygons | Marion County Property Appraiser GIS download, or the statewide FL parcel layer (FGIO / FDOR cadastral) | UNVERIFIED which is easier. Must join on parcel ID. |
| Attributes (land use, just value, acres, owner) | FL DOR NAL file, Marion, latest year | Also in many county GIS layers directly |
| Sales | FL DOR SDF file, Marion, last ~5 years; plus "last 2 sales" fields in NAL | Keep only qualified sales (DOR qualification codes) for price stats; show all in popup |
| Flood (stretch) | FEMA NFHL for Marion | |

## Tech (no backend for MVP)
```
scripts/build_marion.py   download -> join polygons + NAL + SDF -> compute metrics -> GeoParquet
                          -> tippecanoe -> marion_parcels.pmtiles (vector tiles, one static file)
map/index.html            MapLibre GL JS + pmtiles protocol, filters done client-side with feature-state/filter expressions
deploy                    Netlify static site (connected). PMTiles file may exceed Netlify's per-file limit:
                          fallback = Cloudflare R2 or Supabase Storage bucket with range requests.
```
Why this: one static file of tiles handles ~200k parcels smoothly, costs ~$0, no server to maintain.
When we add history, predictions and agents, the same build script writes to Supabase and the map reads tiles + API.

Basemap: free options without a key (OpenFreeMap, or Protomaps basemap). Satellite: Esri World Imagery tiles (check terms) or skip.

## Derived fields (computed in build script)
- `acres` (from DOR or polygon area), `is_vacant` (DOR land use 00, 10, 40, 70 range etc., verify codes)
- `last_sale_price`, `last_sale_date`, `last_sale_qualified`, `sale_ppa` = price / acres
- `jv`, `jv_ppa`
- `owner_type` from owner name regex (LLC, INC, TRUST, COUNTY, STATE, USA)
- `ratio_sale_to_jv` (sale price / just value): quick "is assessed value a decent proxy here" sanity check
- Data vintage stamped in the map footer ("DOR 2025 roll, sales through 2025-xx").

## Steps (each is a commit)
1. **Data recon** (worker, 1-2h): confirm download URLs, field dictionaries, land use codes, qualification codes, parcel ID join key. Write `data/README.md`. Stop and report if no free polygon source.
2. **Build script**: produce GeoParquet + summary stats (count parcels, vacant count, vacant qualified sales/year, median $/acre). Sanity-check 10 random parcels against the Property Appraiser website by hand.
3. **Tiles**: tippecanoe to PMTiles, check size and that attributes are present at z13+.
4. **Map**: single `map/index.html`, layers, color ramp, popup, filters, search.
5. **Deploy**: preview on Netlify (Guido approves before publishing anywhere).
6. **Guido uses it for a week**: notes what's missing. That decides v2 (comps, flood, history, signals).

## Acceptance criteria
- Loads in <3s on phone over 4G at county view.
- Clicking any parcel shows correct values for 10/10 spot-checked parcels vs the Property Appraiser site.
- Filter "vacant, 0.5-2 acres, last sale < $30k" returns a plausible set in <1s.
- Footer shows data vintage and sources.

## Risks
- Parcel polygons and DOR files may use different parcel ID formats (dashes, leading zeros). Budget time for the join.
- DOR sale prices include non-arm's-length deals; use qualification codes.
- Just value lags market and is legally capped differently for homestead (less relevant for vacant lots, but note it).
- Tile file size: if too big, drop attributes not used for filtering and fetch details on click from a small per-parcel JSON split.
