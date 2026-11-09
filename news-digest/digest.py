#!/usr/bin/env python3
"""Morning news digest: fetch RSS feeds, dedupe into SQLite, send the top items to Telegram.

Stdlib only. Config lives in sources.json. State lives in a SQLite file under --data-dir.
Env: NEWS_TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (not needed with --dry-run).
"""
import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
UA = "Mozilla/5.0 (compatible; news-digest/1.0)"
TG_LIMIT = 4000

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    topic TEXT NOT NULL,
    published TEXT,
    snippet TEXT,
    first_seen TEXT NOT NULL,
    sent_at TEXT
);
CREATE INDEX IF NOT EXISTS items_sent ON items (sent_at, topic);
"""


# ---------- fetching and parsing ----------

def http_get(url, timeout=25, attempts=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, OSError):
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))


def gnews_url(query, lang="en-US", country="US"):
    ceid = f"{country}:{lang}"
    q = urllib.parse.urlencode({"q": query, "hl": lang, "gl": country, "ceid": ceid})
    return f"https://news.google.com/rss/search?{q}"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def child_text(el, name):
    for c in el:
        if local(c.tag) == name:
            return (c.text or "").strip()
    return ""


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def parse_feed(data):
    """Return a list of {title, url, published, snippet} from an RSS or Atom document."""
    root = ET.fromstring(data)
    out = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        title = strip_tags(child_text(el, "title"))
        link = child_text(el, "link")
        if not link:
            for c in el:
                if local(c.tag) == "link" and c.get("href"):
                    link = c.get("href")
                    break
        if not title or not link:
            continue
        date = (child_text(el, "pubDate") or child_text(el, "published")
                or child_text(el, "updated") or child_text(el, "date"))
        snippet = strip_tags(child_text(el, "description") or child_text(el, "summary")
                             or child_text(el, "content"))[:300]
        out.append({"title": title, "url": link, "published": parse_date(date), "snippet": snippet})
    return out


def feed_url(feed):
    if "gnews" in feed:
        return gnews_url(feed["gnews"], feed.get("lang", "en-US"), feed.get("country", "US"))
    return feed["url"]


def ingest(conn, config, now):
    limit = config["settings"]["per_feed_limit"]
    stats = []
    for topic in config["topics"]:
        for feed in topic["feeds"]:
            try:
                entries = parse_feed(http_get(feed_url(feed)))
            except (urllib.error.URLError, ET.ParseError, OSError, ValueError) as e:
                stats.append(f"FAIL {topic['key']}/{feed['name']}: {e}")
                continue
            entries.sort(key=lambda e: e["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            new = 0
            for e in entries[:limit]:
                item_id = hashlib.sha1(e["url"].encode()).hexdigest()
                cur = conn.execute(
                    "INSERT OR IGNORE INTO items (id, url, title, source, topic, published, snippet, first_seen) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (item_id, e["url"], e["title"], feed["name"], topic["key"],
                     e["published"].isoformat() if e["published"] else None,
                     e["snippet"], now.isoformat()))
                new += cur.rowcount
            stats.append(f"ok   {topic['key']}/{feed['name']}: {len(entries)} entries, {new} new")
    conn.commit()
    return stats


# ---------- selection and formatting ----------

def interleave_by_source(rows):
    """Order rows (already newest first) round-robin across sources so one feed cannot dominate."""
    buckets = {}
    for r in rows:
        buckets.setdefault(r["source"], []).append(r)
    out = []
    while any(buckets.values()):
        for src in list(buckets):
            if buckets[src]:
                out.append(buckets[src].pop(0))
    return out


def select(conn, config, now):
    s = config["settings"]
    cutoff = (now - timedelta(hours=s["max_age_hours"])).isoformat()
    picked = []
    for topic in config["topics"]:
        rows = conn.execute(
            "SELECT * FROM items WHERE sent_at IS NULL AND topic = ? "
            "AND COALESCE(published, first_seen) >= ? "
            "ORDER BY COALESCE(published, first_seen) DESC", (topic["key"], cutoff)).fetchall()
        for r in interleave_by_source(rows)[: s["per_topic"]]:
            picked.append((topic, r))
    return picked[: s["max_total"]]


def build_messages(picked, now_local):
    header = f"☀️ <b>Morning digest</b>, {now_local.strftime('%a %b %-d')}"
    if not picked:
        return [header + "\n\nNothing new that matches your topics."]
    blocks, current = [], None
    for topic, r in picked:
        if current is None or current[0] != topic["key"]:
            current = (topic["key"], [f"\n<b>{html.escape(topic['label'])}</b>"])
            blocks.append(current)
        title = html.escape(r["title"])
        url = html.escape(r["url"], quote=True)
        current[1].append(f'• <a href="{url}">{title}</a> <i>({html.escape(r["source"])})</i>')
    messages, text = [], header
    for _, lines in blocks:
        for line in lines:
            if len(text) + len(line) + 1 > TG_LIMIT:
                messages.append(text)
                text = line.lstrip("\n")
            else:
                text += "\n" + line
    messages.append(text)
    return messages


def send_telegram(token, chat_id, text):
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
    except urllib.error.HTTPError as e:
        # Telegram explains the failure in the body (e.g. "chat not found", "can't parse entities").
        raise RuntimeError(f"Telegram HTTP {e.code}: {e.read().decode(errors='replace')[:500]}") from None


# ---------- main ----------

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--config", default=str(HERE / "sources.json"))
    ap.add_argument("--dry-run", action="store_true", help="print instead of sending, do not mark as sent")
    ap.add_argument("--force", action="store_true", help="send even if it is not 8am Eastern")
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--send-hour", type=int, default=8)
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    now_local = now.astimezone(ZoneInfo(args.tz))
    force = args.force or os.environ.get("FORCE") == "1"
    if not force and not args.dry_run and now_local.hour != args.send_hour:
        print(f"Local time is {now_local:%H:%M} {args.tz}, not {args.send_hour}:00. Skipping (DST double cron).")
        return 0

    token, chat_id = os.environ.get("NEWS_TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not args.dry_run and not (token and chat_id):
        sys.exit("NEWS_TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required (or use --dry-run)")

    config = json.loads(Path(args.config).read_text())
    Path(args.data_dir).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(Path(args.data_dir) / "news.db")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    for line in ingest(conn, config, now):
        print(line)

    picked = select(conn, config, now)
    messages = build_messages(picked, now_local)
    if args.dry_run:
        print("\n---- DRY RUN ----")
        print("\n\n".join(messages))
        return 0
    for m in messages:
        send_telegram(token, chat_id, m)
    conn.executemany("UPDATE items SET sent_at = ? WHERE id = ?",
                     [(now.isoformat(), r["id"]) for _, r in picked])
    conn.commit()
    print(f"Sent {len(picked)} items in {len(messages)} message(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
