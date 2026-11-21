# 01. Data audit (T1)

Run: `python -m model.audit` on `data/raw/marion_parcels.parquet` (Florida Statewide Cadastral, 2026 roll, downloaded 2026-11-21).

## Source for the codes
Florida DOR, *2026 NAL, SDF and NAP Users Guide*, opened and read 2026-11-21:
https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/User%20Guides/2026%20Users%20guide%20and%20quick%20reference/2026_NAL_SDF_NAP_Users_Guide.pdf
Land use codes: field 8 (DOR_UC), pages 5 to 7. Sale qualification codes: field 55 (QUAL_CD1), pages 17 to 18. The codes are verified, not `UNVERIFIED`.

## Code groups (`model/codes.py`)
| Group | Codes | Meaning |
|---|---|---|
| VACANT | 000, 010, 040, 070, 099 | Vacant residential, commercial, industrial, institutional, and non-ag acreage |
| AGRICULTURAL | 050 to 069 | Open land at every T, even with a farmhouse |
| NEVER_DEVELOPABLE | 009, 076, 080 to 089, 091, 094 to 098 | Common areas, cemeteries, government incl. forests and parks, utilities, rights of way, water, marsh and waste land, classified parkland, centrally assessed |
| OTHER | 090, 092, 093 | Government leaseholds, mining, subsurface rights. Neither open nor built |
| IMPROVED | everything else in 000 to 099 | Built uses |
| MARKET_QUAL (sales) | 01, 02 | "Qualified and included in sales ratio analysis". 03 to 06 are arm's length but the price does not match the parcel as rolled |

The groups partition all 100 codes, so coverage is 100% of acres (gate: 99%).

## Check
- **Total parcels: 286,216 rows, not 286,275.** The layer was re-queried today and its own count for CO_NO=52 is 286,216, so the layer changed since Phase 0. Not a download loss.
- **269 parcel IDs appear more than once (345 rows).** They are multipart parcels stored as separate polygon pieces with identical attributes (mostly federal and state land). `model/load.py` dissolves them, giving **285,947 unique parcels**. All counts below are per unique parcel.
- 93 invalid polygons repaired with `make_valid`.

## Last complete year
2026 has 0 homes (the roll is dated 1 January 2026). 2025 has 7,554, 3.5% below 2024 (7,825). That is not a sharp drop, but homes under construction at 1 January 2026 are missing from 2025 and will be added by later rolls, so 2025 cannot be shown complete. **`LAST_FULL_YEAR = 2024`**, the BACKTEST default. No window in the split table ends after 2024, so this choice changes nothing in T4 and T5.

## Finding on sales (changes the plan)
Every sale in this roll is dated 2025 or 2026 (SALE_YR1 min 2025, SALE_YR2 min 2025). The NAL sale fields hold only sales in the roll's sale-qualification window, not the last two sales in a parcel's history. So **the current roll has no historical prices at all.** The "price check" in BACKTEST section 7 cannot be done from it, and the STATUS note "only the last two sales per parcel" was wrong. Historical prices need past SDF files (T7).
Sale code counts (sale 1): blank 241,340, 11 (quit claim, tax deed etc.) 18,889, **01: 16,745, 02: 2,719**, 05 (multi-parcel) 2,549, 30 (relatives) 1,675. Vacant-land sales (VI_CD1 = V): 14,270.

## Tables
raw rows 286,216, unique parcels 285,947, total acres 1,023,876

## Parcels and acres per code group
| group             |     parcels |       acres |   acre_share |
|:------------------|------------:|------------:|-------------:|
| never_developable |  10,452.000 | 410,717.255 |        0.401 |
| agricultural      |  11,188.000 | 379,367.812 |        0.371 |
| improved          | 180,323.000 | 157,876.233 |        0.154 |
| vacant            |  83,760.000 |  74,088.723 |        0.072 |
| other             |     224.000 |   1,825.923 |        0.002 |

acre coverage by named groups: 100.0000%

