"""T2: hex panel. One row per H3 resolution 8 hex and origin year T.

Run from land-investing/: python -m model.build_panel

Allocation: parcels up to 100 acres go wholly to the hex of their representative point. Larger
parcels split their acres across hexes by polygon intersection. Homes always go to the hex of the
parcel's representative point (a farm's one house should not be spread over a 400 acre tract).

Per hex and year Y the stock is rebuilt from ACT_YR_BLT:
- built acres: improved parcels with a build year <= Y, plus improved parcels with no build year
  (326 parcels, 0.18%, counted as built at every Y so they never look open).
- open acres: vacant + agricultural + improved parcels built after Y.
- excluded acres: never developable + other (mining, leaseholds, subsurface).
"""
import sys

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from model.codes import LAST_FULL_YEAR
from model.load import PROCESSED, ROOT, load_parcels

RES = 8
BIG_ACRES = 100
ORIGINS = [1985, 1990, 1995, 2000, 2005, 2009, 2010, 2014, 2015, 2019]
HORIZONS = [5, 10, 15]
TAKEOFF = 10
YEARS = np.arange(1900, 2027)  # matrix columns; build years before 1900 are folded into 1900


def hex_polygon(c: str) -> Polygon:
    return Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)])


def allocate(p: gpd.GeoDataFrame) -> pd.DataFrame:
    """Rows: parcel index, hex, acre share. Shares per parcel sum to 1."""
    pts = p.geometry.representative_point().to_crs(4326)
    p = p.assign(hex_pt=[h3.latlng_to_cell(y, x, RES) for x, y in zip(pts.x, pts.y)])
    small = p[p.acres <= BIG_ACRES]
    rows = [pd.DataFrame({"pidx": small.index, "hex": small.hex_pt, "share": 1.0})]

    big = p[p.acres > BIG_ACRES]
    if len(big):
        big4326 = big.to_crs(4326)
        cand = set()
        for geom in big4326.geometry:
            for part in getattr(geom, "geoms", [geom]):
                if part.geom_type != "Polygon":
                    continue
                cells = h3.geo_to_cells(part.buffer(0.01), RES)  # ~1 km pad so edges are covered
                cand.update(cells)
        cand = sorted(cand)
        hexes = gpd.GeoDataFrame({"hex": cand}, geometry=[hex_polygon(c) for c in cand], crs=4326)
        ov = gpd.overlay(big[["geometry"]].reset_index(names="pidx"), hexes.to_crs(p.crs),
                         how="intersection", keep_geom_type=True)
        ov["a"] = ov.geometry.area
        ov["share"] = ov.a / ov.groupby("pidx").a.transform("sum")
        rows.append(ov[["pidx", "hex", "share"]])
    alloc = pd.concat(rows, ignore_index=True)
    alloc = alloc[alloc.share > 1e-6]
    return alloc, p["hex_pt"]


def hex_year_matrices(p: pd.DataFrame, alloc: pd.DataFrame, hex_pt: pd.Series) -> dict:
    """Per hex: homes built each year, improved acres built each year, and fixed acre totals."""
    yr = p["yr_built"].clip(lower=YEARS[0])
    a = alloc.join(p[["group", "acres"]], on="pidx")
    a["ac"] = a.share * a.acres
    a["yr"] = yr.reindex(a.pidx).to_numpy()
    a["has_year"] = p["has_year"].reindex(a.pidx).to_numpy()
    hexes = pd.Index(sorted(set(a.hex) | set(hex_pt)), name="hex")

    def by_year(df, val):
        m = df.pivot_table(index="hex", columns="yr", values=val, aggfunc="sum", fill_value=0)
        return m.reindex(index=hexes, columns=YEARS, fill_value=0)

    imp = a[a.group == "improved"]
    built_ac_yr = by_year(imp[imp.has_year], "ac")
    fixed = a.groupby(["hex", "group"]).ac.sum().unstack(fill_value=0).reindex(hexes, fill_value=0)
    for g in ["vacant", "agricultural", "never_developable", "other", "improved"]:
        if g not in fixed:
            fixed[g] = 0.0
    no_year_imp = imp[~imp.has_year].groupby("hex").ac.sum().reindex(hexes, fill_value=0)

    h = pd.DataFrame({"hex": hex_pt, "homes": p["homes"], "yr": yr, "has_year": p["has_year"]})
    h = h[h.has_year & (h.homes > 0)]
    homes_yr = by_year(h, "homes")
    return {"hexes": hexes, "homes_yr": homes_yr, "built_ac_yr": built_ac_yr, "fixed": fixed,
            "no_year_imp": no_year_imp}


def stock(m: dict, year: int) -> pd.DataFrame:
    """Stock per hex as of the end of `year`. Uses only build years <= year."""
    cols = m["homes_yr"].columns
    upto = cols <= year
    f = m["fixed"]
    homes = m["homes_yr"].loc[:, upto].sum(axis=1)
    built_imp = m["built_ac_yr"].loc[:, upto].sum(axis=1)
    built = built_imp + m["no_year_imp"]
    open_ = f["vacant"] + f["agricultural"] + (f["improved"] - built).clip(lower=0)
    return pd.DataFrame({"homes": homes, "built_acres": built, "open_acres": open_,
                         "excluded_acres": f["never_developable"] + f["other"]})


