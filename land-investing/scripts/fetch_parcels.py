"""Download Marion County parcels from the Florida Statewide Cadastral layer (FL DOR tax roll + polygons).

Source: https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0
CO_NO is the DOR county number (Marion = 52, not the FIPS code).
Output: data/raw/marion_parcels.parquet (GeoParquet, EPSG:4326)
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

URL = ("https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
       "Florida_Statewide_Cadastral/FeatureServer/0/query")
CO_NO = 52
FIELDS = ["PARCEL_ID", "ASMNT_YR", "DOR_UC", "JV", "LND_VAL", "LND_SQFOOT", "ACT_YR_BLT",
          "EFF_YR_BLT", "NO_BULDNG", "NO_RES_UNT", "TOT_LVG_AR",
          "SALE_PRC1", "SALE_YR1", "SALE_MO1", "QUAL_CD1", "VI_CD1",
          "SALE_PRC2", "SALE_YR2", "SALE_MO2", "QUAL_CD2", "VI_CD2",
          "OWN_NAME", "PHY_ADDR1", "PHY_CITY", "PHY_ZIPCD", "Shape__Area"]
PAGE = 2000
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "marion_parcels.parquet"


def page(offset: int) -> gpd.GeoDataFrame:
    params = {"where": f"CO_NO={CO_NO}", "outFields": ",".join(FIELDS), "outSR": 4326,
              "geometryPrecision": 6, "orderByFields": "OBJECTID", "resultOffset": offset,
              "resultRecordCount": PAGE, "f": "geojson"}
    for attempt in range(4):
        try:
            r = requests.get(URL, params=params, timeout=120)
            r.raise_for_status()
            return gpd.read_file(r.text)
        except Exception:
            if attempt == 3:
                raise


def main() -> None:
    n = requests.get(URL, params={"where": f"CO_NO={CO_NO}", "returnCountOnly": "true",
                                  "f": "json"}, timeout=60).json()["count"]
    with ThreadPoolExecutor(8) as ex:
        parts = list(ex.map(page, range(0, n, PAGE)))
    gdf = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(OUT)
    print(f"expected {n}, got {len(gdf)} parcels -> {OUT}")


if __name__ == "__main__":
    main()