## Top 25 codes by acres
|                              |   parcels |   acres |
|:-----------------------------|----------:|--------:|
| ('never_developable', '088') |       292 | 272,418 |
| ('never_developable', '087') |     1,146 |  98,699 |
| ('agricultural', '063')      |     3,827 |  95,300 |
| ('improved', '001')          |   143,116 |  90,098 |
| ('agricultural', '062')      |     2,583 |  89,598 |
| ('agricultural', '055')      |       349 |  46,324 |
| ('vacant', '000')            |    78,420 |  42,305 |
| ('agricultural', '053')      |     1,377 |  31,285 |
| ('agricultural', '057')      |       705 |  30,920 |
| ('agricultural', '056')      |       613 |  30,294 |
| ('improved', '002')          |    24,630 |  30,204 |
| ('vacant', '099')            |     1,630 |  24,963 |
| ('agricultural', '058')      |       333 |  18,303 |
| ('agricultural', '064')      |       436 |  15,753 |
| ('improved', '008')          |     3,811 |  10,780 |
| ('never_developable', '082') |        34 |   9,609 |
| ('never_developable', '009') |     2,552 |   8,092 |
| ('never_developable', '086') |     3,544 |   8,076 |
| ('agricultural', '065')      |       236 |   5,736 |
| ('never_developable', '089') |       945 |   5,389 |
| ('vacant', '010')            |     3,276 |   5,231 |
| ('improved', '038')          |        40 |   4,776 |
| ('agricultural', '051')      |       128 |   4,616 |
| ('agricultural', '069')      |       244 |   4,528 |
| ('agricultural', '052')      |       208 |   4,283 |

## Improved parcels with missing or zero ACT_YR_BLT
all improved: 326 of 180,323 (0.18%)
residential: 34 of 174,266 (0.02%)
homes on residential parcels with no year: 34
|   uc |   parcels |
|-----:|----------:|
|  028 |       171 |
|  002 |        26 |
|  017 |        26 |
|  018 |        14 |
|  027 |        14 |
|  049 |        12 |
|  019 |        10 |
|  038 |         8 |
|  036 |         7 |
|  048 |         6 |

## Homes built per year, 1980 to 2026 (sum of homes, by ACT_YR_BLT)
|   yr_built |   homes |   cumulative_all_years |
|-----------:|--------:|-----------------------:|
|       1980 |    3450 |                  42671 |
|       1981 |    3259 |                  45930 |
|       1982 |    2889 |                  48819 |
|       1983 |    3420 |                  52239 |
|       1984 |    4360 |                  56599 |
|       1985 |    4056 |                  60655 |
|       1986 |    3769 |                  64424 |
|       1987 |    3741 |                  68165 |
|       1988 |    3510 |                  71675 |
|       1989 |    3684 |                  75359 |
|       1990 |    3601 |                  78960 |
|       1991 |    2729 |                  81689 |
|       1992 |    2510 |                  84199 |
|       1993 |    2742 |                  86941 |
|       1994 |    3278 |                  90219 |
|       1995 |    2961 |                  93180 |
|       1996 |    3052 |                  96232 |
|       1997 |    3777 |                 100009 |
|       1998 |    4408 |                 104417 |
|       1999 |    3698 |                 108115 |
|       2000 |    3156 |                 111271 |
|       2001 |    3528 |                 114799 |
|       2002 |    4949 |                 119748 |
|       2003 |    6106 |                 125854 |
|       2004 |    5494 |                 131348 |
|       2005 |    6310 |                 137658 |
|       2006 |    8403 |                 146061 |
|       2007 |    5327 |                 151388 |
|       2008 |    1931 |                 153319 |
|       2009 |     676 |                 153995 |
|       2010 |     572 |                 154567 |
|       2011 |     396 |                 154963 |
|       2012 |     424 |                 155387 |
|       2013 |     615 |                 156002 |
|       2014 |     725 |                 156727 |
|       2015 |     949 |                 157676 |
|       2016 |    1466 |                 159142 |
|       2017 |    1626 |                 160768 |
|       2018 |    2741 |                 163509 |
|       2019 |    2810 |                 166319 |
|       2020 |    3282 |                 169601 |
|       2021 |    4038 |                 173639 |
|       2022 |    5714 |                 179353 |
|       2023 |    8283 |                 187636 |
|       2024 |    7825 |                 195461 |
|       2025 |    7554 |                 203015 |

homes with a build year, all years: 203,015
