"""T1 audit: parcels and acres per code group, missing build years, homes built per year.

Run from land-investing/: python -m model.audit
"""
import pandas as pd

from model.codes import IMPROVED, RESIDENTIAL
from model.load import RAW, load_parcels


def main() -> None:
    raw_rows = len(pd.read_parquet(RAW, columns=["PARCEL_ID"]))
    d = load_parcels()
    print(f"raw rows {raw_rows:,}, unique parcels {len(d):,}, total acres {d.acres.sum():,.0f}\n")

    g = d.groupby("group").agg(parcels=("PARCEL_ID", "size"), acres=("acres", "sum"))
    g["acre_share"] = g.acres / g.acres.sum()
    print("## Parcels and acres per code group")
    print(g.sort_values("acres", ascending=False).to_markdown(floatfmt=",.3f"))
    covered = g.drop(index="unknown", errors="ignore").acres.sum() / g.acres.sum()
    print(f"\nacre coverage by named groups: {covered:.4%}\n")

    top = d.groupby(["group", "uc"]).agg(parcels=("PARCEL_ID", "size"), acres=("acres", "sum"))
    print("## Top 25 codes by acres")
    print(top.sort_values("acres", ascending=False).head(25).to_markdown(floatfmt=",.0f"))

    imp = d[d.uc.isin(IMPROVED)]
    miss = ~imp.has_year
    print("\n## Improved parcels with missing or zero ACT_YR_BLT")
    print(f"all improved: {miss.sum():,} of {len(imp):,} ({miss.mean():.2%})")
    res = imp[imp.uc.isin(RESIDENTIAL)]
    print(f"residential: {(~res.has_year).sum():,} of {len(res):,} ({(~res.has_year).mean():.2%})")
    print(f"homes on residential parcels with no year: {res.loc[~res.has_year, 'homes'].sum():,}")
    print((imp[miss].groupby("uc").size().sort_values(ascending=False).head(10)
           .rename("parcels").to_markdown()))

    built = d[d.has_year & (d.homes > 0)]
    per = built.groupby("yr_built").homes.sum()
    print("\n## Homes built per year, 1980 to 2026 (sum of homes, by ACT_YR_BLT)")
    t = per.loc[1980:2026].rename("homes").to_frame()
    t["cumulative_all_years"] = per.cumsum().loc[1980:2026]
    print(t.to_markdown())
    print(f"\nhomes with a build year, all years: {built.homes.sum():,}")


if __name__ == "__main__":
    main()
