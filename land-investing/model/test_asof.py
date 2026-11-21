"""T3 check: features for T=2000 must not change when everything after 2000 is erased or scrambled.

Run from land-investing/: python -m pytest model/test_asof.py -q

Why "erase" and not "delete": a parcel built in 2010 was open land in 2000. Deleting it would
remove real open acres that existed in 2000, so open-acre features would rightly change. Instead,
every parcel built after 2000 is turned back into what it was in 2000: vacant land with no
building year and no homes. A second variant scrambles post-2000 build years and home counts
at random. Both must give features identical to the real data at T = 2000.
"""
import numpy as np
import pandas as pd
import pytest

from model.build_panel import prepare
from model.features import compute_features, static_features, hex_geo
from model.load import load_parcels

T = 2000


@pytest.fixture(scope="module")
def parcels():
    return load_parcels()


def feats(p, static=None):
    m = prepare(p)
    return compute_features(m, origins=[T], static=static).set_index("hex").sort_index(), m


def erase_future(p):
    q = p.copy()
    fut = q.yr_built > T
    imp = fut & (q.group == "improved")
    q.loc[imp, "group"] = "vacant"
    q.loc[fut, ["yr_built", "homes"]] = 0
    q.loc[fut, "has_year"] = False
    return q, int(fut.sum())


def scramble_future(p, seed=0):
    rng = np.random.default_rng(seed)
    q = p.copy()
    fut = q.yr_built > T
    q.loc[fut, "yr_built"] = rng.integers(T + 1, 2027, fut.sum())
    q.loc[fut, "homes"] = rng.integers(1, 50, fut.sum())
    return q, int(fut.sum())


def test_features_ignore_the_future(parcels):
    real, m = feats(parcels)
    static = static_features(hex_geo(m["hexes"]))
    real = real.drop(columns=static.columns).join(static)
    for make in (erase_future, scramble_future):
        q, n = make(parcels)
        assert n > 50_000, "the test must actually touch post-2000 parcels"
        got, _ = feats(q, static=static)
        got = got.reindex(real.index)
        cols = [c for c in real.columns]
        pd.testing.assert_frame_equal(got[cols], real[cols], check_dtype=False, rtol=1e-9)
        print(f"{make.__name__}: {n:,} parcels changed, {len(cols)} features x {len(real):,} hexes identical")


def test_negative_control_detects_future(parcels):
    """Same erase, but read at T=2005: features must differ, or the test above proves nothing."""
    q, _ = erase_future(parcels)
    a = compute_features(prepare(parcels), origins=[2005]).set_index("hex").sort_index()
    b = compute_features(prepare(q), origins=[2005], static=a[["dist_road_km", "dist_primary_km",
        "dist_i75_km", "dist_ocala_km", "dist_border_km", "border_flag"]]).set_index("hex").sort_index()
    changed = [c for c in ["homes_T", "homes_last5", "open_acres_T", "dist_front_km", "grav_homes_b1"]
               if not np.allclose(a[c], b.reindex(a.index)[c])]
    print(f"negative control at 2005, changed features: {changed}")
    assert len(changed) == 5
