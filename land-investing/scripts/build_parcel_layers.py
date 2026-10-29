"""Build compact map layers from data/raw/marion_parcels.parquet (run fetch_parcels.py first).

- map/data/growth.json: one row per parcel with a building, [lon, lat, year_built], built 1980+.
  Year built is the oldest building's actual year, so redeveloped parcels show their first build.
- map/data/vacant.json: vacant parcels (DOR use codes 000, 010, 040, 070) with value and last sale.
Rows are arrays (not GeoJSON) to keep the files small; the map turns them into features.
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "marion_parcels.parquet"
OUT = ROOT / "map" / "data"
VACANT = {"000": "Vacant residential", "010": "Vacant commercial",
          "040": "Vacant industrial", "070": "Vacant institutional"}


def main() -> None:
    d = gpd.read_parquet(SRC)
    d["uc"] = d["DOR_UC"].astype(str).str.zfill(3)
    pts = d.geometry.to_crs(6439).representative_point().to_crs(4326)  # Florida GDL Albers (meters), point inside polygon
    d["lon"], d["lat"] = pts.x.round(5), pts.y.round(5)
    d["acres"] = (d.geometry.to_crs(6439).area / 4046.86).round(2)  # m2 -> acres

    yr = pd.to_numeric(d["ACT_YR_BLT"], errors="coerce")
    g = d[yr >= 1980]
    growth = [[r.lon, r.lat, int(y)] for r, y in zip(g.itertuples(), yr[yr >= 1980])]
    (OUT / "growth.json").write_text(json.dumps(growth, separators=(",", ":")))

    for c in ["JV", "SALE_PRC1", "SALE_YR1", "SALE_MO1", "SALE_PRC2", "SALE_YR2"]:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype(int)
    v = d[d["uc"].isin(VACANT)]
    rows = []
    for r in v.itertuples():
        price, year = r.SALE_PRC1, r.SALE_YR1
        rows.append([r.lon, r.lat, r.acres, r.JV, price, year, r.SALE_MO1,
                     str(r.QUAL_CD1 or "").strip(), r.uc, r.PARCEL_ID, (r.PHY_ADDR1 or "").strip(),
                     r.SALE_PRC2, r.SALE_YR2])
    cols = ["lon", "lat", "acres", "jv", "sale1", "sale1_yr", "sale1_mo", "qual1", "uc",
            "parcel_id", "addr", "sale2", "sale2_yr"]
    (OUT / "vacant.json").write_text(json.dumps({"cols": cols, "rows": rows}, separators=(",", ":")))

    print(f"growth points: {len(growth)}   vacant parcels: {len(rows)}")
    print(v["uc"].map(VACANT).value_counts().to_string())
    s = v[(v.SALE_PRC1 > 1000) & (v.SALE_YR1 >= 2023) & (v.uc == "000")]
    ppa = s.SALE_PRC1 / s.acres.clip(lower=0.05)
    print(f"vacant residential sales 2023+ over $1k: {len(s)}, median price ${s.SALE_PRC1.median():,.0f},"
          f" median acres {s.acres.median()}, median $/acre ${ppa.median():,.0f}")
    print("QUAL_CD1 values on those sales:", s.QUAL_CD1.value_counts().head(8).to_dict())


if __name__ == "__main__":
    main()
