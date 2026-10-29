#!/usr/bin/env python3
"""One-off rent comps for a building and unit, using RentCast (about 4 requests).

Pulls: the rent estimate with its comparables (AVM), the building's own active and past
rental listings, and closed rentals of the same bedroom count in nearby buildings.
Requests count against the same monthly cap as the daily monitor.
"""
import argparse
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import monitor

BASE = "https://api.rentcast.io/v1"
RAW_PATH = monitor.HERE / "comps_raw.json"


class Budget:
    """Every request is counted in state.json (shared with the daily monitor) and capped."""

    def __init__(self, key):
        self.key = key
        self.config = monitor.load_json(monitor.CONFIG_PATH, {})
        self.state = monitor.load_json(monitor.STATE_PATH, {})
        self.state.setdefault("seen", {})
        month = date.today().strftime("%Y-%m")
        if self.state.get("quota", {}).get("month") != month:
            self.state["quota"] = {"month": month, "used": 0}
        self.cap = self.config.get("max_requests_per_month", 45)

    def call(self, path, params):
        if self.state["quota"]["used"] >= self.cap:
            print(f"Monthly request cap reached ({self.cap}); stopping.")
            return None
        self.state["quota"]["used"] += 1
        monitor.save_state(self.state)
        url = f"{BASE}{path}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-Api-Key": self.key, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            print(f"RentCast error {e.code} on {path}: {e.read().decode(errors='replace')[:300]}")
            return None

    def listings(self, params, max_pages=2):
        rows, limit = [], params.get("limit", 500)
        for page in range(max_pages):
            data = self.call("/listings/rental/long-term", dict(params, offset=page * limit))
            if not data:
                break
            rows += data
            if len(data) < limit:
                break
        return rows


def unit_key(addr2):
    key = re.sub(r"[^a-z0-9]", "", (addr2 or "").lower())
    return re.sub(r"^(apartment|apt|unit|suite|ste|number|no)", "", key)


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def ppsf(row):
    price, sqft = monitor.num(row.get("price")), monitor.num(row.get("squareFootage"))
    return price / sqft if price and sqft else None


def money(v):
    return f"${v:,.0f}" if v is not None else "n/a"


def line(row):
    beds, baths = row.get("bedrooms"), row.get("bathrooms")
    p = ppsf(row)
    return (f"{(row.get('addressLine2') or '-'):<10} {row.get('status', '?'):<8} {money(row.get('price')):>7} "
            f"{beds}bd/{baths}ba {row.get('squareFootage') or '?':>5} sqft "
            f"{('$%.2f/sf' % p) if p else '':>9}  listed {str(row.get('listedDate'))[:10]} "
            f"removed {str(row.get('removedDate'))[:10] if row.get('removedDate') else '-':<10} "
            f"DOM {row.get('daysOnMarket', '?')}")


def building_key(row):
    number, street = monitor.split_address(row.get("addressLine1"))
    return f"{number} {' '.join(street)}"


