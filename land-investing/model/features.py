"""T3: features per hex and origin year T, strictly as of T (docs/BACKTEST.md section 1).

Run from land-investing/: python -m model.features

Every parcel-derived feature is computed from `stock(m, Y)` or `homes_between(m, lo, hi)` with
Y, hi <= T, so it only reads build years <= T. Static features (roads, Ocala, border) come from
fixed geography and are the same at every T. Roads are TIGER 2020, which is a known leak for early
origins (see reports/03_features.md).
"""
import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial import cKDTree
from shapely.geometry import Point

from model.build_panel import ORIGINS, homes_between, prepare, stock
from model.load import PROCESSED, ROOT

TIGER = ROOT / "data" / "raw" / "tiger"
ROADS_ZIP = TIGER / "tl_2020_12_prisecroads.zip"
BG_ZIP = TIGER / "tl_2020_12_bg.zip"
OCALA = (29.187, -82.140)  # lat, lon of downtown Ocala
RINGS = [1, 2, 5]
GRAVITY_KM = 40
FRONT_MIN_HOMES = 10
BORDER_KM = 10
NO_FRONT_KM = 100.0  # used when no hex at that year has a front

# feature -> (definition, latest data year it touches; "T" means only data dated T or earlier)
DEFS = {}


def hex_geo(hexes: pd.Index) -> pd.DataFrame:
    ll = np.array([h3.cell_to_latlng(c) for c in hexes])
    pts = gpd.GeoSeries(gpd.points_from_xy(ll[:, 1], ll[:, 0]), crs=4326).to_crs(6439)
    return pd.DataFrame({"lat": ll[:, 0], "lon": ll[:, 1], "x_km": pts.x.to_numpy() / 1000,
                         "y_km": pts.y.to_numpy() / 1000}, index=hexes)


def ring_matrix(hexes: pd.Index, k: int) -> sparse.csr_matrix:
    """A[i, j] = 1 if hex j is within k rings of hex i, j != i (both in the panel)."""
    pos = {c: i for i, c in enumerate(hexes)}
    rows, cols = [], []
    for i, c in enumerate(hexes):
        for n in h3.grid_disk(c, k):
            j = pos.get(n)
            if j is not None and j != i:
                rows.append(i)
                cols.append(j)
    n = len(hexes)
    return sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))


def gravity_matrices(xy: np.ndarray) -> dict:
    tree = cKDTree(xy)
    D = tree.sparse_distance_matrix(tree, GRAVITY_KM, output_type="coo_matrix")
    keep = D.row != D.col
    r, c, d = D.row[keep], D.col[keep], np.maximum(D.data[keep], 1.0)
    n = len(xy)
    return {b: sparse.csr_matrix((1 / d ** b, (r, c)), shape=(n, n)) for b in (1, 2)}


def front_distance(xy: np.ndarray, recent: np.ndarray) -> np.ndarray:
    on = recent >= FRONT_MIN_HOMES
    if not on.any():
        return np.full(len(xy), NO_FRONT_KM)
    d, _ = cKDTree(xy[on]).query(xy)
    return d


def static_features(geo: pd.DataFrame) -> pd.DataFrame:
    xy_m = geo[["x_km", "y_km"]].to_numpy() * 1000
    pts = gpd.GeoSeries(gpd.points_from_xy(xy_m[:, 0], xy_m[:, 1]), crs=6439)
    roads = gpd.read_file(ROADS_ZIP).to_crs(6439)
    near = roads.cx[xy_m[:, 0].min() - 60e3:xy_m[:, 0].max() + 60e3,
                    xy_m[:, 1].min() - 60e3:xy_m[:, 1].max() + 60e3]
    all_roads = near.geometry.union_all()
    i75 = roads[roads.FULLNAME == "I- 75"].geometry.union_all()
    primary = near[near.MTFCC == "S1100"].geometry.union_all()
    bg = gpd.read_file(BG_ZIP)
    county = bg[bg.COUNTYFP == "083"].to_crs(6439).geometry.union_all()
    ocala = gpd.GeoSeries([Point(OCALA[1], OCALA[0])], crs=4326).to_crs(6439).iloc[0]
    out = pd.DataFrame(index=geo.index)
    out["dist_road_km"] = pts.distance(all_roads).to_numpy() / 1000
    out["dist_primary_km"] = pts.distance(primary).to_numpy() / 1000
    out["dist_i75_km"] = pts.distance(i75).to_numpy() / 1000
    out["dist_ocala_km"] = pts.distance(ocala).to_numpy() / 1000
    out["dist_border_km"] = pts.distance(county.boundary).to_numpy() / 1000
    out["border_flag"] = (out.dist_border_km <= BORDER_KM).astype(int)
    return out


