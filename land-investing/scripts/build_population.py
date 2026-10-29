"""Build the population growth layer for Marion County, FL (block groups).

Uses Census bulk files from www2.census.gov (the Census API now requires a key):
- 2020 Decennial PL 94-171 Florida file: P1 total population.
- ACS 5-year table-based summary files (default 2024): B01003 population,
  B19013 median household income, B25077 median home value. ACS 2020+ uses
  2020 block group boundaries, so it joins cleanly with the decennial data.
- TIGER/Line 2020 block group shapes for Florida.

Output: map/data/population.geojson
Run from land-investing/:  python scripts/build_population.py [--acs-year 2024]
"""
import argparse
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
PL_URL = ("https://www2.census.gov/programs-surveys/decennial/2020/data/"
          "01-Redistricting_File--PL_94-171/Florida/fl2020.pl.zip")
ACS_URL = ("https://www2.census.gov/programs-surveys/acs/summary_file/{y}/"
           "table-based-SF/data/5YRData/acsdt5y{y}-{t}.dat")
PREFIX = STATE + COUNTY


def download(url: str) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / url.rsplit("/", 1)[1]
    if not path.exists():
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return path


def decennial_pop() -> pd.DataFrame:
    """P1_001N per Marion block group, joining the PL geo file to segment 1 by LOGRECNO."""
    logrec = {}
    with zipfile.ZipFile(download(PL_URL)) as z:
        with z.open("flgeo2020.pl") as f:
            for line in f:
                c = line.decode("latin-1").split("|")
                if c[2] == "150" and c[9].startswith(PREFIX):  # SUMLEV 150 = block group
                    logrec[c[7]] = c[9]
        rows = []
        with z.open("fl000012020.pl") as f:
            for line in f:
                c = line.decode("latin-1").split("|")
                if c[4] in logrec:
                    rows.append((logrec[c[4]], int(c[5])))
    return pd.DataFrame(rows, columns=["GEOID", "pop_2020"])


def acs(year: int, table: str, name: str) -> pd.DataFrame:
    df = pd.read_csv(download(ACS_URL.format(y=year, t=table)), sep="|", dtype=str,
                     usecols=["GEO_ID", f"{table.upper()}_E001"])
    df = df[df["GEO_ID"].str.startswith("1500000US" + PREFIX)]
    df["GEOID"] = df["GEO_ID"].str[9:]
    v = pd.to_numeric(df[f"{table.upper()}_E001"], errors="coerce")
    df[name] = v.where(v >= 0)  # negative values are "not available" sentinels
    return df[["GEOID", name]]


# B25034 year structure built (ACS 2022+ layout): E002 = 2020 or later, E003 = 2010s, ...
DECADES = {"2020": "E002", "2010": "E003", "2000": "E004", "1990": "E005", "1980": "E006"}


def year_built(year: int) -> pd.DataFrame:
    df = pd.read_csv(download(ACS_URL.format(y=year, t="b25034")), sep="|", dtype=str)
    df = df[df["GEO_ID"].str.startswith("1500000US" + PREFIX)].copy()
    out = pd.DataFrame({"GEOID": df["GEO_ID"].str[9:]})
    out["units"] = pd.to_numeric(df["B25034_E001"]).values
    for dec, col in DECADES.items():
        out[f"built_{dec}"] = pd.to_numeric(df[f"B25034_{col}"]).values
    return out


def block_groups() -> gpd.GeoDataFrame:
    zpath = download(TIGER_URL)
    gdf = gpd.read_file(f"zip://{zpath}")
    return gdf[gdf["COUNTYFP"] == COUNTY][["GEOID", "ALAND", "geometry"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--acs-year", type=int, default=2024)
    args = ap.parse_args()

    gdf = block_groups().merge(decennial_pop(), on="GEOID", how="left")
    for table, name in [("b01003", "pop_acs"), ("b19013", "median_income"),
                        ("b25077", "median_home_value")]:
        gdf = gdf.merge(acs(args.acs_year, table, name), on="GEOID", how="left")
    gdf = gdf.merge(year_built(args.acs_year), on="GEOID", how="left")
    km2 = gdf["ALAND"] / 1e6
    for dec in DECADES:
        gdf[f"built_{dec}_km2"] = (gdf[f"built_{dec}"] / km2).round(1)
    gdf["pct_built_2010plus"] = (100 * (gdf["built_2020"] + gdf["built_2010"]) / gdf["units"]).round(1)
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
