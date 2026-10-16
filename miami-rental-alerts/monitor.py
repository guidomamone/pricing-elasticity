#!/usr/bin/env python3
"""Daily check of RentCast rental listings for a short list of Miami buildings.

One API request per run (search area in buildings.json). New listings are sent to
Telegram as two lists: tennis-court buildings, and other listings in the Brickell zip
codes (a tennis-court listing is never repeated in the second list). Both lists go in one
message every run; an empty one says "Nothing new today." State lives in
state.json.
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
    tokens = [re.sub(r"^(\d+)(st|nd|rd|th)$", r"\1", t) for t in tokens]  # 25th -> 25
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


def num(value):
    """Parse a numeric API field. Returns None when missing or unparseable (never guesses)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def days_on_market(listing):
    d = num(listing.get("daysOnMarket"))
    if d is not None:
        return int(d)
    try:
        return (date.today() - date.fromisoformat(str(listing.get("listedDate"))[:10])).days
    except ValueError:
        return None


def check_filters(listing, config):
    """Returns (skip_reason, warnings). Missing/unparseable data never filters a listing out:
    it passes with a warning, so a parsing problem shows up in the alert instead of hiding it."""
    warnings = []
    price, beds = num(listing.get("price")), num(listing.get("bedrooms"))
    max_price, min_beds = config.get("max_price"), config.get("min_bedrooms")
    if max_price:
        if price is None:
            warnings.append("price missing, could not apply max price filter")
        elif price > max_price:
            return f"price ${price:,.0f} > {max_price}", warnings
    if min_beds is not None:
        if beds is None:
            warnings.append("bedrooms missing, could not apply bedroom filter")
        elif beds < min_beds:
            return f"{beds:g} bedrooms < {min_beds}", warnings
    return None, warnings


def describe(listing):
    price, beds = num(listing.get("price")), num(listing.get("bedrooms"))
    return (f"{listing.get('formattedAddress')} | price={listing.get('price')!r} "
            f"beds={listing.get('bedrooms')!r}" if price is None or beds is None else
            f"{listing.get('formattedAddress')} | ${price:,.0f} | {beds:g}bd")


def zip_of(listing):
    return str(listing.get("zipCode") or "").strip()[:5]


def format_entry(listing, name, warnings=()):
    """Compact 3-line block. name is the tracked building's name, or None for a general Brickell listing."""
    unit = listing.get("addressLine2") or ""
    short = ", ".join(x for x in (listing.get("addressLine1"), unit) if x) or listing.get("formattedAddress", "")
    title = f"{name} {unit}".strip() if name else short
    price, beds = num(listing.get("price")), num(listing.get("bedrooms"))
    bits = [f"${price:,.0f}/mo" if price else "price n/a"]
    if beds is not None:
        bits.append(f"{beds:g}bd/{listing.get('bathrooms', '?')}ba")
    if listing.get("squareFootage"):
        bits.append(f"{listing['squareFootage']:,} sqft")
    dom = days_on_market(listing)
    bits.append(f"{dom}d on market" if dom is not None else "days on market n/a")
    addr = listing.get("formattedAddress", "")
    link = "https://www.zillow.com/homes/" + urllib.parse.quote(addr.replace(" ", "-")) + "_rb/"
    lines = [
        f"<b>{html.escape(title)}</b>",
        html.escape(" · ".join(bits)),
        f'<a href="{html.escape(link)}">{html.escape(short if name else "Search on Zillow")}</a>',
    ]
    lines += [f"⚠️ {html.escape(w)}" for w in warnings]
    return "\n".join(lines)


def build_digest(sections, limit=3800):
    """sections: [(header, [(listing, block)])]. Returns [(message_text, [listings])].

    Everything goes in one message; it is split only if it would exceed Telegram's size
    limit, repeating the section header with "(cont.)". An empty section says so."""
    msgs, text, group = [], "", []
    for header, items in sections:
        first = True
        for listing, block in items or [(None, "Nothing new today.")]:
            piece = (header + "\n\n" if first or not text else "") + block
            if text and len(text) + 2 + len(piece) > limit:
                msgs.append((text, group))
                text, group = "", []
                piece = (header if first else header + " (cont.)") + "\n\n" + block
            text = text + "\n\n" + piece if text else piece
            if listing is not None:
                group.append(listing)
            first = False
    if text:
        msgs.append((text, group))
    return msgs


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

    limit = config["search"].get("limit")
    if limit and len(listings) >= limit:
        print(f"WARNING: got {len(listings)} listings (limit {limit}); results may be truncated.")

    zips = set(config.get("brickell_zips", []))
    sections = {"tennis": [], "brickell": []}
    skipped, skipped_brickell, missing, considered = [], 0, 0, 0
    for listing in listings:
        building = match_building(listing, config["buildings"])
        if not building and zip_of(listing) not in zips:
            continue
        considered += 1
        reason, warnings = check_filters(listing, config)
        missing += bool(warnings)
        if listing["id"] in state["seen"]:
            continue
        if reason:
            # Not marked as seen, so a later change (price drop) still alerts.
            if building:
                skipped.append((listing, reason))
            else:
                skipped_brickell += 1
            continue
        # A tennis-court building is listed only in the tennis list, never again under Brickell.
        sections["tennis" if building else "brickell"].append((listing, building, warnings))

    headers = {"tennis": "🎾 <b>Tennis-court buildings: {n} new</b>",
               "brickell": "🏙 <b>Brickell, other buildings: {n} new</b>"}
    new, digest_sections = {}, []
    for key, entries in sections.items():
        entries.sort(key=lambda e: num(e[0].get("price")) or float("inf"))
        new[key] = len(entries)
        items = [(l, format_entry(l, b["name"] if b else None, w)) for l, b, w in entries]
        digest_sections.append((headers[key].format(n=len(entries)), items))
    # One message with both lists. An empty list is still shown, so a quiet day is visible
    # and not mistaken for a broken bot.
    for text, group in build_digest(digest_sections):
        if args.dry_run:
            print(text + "\n")
            continue
        send_telegram(token, chat_id, text)
        for l in group:
            state["seen"][l["id"]] = {"first_seen": date.today().isoformat(), "price": l.get("price")}
        save_state(state)

    # Safety nets for parsing problems, all visible in the Actions log.
    for listing, reason in skipped:
        print(f"SKIPPED ({reason}): {describe(listing)}")

    problems = []
    if considered >= 4 and missing / considered >= 0.5:
        problems.append(f"{missing} of {considered} matched listings are missing price or bedrooms. RentCast data format may have changed.")
    for text in problems:
        print("WARNING:", text)
    if not args.dry_run:
        if problems:
            send_telegram(token, chat_id, "⚠️ " + html.escape(problems[0]))
        if config.get("notify_skipped"):
            reported = state.setdefault("skipped_reported", {})
            fresh = [(l, r) for l, r in skipped if l["id"] not in reported]
            if fresh:
                body = "\n".join(f"• {html.escape(describe(l))} ({html.escape(r)})" for l, r in fresh)
                send_telegram(token, chat_id, f"<b>Filtered out, not alerted</b>\n{body}")
                for l, _ in fresh:
                    reported[l["id"]] = date.today().isoformat()
                save_state(state)

    print(f"{len(listings)} listings in area. Tennis buildings: {new['tennis']} new, {len(skipped)} filtered out. "
          f"Other Brickell: {new['brickell']} new, {skipped_brickell} filtered out. "
          f"Requests this month: {state['quota']['used']}/{cap}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
