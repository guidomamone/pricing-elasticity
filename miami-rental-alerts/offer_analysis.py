#!/usr/bin/env python3
"""View-tier analysis for the 20M offer, from the CSVs in data/. No network, no API."""
import csv
import math
import statistics as st
from pathlib import Path

DATA = Path(__file__).parent / "data"
TIERS = ("water", "water_limited", "parking_lot")
ASK, SQFT_M = 3950, 1344


def load(name):
    with open(DATA / name) as f:
        return list(csv.DictReader(f))


def num(x):
    return float(x) if x not in ("", None) else None


def pct(values, q):
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def ranges_table(rows):
    print("=== Contract price ranges by bedrooms and view tier (Compass contract prices, 2451 Brickell Ave)")
    print(f"{'beds':<5}{'view tier':<15}{'n':>3}{'min':>8}{'p25':>8}{'median':>8}{'mean':>8}{'p75':>8}{'max':>8}"
          f"   {'$/sf min':>9}{'median':>8}{'max':>7}")
    for beds in ("1", "2"):
        for tier in TIERS:
            sel = [r for r in rows if r["beds"] == beds and r["view"] == tier]
            if not sel:
                continue
            p = [num(r["contract_price"]) for r in sel]
            sf = [num(r["contract_price"]) / num(r["sqft"]) for r in sel if r["sqft"]]
            print(f"{beds:<5}{tier:<15}{len(p):>3}{min(p):>8,.0f}{pct(p, .25):>8,.0f}{st.median(p):>8,.0f}{st.mean(p):>8,.0f}"
                  f"{pct(p, .75):>8,.0f}{max(p):>8,.0f}   {min(sf):>9.2f}{st.median(sf):>8.2f}{max(sf):>7.2f}")


def solve(a, b):
    """Gauss-Jordan: returns (inverse of a, a^-1 b)."""
    n = len(a)
    m = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        d = m[c][c]
        m[c] = [v / d for v in m[c]]
        for r in range(n):
            if r != c:
                f = m[r][c]
                m[r] = [v - f * w for v, w in zip(m[r], m[c])]
    return [row[n:2 * n] for row in m], [row[-1] for row in m]


def month_index(month):
    y, mth = int(month[:4]), int(month[5:7])
    return (y - 2025) * 12 + mth - 7


def regression(rows):
    score = {"water": 1.0, "water_limited": 0.5, "parking_lot": 0.0}
    data = []
    for r in rows:
        if r["view"] not in score or not r["sqft"]:
            continue
        floor = num(r["floor_num"]) or 22  # assumption: PH level counts as floor 22
        data.append(([1.0, score[r["view"]], math.log(num(r["sqft"])), floor, month_index(r["month"])],
                     math.log(num(r["contract_price"])), r["unit"]))
    k, n = 5, len(data)
    xtx = [[sum(x[i] * x[j] for x, _, _ in data) for j in range(k)] for i in range(k)]
    xty = [sum(x[i] * y for x, y, _ in data) for i in range(k)]
    inv, beta = solve(xtx, xty)
    resid = [y - sum(b * v for b, v in zip(beta, x)) for x, y, _ in data]
    s2 = sum(e * e for e in resid) / (n - k)
    se = [math.sqrt(s2 * inv[i][i]) for i in range(k)]
    names = ["intercept", "view (water=1, limited=.5)", "ln(sqft)", "floor", "month (from 2025-07)"]
    print(f"\n=== Regression: ln(contract price) on view, ln(sqft), floor, month   (n={n}, all bedroom counts)")
    for name, b, s in zip(names, beta, se):
        print(f"  {name:<28} coef {b:>8.4f}  se {s:.4f}   t {b / s:>6.2f}")
    print(f"  residual std {math.sqrt(s2):.3f} (about {math.sqrt(s2) * 100:.0f}% of price)")
    print(f"  water premium {math.expm1(beta[1]) * 100:.1f}%   per floor {math.expm1(beta[3]) * 100:.2f}%   "
          f"per month {math.expm1(beta[4]) * 100:.2f}%   sqft elasticity {beta[2]:.2f}")
    return beta, inv, s2


def predict(beta, inv, s2, view, sqft, floor, month):
    x = [1.0, view, math.log(sqft), floor, month_index(month)]
    mu = sum(b * v for b, v in zip(beta, x))
    quad = sum(x[i] * inv[i][j] * x[j] for i in range(5) for j in range(5))
    sd = math.sqrt(s2 * (1 + quad))
    return math.exp(mu), math.exp(mu - 1.7 * sd), math.exp(mu + 1.7 * sd)


