"""Build the population growth layer for Marion County, FL (block groups).

Sources (no API key needed for light use; set CENSUS_API_KEY to raise limits):
- 2020 Decennial PL 94-171: P1_001N total population
- ACS 5-year (latest, default 2024): B01003 population, B19013 median household income,
  B25077 median home value. ACS 2020+ uses 2020 block group boundaries, so it joins cleanly.
- TIGER/Line 2020 block group shapes for Florida.

Output: map/data/population.geojson
Run from land-investing/:  python scripts/build_population.py [--acs-year 2024]
"""
import argparse
import io
import os
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

STATE, COUNTY = "12", "083"  # Florida, Marion
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "map" / "data" / "population.geojson"
TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER2020/BG/tl_2020_12_bg.zip"


def census(dataset: str, variables: list[str]) -> pd.DataFrame:
    params = {
        "get": ",".join(variables),
        "for": "block group:*",
        "in": f"state:{STATE} county:{COUNTY} tract:*",
    }
    if key := os.environ.get("CENSUS_API_KEY"):
        params["key"] = key
    r = requests.get(f"https://api.census.gov/data/{dataset}", params=params, timeout=60)
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"] + df["block group"]
    for v in variables:
        df[v] = pd.to_numeric(df[v], errors="coerce")
        # Census uses large negative sentinels for "not available"
        df.loc[df[v] < 0, v] = pd.NA
    return df[["GEOID", *variables]]


def block_groups() -> gpd.GeoDataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    zpath = RAW / "tl_2020_12_bg.zip"
    if not zpath.exists():
        r = requests.get(TIGER_URL, timeout=300)
        r.raise_for_status()
        zpath.write_bytes(r.content)
    gdf = gpd.read_file(f"zip://{zpath}")
    return gdf[gdf["COUNTYFP"] == COUNTY][["GEOID", "ALAND", "geometry"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--acs-year", type=int, default=2024)
    args = ap.parse_args()

    dec = census("2020/dec/pl", ["P1_001N"]).rename(columns={"P1_001N": "pop_2020"})
    acs = census(
        f"{args.acs_year}/acs/acs5",
        ["B01003_001E", "B19013_001E", "B25077_001E"],
    ).rename(columns={
        "B01003_001E": "pop_acs",
        "B19013_001E": "median_income",
        "B25077_001E": "median_home_value",
    })

    gdf = block_groups().merge(dec, on="GEOID", how="left").merge(acs, on="GEOID", how="left")
    km2 = gdf["ALAND"] / 1e6
    gdf["density_km2"] = (gdf["pop_acs"] / km2).round(1)
    gdf["pop_change"] = gdf["pop_acs"] - gdf["pop_2020"]
    gdf["pop_change_pct"] = (100 * gdf["pop_change"] / gdf["pop_2020"]).round(1)
    gdf["added_per_km2"] = (gdf["pop_change"] / km2).round(1)
    gdf["acs_year"] = args.acs_year
    gdf = gdf.drop(columns="ALAND").to_crs(4326)
    gdf["geometry"] = gdf.geometry.simplify(0.0002, preserve_topology=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT, driver="GeoJSON")
    print(f"wrote {len(gdf)} block groups -> {OUT}")
    print(gdf[["pop_2020", "pop_acs", "pop_change"]].sum().to_string())


if __name__ == "__main__":
    main()
