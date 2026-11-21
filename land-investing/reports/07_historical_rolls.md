# 07. Historical tax rolls (T7)

Researched 2026-11-21.

## Answer
**Florida DOR does not publish past years of NAL or SDF files.** Its data portal holds only the current roll year (2026 preliminary and final). Older years, including 2025, are removed. So the 2015 versus reconstruction comparison **could not be done**. Past rolls need a public records request.

## What was checked
| URL | Result |
|---|---|
| https://floridarevenue.com/property/dataportal/Pages/default.aspx | Opened. Folder "Tax Roll Data Files" has NAL, NAP, NAV, SDF and ~NAL-EDR |
| Portal folder `Tax Roll Data Files/NAL` | Opened. Subfolders 2026F and 2026P only |
| Portal folder `Tax Roll Data Files/SDF` | Opened. Subfolders 2026F and 2026P only |
| Portal folders `NAL/2015F`, `NAL/2020F`, `NAL/2025F` | Page loads, 0 files listed |
| `.../NAL/2026F/Marion 52 Final NAL 2026.zip` | Downloaded, 21.0 MB |
| `.../SDF/2026F/Marion 52 Final SDF 2026.zip` | Downloaded, 1.6 MB |
| `.../NAL/2015F/Marion 52 Final NAL 2015.zip` and same for 2025 | HTTP 404 |
| Portal folder `~Public Records` | Opened. Dated subfolders (e.g. `~20261112-1389718`), apparently files delivered for individual public records requests. The one subfolder opened listed no files |
| Portal folder `Databook Historical Data` (1976 to 2015) | Listed, not opened. By name, yearly statewide summary databooks, not parcel files (`UNVERIFIED`) |
| archive.org (Wayback Machine) | Blocked by this environment's network policy. `UNVERIFIED` whether old zips were archived |

## How to get past rolls
1. **Public records request to Florida DOR, Property Tax Oversight**, asking for Marion (county 52) final NAL and SDF files for 2005, 2010, 2015 and 2020. The `~Public Records` folders suggest DOR fulfils these by posting files to the portal. The request channel and any fee are `UNVERIFIED`. Guido should confirm the contact on floridarevenue.com before sending.
2. **Marion County Property Appraiser** may keep past certified rolls. `UNVERIFIED`, not checked.
3. **Start archiving now.** `scripts/fetch_dor_history.py` snapshots the current year's NAL and SDF into `data/raw/dor/` (tested: 2026 downloads, 2015 returns 404). Run it every October after the final roll.

## Sales: what the 2026 SDF adds over the roll
The SDF lists every recorded sale in the roll's sale window, not only two per parcel. The 2026 final SDF covers sales dated 2025 and 2026 (76,873 rows, 70,087 distinct sales, 14,118 rows in multi-parcel sales). The parcel layer we use (`data/raw/marion_parcels.parquet`) was taken from an earlier 2026 roll snapshot, so it is missing most 2026 sales.

| Sale year | SDF: all / vacant / vacant market (01, 02) | Parcel layer: all / vacant / vacant market |
|---|---|---|
| 2025 | 46,351 / 15,251 / 3,558 | 42,121 / 14,072 / 3,533 |
| 2026 | 30,522 / 9,381 / 2,568 | 14,155 / 4,586 / 1,288 |

So one year of SDF gives about 3,500 market vacant-land sales in Marion. Ten past SDF years would give roughly 35,000 dated prices, enough for the Phase 3 price model. Without them, the price side of the plan rests on 2025 and 2026 only.

## Not done
- Vacant parcels in 2015, real roll versus reconstruction: needs the 2015 NAL. Blocked.
- Vacant-land sales per year before 2025: needs past SDF files. Blocked.