def homes_between(m: dict, lo: int, hi: int) -> pd.Series:
    """Homes built in (lo, hi]."""
    c = m["homes_yr"].columns
    return m["homes_yr"].loc[:, (c > lo) & (c <= hi)].sum(axis=1)


def build_panel(m: dict, origins=ORIGINS, last_full_year=LAST_FULL_YEAR) -> pd.DataFrame:
    out = []
    for T in origins:
        s = stock(m, T)
        df = pd.DataFrame({"hex": m["hexes"], "T": T,
                           "homes_T": s.homes.to_numpy(), "built_acres_T": s.built_acres.to_numpy(),
                           "open_acres_T": s.open_acres.to_numpy(),
                           "excluded_acres": s.excluded_acres.to_numpy(),
                           "homes_last5": homes_between(m, T - 5, T).to_numpy(),
                           "homes_prev5": homes_between(m, T - 10, T - 5).to_numpy()})
        for h in HORIZONS:
            if T + h <= last_full_year:
                nh = homes_between(m, T, T + h).to_numpy()
                df[f"new_homes_{h}"] = nh.astype(float)
                df[f"takeoff_{h}"] = (nh >= TAKEOFF).astype(float)
            else:
                df[f"new_homes_{h}"] = np.nan
                df[f"takeoff_{h}"] = np.nan
        out.append(df)
    return pd.concat(out, ignore_index=True)


def prepare(parcels: gpd.GeoDataFrame | None = None) -> dict:
    p = load_parcels() if parcels is None else parcels
    alloc, hex_pt = allocate(p)
    return hex_year_matrices(p, alloc, hex_pt)


def main() -> None:
    p = load_parcels()
    alloc, hex_pt = allocate(p)
    print(f"parcels {len(p):,}, split parcels (>{BIG_ACRES} ac) {(p.acres > BIG_ACRES).sum():,}, "
          f"allocation rows {len(alloc):,}")
    acre_err = abs(alloc.join(p.acres, on="pidx").eval("share*acres").sum() - p.acres.sum())
    print(f"acres lost in allocation: {acre_err:,.2f}")
    m = hex_year_matrices(p, alloc, hex_pt)
    panel = build_panel(m)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PROCESSED / "panel.parquet", index=False)
    pd.to_pickle(m, PROCESSED / "hex_year.pkl")
    pd.DataFrame({"hex": hex_pt}).to_parquet(PROCESSED / "parcel_hex.parquet")
    report(panel, p)


def report(panel: pd.DataFrame, p: pd.DataFrame) -> None:
    n_hex = panel.hex.nunique()
    lines = ["# 02. Hex panel (T2)", "",
             "Run: `python -m model.build_panel`. Output: `data/processed/panel.parquet` "
             "(not committed).", "",
             f"- Hexes (H3 res {RES}) touching Marion parcels: **{n_hex:,}**. "
             f"Rows: **{len(panel):,}** ({n_hex:,} hexes x {len(ORIGINS)} origins).",
             f"- Parcels over {BIG_ACRES} acres split by polygon intersection: "
             f"{(p.acres > BIG_ACRES).sum():,}. Homes always go to the representative-point hex.",
             f"- Labels: takeoff = {TAKEOFF}+ new homes in (T, T+h]. Filled only where "
             f"T + h <= {LAST_FULL_YEAR}.", ""]

    # check 1: homes_T at latest origin vs audit cumulative count
    T = max(ORIGINS)
    built = p[p.has_year & (p.homes > 0)]
    audit = built.loc[built.yr_built <= T, "homes"].sum()
    got = panel.loc[panel["T"] == T, "homes_T"].sum()
    lines += ["## Check", "",
              f"- Sum of homes_T at T={T}: {got:,.0f}. Audit count of homes built by {T}: "
              f"{audit:,}. Difference {abs(got - audit) / audit:.3%} (gate 2%).",
              ]
    bad = 0
    for h in HORIZONS:
        late = panel["T"] + h > LAST_FULL_YEAR
        bad += panel.loc[late, [f"new_homes_{h}", f"takeoff_{h}"]].notna().sum().sum()
    lines += [f"- Label cells filled where T + h > {LAST_FULL_YEAR}: {bad} (must be 0).", ""]
    assert abs(got - audit) / audit < 0.02 and bad == 0

    lines += ["## Rows and takeoff base rate by origin and horizon", "",
              "Sample = hexes with open_acres_T >= 5 (the model sample). Rate = share with takeoff.",
              ""]
    rows = []
    for T, g in panel.groupby("T"):
        s = g[g.open_acres_T >= 5]
        r = {"T": T, "hexes": len(g), "sample (open>=5 ac)": len(s),
             "open acres": f"{g.open_acres_T.sum():,.0f}", "homes_T": f"{g.homes_T.sum():,.0f}"}
        for h in HORIZONS:
            col = s[f"takeoff_{h}"]
            r[f"takeoff {h}y"] = f"{col.mean():.1%} ({int(col.sum())})" if col.notna().any() else ""
        rows.append(r)
    lines.append(pd.DataFrame(rows).to_markdown(index=False))
    lines += ["", "Distortions (BACKTEST section 2): parcel shapes are today's, so the panel counts "
              "acres and homes, never parcels. Demolitions are invisible. 2025 and 2026 are not "
              "used for labels. Sales are not used here."]
    (ROOT / "reports" / "02_panel.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
