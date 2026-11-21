# 03. Features (T3)

Run: `python -m model.features`. Output: `data/processed/features.parquet` (65,330 rows, one per hex and origin, not committed). As-of test: `python -m pytest model/test_asof.py`.

No lot count, lot size, assessed value or any feature built from today's parcel shapes or values is used. Parcel shapes enter only through acres, which are conserved when a tract is subdivided.

| Feature | Definition | Latest data year touched |
|---|---|---|
| `homes_T` | homes with ACT_YR_BLT <= T in the hex | T |
| `homes_last5` | homes built in (T-5, T] | T |
| `homes_prev5` | homes built in (T-10, T-5] | T-5 |
| `momentum_ratio` | (homes_last5 + 1) / (homes_prev5 + 1) | T |
| `open_acres_T` | vacant + agricultural + improved-but-built-after-T acres | T |
| `built_acres_T` | improved acres built by T (plus improved parcels with no year) | T |
| `built_share_T` | built / (built + open) | T |
| `excluded_share` | never-developable + other acres / all acres in the hex. Static | 2026 codes |
| `homes_T_r{1,2,5}` | homes_T summed over hexes within k rings, centre excluded | T |
| `homes_last5_r{1,2,5}` | homes_last5 summed over k rings | T |
| `open_acres_r{1,2,5}` | open_acres_T summed over k rings | T |
| `dist_front_km` | km to the nearest hex with 10+ homes built in (T-5, T]. 0 if the hex itself | T |
| `front_move_km` | front distance using (T-10, T-5] minus dist_front_km. Positive = front approaching | T |
| `grav_homes_b{1,2}` | sum over other hexes within 40 km of homes_T / max(d,1)^b | T |
| `grav_last5_b{1,2}` | same with homes_last5 | T |
| `dist_road_km` | km to nearest TIGER primary or secondary road | 2020 (leak for T < 2020) |
| `dist_primary_km` | km to nearest primary road (MTFCC S1100) | 2020 (leak for T < 2020) |
| `dist_i75_km` | km to I-75 (built in Marion in the 1960s, so no practical leak) | 2020 |
| `dist_ocala_km` | km to downtown Ocala (29.187, -82.140) | fixed |
| `dist_border_km` | km from hex centre to the Marion county line | fixed |
| `border_flag` | 1 if within 10 km of the county line | fixed |

## Known leaks in static features

- **Roads are 2020.** A primary or secondary road built after T is visible at T. T5 reports a model without `dist_road_km` and `dist_primary_km` to size this.
- **excluded_share uses 2026 codes.** Land that became a park or a retention area after T looks excluded at T. Small in Marion, where most excluded land is the Ocala National Forest and state land.
- **Edge effect.** Gravity, ring and front features see only Marion. 3,847 of 6,533 hexes have `border_flag` = 1 (T6 fixes this).
## Check: as-of test (`model/test_asof.py`)

Deleting post-2000 parcels would remove land that really was open in 2000, so the test instead turns every parcel built after 2000 back into vacant land with no year and no homes (`erase_future`), and separately scrambles their build years and home counts at random (`scramble_future`). Features at T=2000 must be identical to the real data. A negative control repeats the erase at T=2005, where features must change.

```
$ python -m pytest model/test_asof.py -q -s
erase_future: 85,162 parcels changed, 30 features x 6,533 hexes identical
scramble_future: 85,162 parcels changed, 30 features x 6,533 hexes identical
negative control at 2005, changed features: ['homes_T', 'homes_last5', 'open_acres_T', 'dist_front_km', 'grav_homes_b1']
2 passed in 128.67s
```
