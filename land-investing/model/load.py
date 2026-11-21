"""Shared parcel loader. One row per PARCEL_ID, projected to EPSG:6439 (meters).

The cadastral layer stores some parcels as several polygon pieces with the same PARCEL_ID and
identical attributes (mostly government land). They are dissolved here so homes and acres are
counted once.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from model.codes import GROUPS, RESIDENTIAL, group_of

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "marion_parcels.parquet"
PROCESSED = ROOT / "data" / "processed"
M2_PER_ACRE = 4046.86


def load_parcels(path: Path = RAW) -> gpd.GeoDataFrame:
    d = gpd.read_parquet(path)
    d["geometry"] = d.geometry.make_valid()
    if d.PARCEL_ID.duplicated().any():
        geom = d.dissolve("PARCEL_ID").geometry
        d = d.drop_duplicates("PARCEL_ID").set_index("PARCEL_ID")
        d["geometry"] = geom
        d = d.reset_index()
    d = d.to_crs(6439)
    d["uc"] = d["DOR_UC"].astype(str).str.zfill(3)
    d["group"] = d["uc"].map(group_of)
    d["acres"] = d.geometry.area / M2_PER_ACRE
    yr = pd.to_numeric(d["ACT_YR_BLT"], errors="coerce").fillna(0).astype(int)
    d["yr_built"] = yr.where(yr > 1800, 0)  # 0 = no building year
    units = pd.to_numeric(d["NO_RES_UNT"], errors="coerce").fillna(0).clip(lower=0)
    d["homes"] = np.where(d["uc"].isin(RESIDENTIAL), units.clip(lower=1), units).astype(int)
    d["has_year"] = d["yr_built"] > 0
    return d


__all__ = ["load_parcels", "GROUPS", "ROOT", "PROCESSED", "M2_PER_ACRE"]