def compute_features(m: dict, origins=ORIGINS, static: pd.DataFrame | None = None) -> pd.DataFrame:
    hexes = m["hexes"]
    geo = hex_geo(hexes)
    xy = geo[["x_km", "y_km"]].to_numpy()
    rings = {k: ring_matrix(hexes, k) for k in RINGS}
    grav = gravity_matrices(xy)
    out = []
    for T in origins:
        s = stock(m, T)
        last5 = homes_between(m, T - 5, T).to_numpy()
        prev5 = homes_between(m, T - 10, T - 5).to_numpy()
        homes = s.homes.to_numpy()
        open_ = s.open_acres.to_numpy()
        built = s.built_acres.to_numpy()
        excl = s.excluded_acres.to_numpy()
        f = {"hex": hexes, "T": T, "homes_T": homes, "homes_last5": last5, "homes_prev5": prev5,
             "momentum_ratio": (last5 + 1) / (prev5 + 1), "open_acres_T": open_,
             "built_acres_T": built,
             "built_share_T": built / np.maximum(built + open_, 1e-9),
             "excluded_share": excl / np.maximum(built + open_ + excl, 1e-9)}
        for k, A in rings.items():
            f[f"homes_T_r{k}"] = A @ homes
            f[f"homes_last5_r{k}"] = A @ last5
            f[f"open_acres_r{k}"] = A @ open_
        d_now = front_distance(xy, last5)
        d_before = front_distance(xy, prev5)  # front at T-5 = homes built in (T-10, T-5]
        f["dist_front_km"] = d_now
        f["front_move_km"] = d_before - d_now
        for b, G in grav.items():
            f[f"grav_homes_b{b}"] = G @ homes
            f[f"grav_last5_b{b}"] = G @ last5
        out.append(pd.DataFrame(f))
    feats = pd.concat(out, ignore_index=True)
    if static is None:
        static = static_features(geo)
    feats = feats.join(static, on="hex")
    return feats


DEFS.update({
    "homes_T": ("homes with ACT_YR_BLT <= T in the hex", "T"),
    "homes_last5": ("homes built in (T-5, T]", "T"),
    "homes_prev5": ("homes built in (T-10, T-5]", "T-5"),
    "momentum_ratio": ("(homes_last5 + 1) / (homes_prev5 + 1)", "T"),
    "open_acres_T": ("vacant + agricultural + improved-but-built-after-T acres", "T"),
    "built_acres_T": ("improved acres built by T (plus improved parcels with no year)", "T"),
    "built_share_T": ("built / (built + open)", "T"),
    "excluded_share": ("never-developable + other acres / all acres in the hex. Static", "2026 codes"),
    "homes_T_r{1,2,5}": ("homes_T summed over hexes within k rings, centre excluded", "T"),
    "homes_last5_r{1,2,5}": ("homes_last5 summed over k rings", "T"),
    "open_acres_r{1,2,5}": ("open_acres_T summed over k rings", "T"),
    "dist_front_km": ("km to the nearest hex with 10+ homes built in (T-5, T]. 0 if the hex itself", "T"),
    "front_move_km": ("front distance using (T-10, T-5] minus dist_front_km. Positive = front approaching", "T"),
    "grav_homes_b{1,2}": ("sum over other hexes within 40 km of homes_T / max(d,1)^b", "T"),
    "grav_last5_b{1,2}": ("same with homes_last5", "T"),
    "dist_road_km": ("km to nearest TIGER primary or secondary road", "2020 (leak for T < 2020)"),
    "dist_primary_km": ("km to nearest primary road (MTFCC S1100)", "2020 (leak for T < 2020)"),
    "dist_i75_km": ("km to I-75 (built in Marion in the 1960s, so no practical leak)", "2020"),
    "dist_ocala_km": ("km to downtown Ocala (29.187, -82.140)", "fixed"),
    "dist_border_km": ("km from hex centre to the Marion county line", "fixed"),
    "border_flag": ("1 if within 10 km of the county line", "fixed"),
})


def main() -> None:
    m = pd.read_pickle(PROCESSED / "hex_year.pkl") if (PROCESSED / "hex_year.pkl").exists() else prepare()
    feats = compute_features(m)
    feats.to_parquet(PROCESSED / "features.parquet", index=False)
    print(f"features: {feats.shape}")
    print(feats.describe().T[["mean", "min", "max"]].round(2).to_string())
    lines = ["# 03. Features (T3)", "",
             "Run: `python -m model.features`. Output: `data/processed/features.parquet` "
             f"({len(feats):,} rows, one per hex and origin, not committed). As-of test: "
             "`python -m pytest model/test_asof.py`.", "",
             "No lot count, lot size, assessed value or any feature built from today's parcel "
             "shapes or values is used. Parcel shapes enter only through acres, which are "
             "conserved when a tract is subdivided.", "",
             "| Feature | Definition | Latest data year touched |", "|---|---|---|"]
    lines += [f"| `{k}` | {v[0]} | {v[1]} |" for k, v in DEFS.items()]
    lines += ["", "## Known leaks in static features", "",
              "- **Roads are 2020.** A primary or secondary road built after T is visible at T. "
              "T5 reports a model without `dist_road_km` and `dist_primary_km` to size this.",
              "- **excluded_share uses 2026 codes.** Land that became a park or a retention area "
              "after T looks excluded at T. Small in Marion, where most excluded land is the "
              "Ocala National Forest and state land.",
              "- **Edge effect.** Gravity, ring and front features see only Marion. "
              f"{int(feats.loc[feats['T'] == ORIGINS[-1], 'border_flag'].sum()):,} of "
              f"{feats.hex.nunique():,} hexes have `border_flag` = 1 (T6 fixes this).", ""]
    (ROOT / "reports" / "03_features.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
