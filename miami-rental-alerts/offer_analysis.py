#!/usr/bin/env python3
"""View-tier analysis for the 20M offer, from the CSVs in data/. No network, no API."""
import csv
import statistics as st
from pathlib import Path

DATA = Path(__file__).parent / "data"


def load(name):
    with open(DATA / name) as f:
        return list(csv.DictReader(f))


def num(x):
    return float(x) if x not in ("", None) else None


def stats(label, rows, key="contract_price"):
    prices = [num(r[key]) for r in rows]
    ppsf = [num(r["contract_price"]) / num(r["sqft"]) for r in rows if r["sqft"]]
    if not prices:
        print(f"{label:<34} n=0")
        return
    print(f"{label:<34} n={len(prices):>2}  median {st.median(prices):>6,.0f}  mean {st.mean(prices):>6,.0f}  "
          f"min {min(prices):>6,.0f}  max {max(prices):>6,.0f}  median $/sf "
          f"{(st.median(ppsf) if ppsf else 0):.2f}")


def main():
    rows = [r for r in load("compass_past_rentals_2451.csv") if r["beds"] == "2"]
    water = [r for r in rows if r["view"] == "water"]
    park = [r for r in rows if r["view"] == "parking_lot"]
    unknown = [r for r in rows if r["view"] == "unknown"]
    print("=== 2bd contract prices by view tier (Compass, 2451 Brickell Ave)")
    stats("water, all", water)
    stats("water, 2026 only", [r for r in water if r["month"] >= "2026-01"])
    stats("parking lot, all", park)
    stats("parking lot, excluding 4L", [r for r in park if r["unit"] != "4L"])
    stats("parking lot, 2026 only", [r for r in park if r["month"] >= "2026-01"])
    stats("view unknown", unknown)

    print("\n=== every 2bd contract, newest first")
    for r in sorted(rows, key=lambda r: r["month"], reverse=True):
        print(f"  {r['month']} {r['unit']:>4} line {r['line']} {r['view']:<12} {r['sqft']:>5} sqft  "
              f"${num(r['contract_price']):>6,.0f}  orig {r['orig_price'] or '-':>5}  rc_ask {r['rc_last_ask'] or '-':>5}")

    pw, pp = st.mean(num(r["contract_price"]) for r in water), st.mean(num(r["contract_price"]) for r in park)
    mw, mp = st.median(num(r["contract_price"]) for r in water), st.median(num(r["contract_price"]) for r in park)
    print(f"\nwater premium: mean {pw - pp:,.0f} ({(pw / pp - 1) * 100:.0f}%), median {mw - mp:,.0f} ({(mw / mp - 1) * 100:.0f}%)")

    print("\n=== same-floor pairs (water vs parking lot)")
    by_floor = {}
    for r in rows:
        by_floor.setdefault(r["floor_num"], []).append(r)
    for floor, items in sorted(by_floor.items(), key=lambda kv: int(kv[0]) if kv[0] else 99):
        views = {r["view"] for r in items}
        if {"water", "parking_lot"} <= views:
            print(f"  floor {floor}: " + ", ".join(f"{r['unit']} {r['view']} ${num(r['contract_price']):,.0f} ({r['month']})" for r in items))

    print("\n=== price per sqft applied to the M line (1,344 sqft per the Ph M listing)")
    for label, tier in (("parking lot", park), ("parking lot excl. 4L", [r for r in park if r["unit"] != "4L"]), ("water", water)):
        ppsf = [num(r["contract_price"]) / num(r["sqft"]) for r in tier if r["sqft"]]
        print(f"  {label:<22} median ${st.median(ppsf):.2f}/sf -> {st.median(ppsf) * 1344:,.0f}   mean ${st.mean(ppsf):.2f}/sf -> {st.mean(ppsf) * 1344:,.0f}")

    ask = 3950
    higher = [r for r in park if num(r["contract_price"]) >= ask]
    print(f"\n20M asks {ask:,}: {len(higher)} of {len(park)} parking-lot 2bd contracts were at or above it "
          f"({', '.join(r['unit'] + ' $' + format(num(r['contract_price']), ',.0f') for r in higher) or 'none'})")

    print("\n=== contract vs last RentCast asking price, all matched units")
    allrows = [r for r in load("compass_past_rentals_2451.csv") if r["contract_vs_rc_ask_pct"] != ""]
    gaps = [num(r["contract_vs_rc_ask_pct"]) for r in allrows]
    print(f"  all {len(gaps)} units: mean {st.mean(gaps):.1f}%  median {st.median(gaps):.1f}%")
    two = [num(r["contract_vs_rc_ask_pct"]) for r in allrows if r["beds"] == "2"]
    print(f"  2bd {len(two)} units: mean {st.mean(two):.1f}%  median {st.median(two):.1f}%")
    slow = [num(r["contract_vs_rc_ask_pct"]) for r in allrows if r["beds"] == "2" and r["rc_dom"] and int(r["rc_dom"]) > 40]
    fast = [num(r["contract_vs_rc_ask_pct"]) for r in allrows if r["beds"] == "2" and r["rc_dom"] and int(r["rc_dom"]) <= 24]
    print(f"  2bd listed >40 days: n={len(slow)} mean {st.mean(slow):.1f}%   2bd listed <=24 days: n={len(fast)} mean {st.mean(fast):.1f}%")
    print(f"  20M at {ask:,} with the slow-unit gap ({st.mean(slow):.1f}%): {ask * (1 + st.mean(slow) / 100):,.0f}")


if __name__ == "__main__":
    main()