def main():
    allrows = load("compass_past_rentals_2451.csv")
    ranges_table(allrows)
    two = [r for r in allrows if r["beds"] == "2"]
    water = [r for r in two if r["view"] == "water"]
    park = [r for r in two if r["view"] == "parking_lot"]
    price = lambda rs: [num(r["contract_price"]) for r in rs]

    print("\n=== 2bd contracts, newest first")
    for r in sorted(two, key=lambda r: r["month"], reverse=True):
        print(f"  {r['month']} {r['unit']:>4} {r['view']:<12} {r['sqft']:>5} sqft  ${num(r['contract_price']):>6,.0f}  "
              f"orig {r['orig_price'] or '-':>5}  rc_ask {r['rc_last_ask'] or '-':>5}")

    print("\n=== View premium from the data")
    print(f"  2bd: water mean {st.mean(price(water)):,.0f} vs parking mean {st.mean(price(park)):,.0f} -> "
          f"{st.mean(price(water)) - st.mean(price(park)):,.0f} ({(st.mean(price(water)) / st.mean(price(park)) - 1) * 100:.0f}%)")
    one_w = [r for r in allrows if r["beds"] == "1" and r["view"] == "water"]
    one_p = [r for r in allrows if r["beds"] == "1" and r["view"] == "parking_lot"]
    ppsf = lambda rs: st.mean(num(r["contract_price"]) / num(r["sqft"]) for r in rs if r["sqft"])
    print(f"  1bd: water $/sf {ppsf(one_w):.2f} (n={len(one_w)}) vs parking $/sf {ppsf(one_p):.2f} (n={len(one_p)}) -> "
          f"{(ppsf(one_w) / ppsf(one_p) - 1) * 100:.0f}% premium")
    print(f"  2bd: water $/sf {ppsf(water):.2f} vs parking $/sf {ppsf(park):.2f} -> {(ppsf(water) / ppsf(park) - 1) * 100:.0f}% premium")

    beta, inv, s2 = regression(allrows)
    reg, reg_lo, reg_hi = predict(beta, inv, s2, 0.0, SQFT_M, 20, "2026-11")

    print("\n=== Implied 20M price (parking lot, 1,344 sqft, floor 20, lease starting 2026-11) by method")
    park_ppsf_mean = st.mean(num(r["contract_price"]) / num(r["sqft"]) for r in park)
    park_ppsf_med = st.median(num(r["contract_price"]) / num(r["sqft"]) for r in park)
    ex4l = [r for r in park if r["unit"] != "4L"]
    ex_mean = st.mean(num(r["contract_price"]) / num(r["sqft"]) for r in ex4l)
    slow = [num(r["contract_vs_rc_ask_pct"]) for r in two if r["contract_vs_rc_ask_pct"] != "" and r["rc_dom"] and int(r["rc_dom"]) > 40]
    water_slow = [r for r in water if r["unit"] in ("12B", "2E")]
    prem2 = st.mean(price(water)) / st.mean(price(park))
    methods = [
        ("Ph M precedent (same line, May 2026)", 3600, 3600),
        ("parking $/sf x 1,344 (median to mean)", park_ppsf_med * SQFT_M, park_ppsf_mean * SQFT_M),
        ("parking $/sf excl. 4L x 1,344", ex_mean * SQFT_M * 0.98, ex_mean * SQFT_M * 1.02),
        ("slow water units less 2bd view premium", st.mean(price(water_slow)) / prem2, st.mean(price(water_slow)) / prem2 * (1344 / 1188)),
        ("regression (90% range)", reg_lo, reg_hi),
        ("ask less stale-unit gap (-2.5% to -9.9%)", ASK * (1 - 0.099), ASK * (1 - 0.025)),
    ]
    print(f"  {'method':<46}{'low':>8}{'high':>8}")
    for name, lo, hi in methods:
        print(f"  {name:<46}{lo:>8,.0f}{hi:>8,.0f}")
    print(f"  regression point estimate: {reg:,.0f}")
    lows, highs = [m[1] for m in methods], [m[2] for m in methods]
    print(f"  median of lows {st.median(lows):,.0f}   median of highs {st.median(highs):,.0f}")

    print("\n=== Contract vs last RentCast asking price")
    allm = [r for r in allrows if r["contract_vs_rc_ask_pct"] != ""]
    gaps = [num(r["contract_vs_rc_ask_pct"]) for r in allm]
    print(f"  all {len(gaps)} units: mean {st.mean(gaps):.1f}%  median {st.median(gaps):.1f}%")
    higher = [r for r in park if num(r["contract_price"]) >= ASK]
    print(f"  20M asks {ASK:,}: {len(higher)} of {len(park)} parking-lot 2bd contracts were at or above it")


if __name__ == "__main__":
    main()
