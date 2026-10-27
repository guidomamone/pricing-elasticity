# Land Investing: Hold & Sell (Brainstorm)

Scope: vacant lots / small acreage in **Florida + bordering states (Georgia, Alabama)**.
Goal: a model that says "is this lot worth buying at price X, given expected value in N years?"
Status: brainstorming only. Nothing built yet.

---

## 1. Don't reinvent the wheel: what already exists

### Commercial tools (land-investor focused)
| Tool | What it does | Gap vs. our goal |
|---|---|---|
| [Land Insights](https://help.landinsights.co/en/articles/12988032-how-to-comp-a-deal-in-land-insights) | Comps, AI comp value, sell-through rate, wetlands/HOA flags, offer calculator, has an MCP server | Prices *today's* value for flipping. No growth forecast |
| [Land id](https://id.land/blog/how-to-price-land-for-sale-using-comparable-sales-data) (ex-MapRight) | Maps, layers, 24-month sold comps | Same, current value only |
| PropStream / Privy | Lists, comps | Weak on vacant land per [BiggerPockets users](https://www.biggerpockets.com/posts/7313083) |
| Regrid | Nationwide parcel data, zoning, owner | Data source, not a model |
| Zillow / Redfin / LandWatch / Lands of America | Listings + some sold data | Raw data only |

**Takeaway:** the "comp a lot today" problem is solved and cheap to buy. What is **not** packaged anywhere I found is the forward-looking piece: *where will growth reach in 3-10 years*. That is our edge to build.

### Open source / academic
- **Boston University national land value model** (open code on GitHub, rasters on GCP, [Regrid listing](https://regrid.com/listing/bu-land-value)). Best starting point for a baseline per-parcel value. Need to locate the actual repo.
- **IDB Urban Land Valuation tool** ([link](https://knowledge.iadb.org/en/open-knowledge/code-development/open-source-solution/urban-land-valuation)): open source, estimates land appreciation near public works. Conceptually exactly our "infrastructure uplift" piece.
- **SLEUTH** (cellular-automata urban growth model, USGS lineage) and **UrbanSim** (parcel-level land use simulation, open source). Classic urban expansion simulators.
- **PURGOM** parcel-based urban growth model ([paper](https://research.itu.edu.tr/en/publications/urban-growth-prediction-with-parcel-based-3d-urban-growth-model-p/)).
- Random-forest parcel valuation papers (e.g. [Surabaya study](https://ijg.journals.publicknowledgeproject.org/index.php/journal/article/view/4319)): features = zoning, road width, distance to CBD, schools, hospitals.

---

## 2. Literature: how do cities grow and when does land price it in?

**Theory**
- **Alonso-Muth-Mills** monocentric city model: land rent falls with distance to center; city edge is where urban rent = agricultural rent. Growth in population/income pushes the edge out.
- **Capozza & Helsley (1989/1990)** "The fundamentals of land prices and urban growth": land at the fringe = agricultural value + conversion cost + accessibility value + **growth premium**. The growth premium is the thing we're trying to buy cheap. Foundational paper for this project.
- **Real options on land** (Titman 1985, Capozza & Li): undeveloped land is an option to build. Uncertainty raises its value and delays development.
- **Leapfrog development**: growth isn't a smooth ring. It jumps along highways and utility lines.

**Anticipation / announcement effects (the "rumors and plans" question)**
- Timing matters: uplift can come at announcement, funding, construction, or opening. Evidence is mixed.
- St. Paul Green Line: planning announcement no effect on permits; **full funding agreement** did ([Cao & Porter-Nelson 2016](https://ideas.repec.org/a/eee/trapol/v51y2016icp24-32.html)).
- Indian roads programme: no price move at announcement, moved at construction start and completion ([JREFE 2024](https://link.springer.com/10.1007/s11146-022-09938-5)).
- Bangkok transit: premium (~10%) mostly at opening ([thesis](https://thesis.eur.nl/pub/17284)).
- Also to read: McDonald & Osuji (1995), Agostini & Palmucci (2008), Devaux/Dubé/Apparicio (2017), Dubé et al. (2018).
- **Hypothesis for us:** buy between "credible plan" and "funded". Announcements are noise; budgets and permits are signal.

---

## 3. Leading indicators of growth (feature ideas)

Ordered roughly from earliest/weakest to latest/strongest signal:

1. **Long-range plans**: county Comprehensive Plans, Future Land Use Maps (FLUM), urban service boundary changes, MPO Long Range Transportation Plans (20-yr).
2. **Transportation**: FDOT 5-Year Work Program (funded projects, public), GDOT STIP, ALDOT STIP, new interchanges, toll roads (e.g. Florida's Turnpike extensions, Suncoast Parkway).
3. **Utilities**: water/sewer line extensions. In Florida this is often *the* gate for density. Check utility CIPs.
4. **Big anchors**: Developments of Regional Impact, large master-planned communities (e.g. the Villages, Babcock Ranch, Wellen Park style), new schools (school board siting = strong signal), hospitals, distribution centers, Buc-ee's / Publix land buys.
5. **Rezonings & annexations**: city/county commission agendas, planning board minutes. Annexations mean a city is reaching out.
6. **Permits**: building permit counts by census tract/zip (Census BPS, county portals). Permits moving outward = growth front.
7. **Subdivision plats** filed nearby; homebuilder land purchases (D.R. Horton, Lennar etc. disclose land pipelines in 10-Ks).
8. **Demographics**: Census/ACS population growth, IRS migration data, USPS change-of-address.
9. **Rumors**: local news, Reddit city subs, Facebook groups, Nextdoor. Useful as a *trigger to investigate*, not a feature.

**Negative / risk features** (Florida-specific, important):
- FEMA flood zone, sea-level-rise projections, wetlands (NWI), protected species habitat.
- Insurance cost trajectory (affects buildability demand).
- No road access, no utilities, HOA restrictions, deed restrictions.
- **Pre-platted "paper subdivisions"** (Cape Coral, Port Charlotte, Lehigh Acres, Palm Bay, Citrus Springs, Poinciana): huge lot supply, sold by mail-order decades ago. Supply glut can cap appreciation. Classic trap and classic opportunity.
- Back taxes, liens, impact fees.

---

## 4. Model sketch

Two layers:

**A. Today's value (buy the data, don't build):** comps-based estimate from Land Insights / Land id / BU model.

**B. Growth probability & uplift (what we build):**
- Unit = parcel or ~H3 hex cell.
- Target = P(cell gets "urbanized" within N years) and/or price change over N years.
- Train historically: take snapshots (e.g. 2010 features → 2020 outcome) in FL/GA/AL counties that already grew (Ocala, Lakeland, Wildwood, St. Johns, Pasco, Bryan County GA, Baldwin County AL).
- Features from section 3: distance to growth front, distance to funded road project, sewer distance, permit velocity nearby, FLUM designation, flood risk.
- Models: logistic regression / gradient boosting first. Spatial CA (SLEUTH-like) later if useful.

**Decision rule (hold & sell):**
```
expected_sale = P(growth) * value_if_growth + (1 - P(growth)) * value_if_not
IRR over hold years, minus: property tax, closing costs both sides,
liquidity discount (lots can take months to sell), opportunity cost.
Buy if IRR > hurdle (e.g. 12-15%) AND downside case still ~breakeven.
```

---

## 5. Data sources to check (free first)
- Florida Dept. of Revenue **statewide parcel + sales data** (NAL/SDF files, free, annual). Huge win: real sales for every parcel in Florida.
- County property appraiser sites; GA/AL county assessors (patchier, no statewide equivalent as clean).
- FDOT Work Program, MPO LRTPs, county comp plans.
- Census Building Permits Survey, ACS.
- FEMA NFHL, USFWS NWI wetlands.
- Regrid (paid, but nationwide normalized parcels).

---

## 6. Open questions for us
- Budget per lot? ($5k paper lots vs $50k+ near-path-of-growth acreage are very different games.)
- Hold horizon: 2-3 yrs vs 7-10 yrs?
- Buy at tax deed auctions / direct mail (cheap, high work) vs MLS?
- Start with one region to learn deeply (e.g. Marion/Sumter/Lake, or Pasco/Hernando)?
- Do we want to sell to builders (bulk) or end users (one lot at a time)?

## 7. Next steps (when we stop brainstorming)
1. Locate BU land value repo and IDB tool, read their methods.
2. Read Capozza & Helsley; skim SLEUTH/UrbanSim docs.
3. Pull FL DOR sales file for 2-3 counties; plot lot price over time vs distance to growth.
4. Pick a pilot county.
