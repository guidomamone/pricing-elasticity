import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

import digest

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Hello &amp; &lt;b&gt;world&lt;/b&gt;</title><link>https://a.example/1</link>
<pubDate>Mon, 09 Nov 2026 12:00:00 GMT</pubDate><description>&lt;p&gt;Body text&lt;/p&gt;</description></item>
<item><title>No link</title></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom one</title><link href="https://b.example/1"/><updated>2026-11-09T10:00:00Z</updated>
<summary>Sum</summary></entry></feed>"""

NOW = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)
CONFIG = {"settings": {"max_age_hours": 48, "per_feed_limit": 30, "per_topic": 2, "max_total": 14},
          "topics": [{"key": "t1", "label": "One", "feeds": []}, {"key": "t2", "label": "Two", "feeds": []}]}


def db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(digest.SCHEMA)
    return c


def add(c, i, topic, source, hours_ago, sent=None):
    pub = (NOW - timedelta(hours=hours_ago)).isoformat()
    c.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?)",
              (str(i), f"https://x/{i}", f"Title {i}", source, topic, pub, "", NOW.isoformat(), sent))


class ParseTests(unittest.TestCase):
    def test_rss(self):
        items = digest.parse_feed(RSS)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hello & world")
        self.assertEqual(items[0]["snippet"], "Body text")
        self.assertEqual(items[0]["published"].hour, 12)

    def test_atom(self):
        items = digest.parse_feed(ATOM)
        self.assertEqual(items[0]["url"], "https://b.example/1")
        self.assertEqual(items[0]["published"].hour, 10)


class SelectTests(unittest.TestCase):
    def test_skips_sent_and_old_and_caps_per_topic(self):
        c = db()
        add(c, 1, "t1", "A", 1)
        add(c, 2, "t1", "A", 2)
        add(c, 3, "t1", "A", 3)
        add(c, 4, "t1", "A", 4, sent="x")
        add(c, 5, "t2", "A", 100)  # too old
        picked = digest.select(c, CONFIG, NOW)
        self.assertEqual([r["id"] for _, r in picked], ["1", "2"])

    def test_round_robin_sources(self):
        c = db()
        add(c, 1, "t1", "A", 1)
        add(c, 2, "t1", "A", 2)
        add(c, 3, "t1", "B", 3)
        picked = digest.select(c, CONFIG, NOW)
        self.assertEqual([r["id"] for _, r in picked], ["1", "3"])


class FormatTests(unittest.TestCase):
    def test_escapes_and_splits(self):
        c = db()
        add(c, 1, "t1", "A<b>", 1)
        picked = digest.select(c, CONFIG, NOW)
        msg = digest.build_messages(picked, NOW)
        self.assertIn("A&lt;b&gt;", msg[0])
        many = [(CONFIG["topics"][0], {"title": "x" * 300, "url": "https://x/" + str(i), "source": "S"})
                for i in range(30)]
        msgs = digest.build_messages(many, NOW)
        self.assertGreater(len(msgs), 1)
        self.assertTrue(all(len(m) <= 4096 for m in msgs))

    def test_empty(self):
        self.assertIn("Nothing new", digest.build_messages([], NOW)[0])


if __name__ == "__main__":
    unittest.main()
