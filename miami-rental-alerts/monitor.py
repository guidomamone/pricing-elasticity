#!/usr/bin/env python3
"""Daily check of RentCast rental listings for a short list of Miami buildings.

One API request per run (search area in buildings.json), matched locally to the
buildings, new listings sent to Telegram. State lives in state.json.
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "buildings.json"
STATE_PATH = HERE / "state.json"
RENTCAST_URL = "https://api.rentcast.io/v1/listings/rental/long-term"

SUFFIXES = {"avenue": "ave", "boulevard": "blvd", "drive": "dr", "street": "st", "road": "rd"}
DIRECTIONS = {"n", "s", "e", "w", "ne", "nw", "se", "sw"}


def normalize_street(street):
    tokens = re.sub(r"[^a-z0-9 ]", " ", street.lower()).split()
    return [SUFFIXES.get(t, t) for t in tokens if t not in DIRECTIONS]


def split_address(line1):
    m = re.match(r"\s*(\d+)\s+(.+)", line1 or "")
    if not m:
        return None, []
    return int(m.group(1)), normalize_street(m.group(2))


def match_building(listing, buildings):
    number, street = split_address(listing.get("addressLine1"))
    if number is None:
        return None
    for b in buildings:
        if street != normalize_street(b["street"]):
            continue
        if number in b.get("numbers", []):
            return b
        lo_hi = b.get("number_range")
        if lo_hi and lo_hi[0] <= number <= lo_hi[1]:
            if b.get("odd_only") and number % 2 == 0:
                continue
            return b
    return None


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def fetch_listings(api_key, search):
    url = RENTCAST_URL + "?" + urllib.parse.urlencode(search)
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def format_message(listing, building):
    unit = listing.get("addressLine2") or ""
    title = f"{building['name']} {unit}".strip()
    price = listing.get("price")
    bits = [f"${price:,.0f}/mo" if price else "price n/a"]
    if listing.get("bedrooms") is not None:
        bits.append(f"{listing['bedrooms']:g}bd/{listing.get('bathrooms', '?')}ba")
    if listing.get("squareFootage"):
        bits.append(f"{listing['squareFootage']:,} sqft")
    addr = listing.get("formattedAddress", "")
    link = "https://www.zillow.com/homes/" + urllib.parse.quote(addr.replace(" ", "-")) + "_rb/"
    return (
        f"<b>{html.escape(title)}</b>\n"
        f"{html.escape(' · '.join(bits))}\n"
        f"Listed {html.escape(str(listing.get('listedDate', '?'))[:10])}\n"
        f"{html.escape(addr)}\n"
        f'<a href="{html.escape(link)}">Search on Zillow</a>'
    )


def send_telegram(token, chat_id, text):
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=30):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print alerts, do not send or mark as seen")
    ap.add_argument("--days", type=int, help="override search daysOld (useful with --dry-run to look further back)")
    args = ap.parse_args(argv)

    config = load_json(CONFIG_PATH, None)
    state = load_json(STATE_PATH, {})
    state.setdefault("seen", {})
    month = date.today().strftime("%Y-%m")
    if state.get("quota", {}).get("month") != month:
        state["quota"] = {"month": month, "used": 0}

    api_key = os.environ.get("RENTCAST_API_KEY")
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not api_key:
        sys.exit("RENTCAST_API_KEY is not set")
    if not args.dry_run and not (token and chat_id):
        sys.exit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required (or use --dry-run)")

    cap = config.get("max_requests_per_month", 45)
    if state["quota"]["used"] >= cap:
        print(f"Monthly request cap reached ({cap}); skipping to avoid overage fees.")
        if not args.dry_run and not state["quota"].get("warned"):
            send_telegram(token, chat_id, f"RentCast request cap ({cap}/month) reached. Alerts paused until next month.")
            state["quota"]["warned"] = True
            save_state(state)
        return 0

    # Count before calling so a crash mid-request still counts against the cap.
    state["quota"]["used"] += 1
    save_state(state)
    search = dict(config["search"])
    if args.days:
        search["daysOld"] = args.days
    try:
        listings = fetch_listings(api_key, search)
    except urllib.error.HTTPError as e:
        sys.exit(f"RentCast error {e.code}: {e.read().decode(errors='replace')[:300]}")

    if args.dry_run:
        print("Brickell-area addresses returned (check these against buildings.json):")
        for l in listings:
            if "brickell" in (l.get("addressLine1") or "").lower():
                print(f"  {l.get('formattedAddress')}")

    limit = config["search"].get("limit")
    if limit and len(listings) >= limit:
        print(f"WARNING: got {len(listings)} listings (limit {limit}); results may be truncated.")

    new = 0
    for listing in listings:
        building = match_building(listing, config["buildings"])
        if not building or listing["id"] in state["seen"]:
            continue
        max_price = config.get("max_price")
        # Not marked as seen, so a later price drop under the cap still alerts.
        if max_price and (listing.get("price") or 0) > max_price:
            continue
        msg = format_message(listing, building)
        new += 1
        if args.dry_run:
            print(msg + "\n")
            continue
        send_telegram(token, chat_id, msg)
        state["seen"][listing["id"]] = {"first_seen": date.today().isoformat(), "price": listing.get("price")}
        save_state(state)

    print(f"{len(listings)} listings in area, {new} new in tracked buildings. "
          f"Requests this month: {state['quota']['used']}/{cap}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
