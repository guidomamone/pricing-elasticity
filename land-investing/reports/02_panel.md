# 02. Hex panel (T2)

Run: `python -m model.build_panel`. Output: `data/processed/panel.parquet` (not committed).

- Hexes (H3 res 8) touching Marion parcels: **6,533**. Rows: **65,330** (6,533 hexes x 10 origins).
- Parcels over 100 acres split by polygon intersection: 1,029. Homes always go to the representative-point hex.
- Labels: takeoff = 10+ new homes in (T, T+h]. Filled only where T + h <= 2024.

## Check

- Sum of homes_T at T=2019: 166,319. Audit count of homes built by 2019: 166,319. Difference 0.000% (gate 2%).
- Label cells filled where T + h > 2024: 0 (must be 0).

## Rows and takeoff base rate by origin and horizon

Sample = hexes with open_acres_T >= 5 (the model sample). Rate = share with takeoff.

|    T |   hexes |   sample (open>=5 ac) |   open acres |   homes_T | takeoff 5y   | takeoff 10y   | takeoff 15y   |
|-----:|--------:|----------------------:|-------------:|----------:|:-------------|:--------------|:--------------|
| 1985 |    6533 |                  4534 |      557,344 |    60,655 | 8.1% (369)   | 14.8% (673)   | 22.1% (1002)  |
| 1990 |    6533 |                  4527 |      541,732 |    78,960 | 6.3% (286)   | 14.8% (670)   | 22.0% (997)   |
| 1995 |    6533 |                  4510 |      527,947 |    93,180 | 7.3% (330)   | 16.3% (735)   | 22.5% (1017)  |
| 2000 |    6533 |                  4479 |      508,919 |   111,271 | 9.2% (413)   | 15.7% (703)   | 16.7% (747)   |
| 2005 |    6533 |                  4447 |      491,551 |   137,658 | 8.2% (363)   | 9.1% (405)    | 12.1% (537)   |
| 2009 |    6533 |                  4433 |      480,578 |   153,995 | 0.9% (39)    | 4.7% (207)    | 13.1% (581)   |
| 2010 |    6533 |                  4431 |      479,915 |   154,567 | 1.2% (52)    | 6.1% (270)    |               |
| 2014 |    6533 |                  4423 |      477,141 |   156,727 | 4.0% (178)   | 12.4% (549)   |               |
| 2015 |    6533 |                  4421 |      476,337 |   157,676 | 5.3% (235)   |               |               |
| 2019 |    6533 |                  4401 |      470,458 |   166,319 | 10.6% (468)  |               |               |

Distortions (BACKTEST section 2): parcel shapes are today's, so the panel counts acres and homes, never parcels. Demolitions are invisible. 2025 and 2026 are not used for labels. Sales are not used here.