def offline_report(path, lo, hi):
    """Re-reads a saved comps_raw.json: no API requests, no quota. Lists, building by building,
    every closed or active listing on the street between two street numbers."""
    raw = json.loads(Path(path).read_text())
    rows, seen = [], set()
    for key in ("building_past", "building_active", "nearby_past"):
        for r in raw.get(key) or []:
            if r.get("id") not in seen:
                seen.add(r.get("id"))
                rows.append(r)
    street_ref = monitor.normalize_street("Brickell Ave")
    picked = []
    for r in rows:
        number, street = monitor.split_address(r.get("addressLine1"))
        if number is not None and street == street_ref and lo <= number <= hi:
            picked.append((number, r))
    print(f"=== Brickell Ave {lo} to {hi}: {len(picked)} listings in the saved data "
          f"(closed 2bd within 0.5 mi for {raw.get('nearby_days', 180)} days, plus the building area's closed/active of any size)")
    by_number = {}
    for number, r in picked:
        by_number.setdefault(number, []).append(r)
    for number in sorted(by_number):
        group = sorted(by_number[number], key=lambda r: str(r.get("removedDate") or r.get("listedDate")), reverse=True)
        two = [r for r in group if r.get("bedrooms") == 2 and r.get("status") == "Inactive"]
        print(f"\n--- {number} Brickell Ave: {len(group)} listings, closed 2bd n={len(two)} "
              f"median {money(median([r.get('price') for r in two]))}")
        for r in group:
            print("  " + line(r))
    months = {}
    for number, r in picked:
        if number == 2451 and r.get("bedrooms") == 2 and r.get("status") == "Inactive" and r.get("removedDate"):
            months.setdefault(str(r["removedDate"])[:7], []).append(r.get("addressLine2"))
    print("\n=== 2451 closed 2bd by month the listing left the market")
    for month in sorted(months):
        print(f"  {month}: {', '.join(map(str, months[month]))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", help="path to a saved comps_raw.json: analyse it without any API request")
    ap.add_argument("--from-number", type=int, default=2000)
    ap.add_argument("--to-number", type=int, default=2500)
    ap.add_argument("--address", default="2451 Brickell Ave")
    ap.add_argument("--unit", default="20M")
    ap.add_argument("--city-state-zip", default="Miami, FL 33129")
    ap.add_argument("--beds", type=float)
    ap.add_argument("--baths", type=float)
    ap.add_argument("--sqft", type=int)
    ap.add_argument("--days", type=int, default=180, help="how far back for nearby closed rentals")
    ap.add_argument("--nearby-radius", type=float, default=0.5)
    args = ap.parse_args()

    if args.offline:
        return offline_report(args.offline, args.from_number, args.to_number)
    key = os.environ.get("RENTCAST_API_KEY")
    if not key:
        sys.exit("RENTCAST_API_KEY is not set")
    budget = Budget(key)
    raw = {}
    full_address = f"{args.address}, Unit {args.unit}, {args.city_state_zip}"

    # 1. Rent estimate and its comparables.
    avm_params = {"address": full_address, "propertyType": "Condo", "compCount": 15, "maxRadius": 0.5, "daysOld": args.days}
    for name, value in (("bedrooms", args.beds), ("bathrooms", args.baths), ("squareFootage", args.sqft)):
        if value:
            avm_params[name] = value
    avm = budget.call("/avm/rent/long-term", avm_params)
    raw["avm"] = avm
    lat = lon = None
    print(f"=== Rent estimate for {full_address}")
    if avm:
        lat, lon = avm.get("latitude"), avm.get("longitude")
        print(f"estimate {money(avm.get('rent'))}  range {money(avm.get('rentRangeLow'))} to {money(avm.get('rentRangeHigh'))}")
        for c in avm.get("comparables") or avm.get("listings") or []:
            print(f"  comp {money(c.get('price')):>7}  {c.get('bedrooms')}bd/{c.get('bathrooms')}ba {c.get('squareFootage') or '?':>5} sqft  "
                  f"{c.get('distance', '?')} mi  corr {c.get('correlation', '?')}  {c.get('formattedAddress')}")
    if lat is None or lon is None:
        RAW_PATH.write_text(json.dumps(raw, indent=1))
        sys.exit("No coordinates from the estimate; cannot look up the building. See the error above.")

    # 2. The building's own listings, active and past.
    near = {"latitude": lat, "longitude": lon, "radius": 0.1, "limit": 500}
    past = budget.listings(dict(near, status="Inactive", daysOld=365))
    active = budget.listings(dict(near, status="Active"))
    raw["building_past"], raw["building_active"] = past, active
    number, street = monitor.split_address(args.address)

    def in_building(row):
        n, s = monitor.split_address(row.get("addressLine1"))
        return n == number and s == street

    mine = sorted((r for r in past + active if in_building(r)), key=lambda r: str(r.get("listedDate")), reverse=True)
    target = next((r for r in mine if unit_key(r.get("addressLine2")) == unit_key(args.unit)), None)
    print(f"\n=== {args.address}: {len(mine)} listings in the last 12 months (active and past)")
    for r in mine:
        print("  " + line(r) + ("   <== TARGET UNIT" if r is target or (target and r.get("id") == target.get("id")) else ""))

    beds = args.beds
    if target:
        beds = beds if beds is not None else target.get("bedrooms")
        print(f"\n=== Unit {args.unit} listing history")
        print("  " + line(target))
        for day, event in sorted((target.get("history") or {}).items()):
            print(f"  {day}: {event.get('event')} at {money(event.get('price'))} (DOM {event.get('daysOnMarket', '?')})")
    else:
        print(f"\nUnit {args.unit} not found among the building's listings.")
    if beds is None:
        beds = median([r.get("bedrooms") for r in mine])
        print(f"Bedrooms unknown for the unit; using the building's median ({beds}).")

    same = [r for r in mine if r.get("bedrooms") == beds]
    closed = [r for r in same if r.get("status") == "Inactive"]
    live = [r for r in same if r.get("status") == "Active"]
    print(f"\n=== {args.address}, {beds}bd only")
    print(f"closed in 12 months: n={len(closed)} median {money(median([r.get('price') for r in closed]))} "
          f"median $/sf {median([ppsf(r) for r in closed]) and round(median([ppsf(r) for r in closed]), 2)}")
    print(f"active now:          n={len(live)} median ask {money(median([r.get('price') for r in live]))} "
          f"median DOM {median([r.get('daysOnMarket') for r in live])}")

    # 3. Same bedroom count, closed recently, in nearby buildings.
    wide = budget.listings({"latitude": lat, "longitude": lon, "radius": args.nearby_radius, "status": "Inactive",
                            "bedrooms": beds, "propertyType": "Condo", "daysOld": args.days, "limit": 500})
    raw["nearby_past"] = wide
    raw["nearby_days"] = args.days
    by_building = {}
    for r in wide:
        by_building.setdefault(building_key(r), []).append(r)
    print(f"\n=== Closed {beds}bd rentals within {args.nearby_radius} mi, last {args.days} days: {len(wide)} listings")
    print(f"overall median {money(median([r.get('price') for r in wide]))}  median $/sf "
          f"{median([ppsf(r) for r in wide]) and round(median([ppsf(r) for r in wide]), 2)}")
    for name, rows in sorted(by_building.items(), key=lambda kv: -len(kv[1]))[:12]:
        print(f"  {name:<28} n={len(rows):>3}  median {money(median([r.get('price') for r in rows]))}  "
              f"median sqft {median([r.get('squareFootage') for r in rows])}  "
              f"median $/sf {median([ppsf(r) for r in rows]) and round(median([ppsf(r) for r in rows]), 2)}  "
              f"median DOM {median([r.get('daysOnMarket') for r in rows])}")

    RAW_PATH.write_text(json.dumps(raw, indent=1))
    print(f"\nRequests this month: {budget.state['quota']['used']}/{budget.cap}")


if __name__ == "__main__":
    main()
