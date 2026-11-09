import json
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
SETTINGS = {"max_age_hours": 48, "per_feed_limit": 30, "per_topic": 2, "max_total": 14, "min_score": 5,
            "candidates_per_topic": 12, "max_candidates": 100, "llm_batch_size": 2}
CONFIG = {"settings": SETTINGS,
          "topics": [{"key": "t1", "label": "One", "describe": "first", "feeds": []},
                     {"key": "t2", "label": "Two", "describe": "second", "feeds": []}]}


def db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(digest.SCHEMA)
    digest.migrate(c)
    return c


def add(c, i, topic, source, hours_ago, sent=None, **extra):
    pub = (NOW - timedelta(hours=hours_ago)).isoformat()
    c.execute("INSERT INTO items (id, url, title, source, topic, published, snippet, first_seen, sent_at) "
              "VALUES (?,?,?,?,?,?,?,?,?)",
              (str(i), f"https://x/{i}", f"Title {i}", source, topic, pub, "snip", NOW.isoformat(), sent))
    for col, val in extra.items():
        c.execute(f"UPDATE items SET {col} = ? WHERE id = ?", (val, str(i)))


def classified(c, i, topic, hint, hours_ago, score, story="", summary="Sum"):
    add(c, i, hint, "A", hours_ago, assigned_topic=topic, score=score, story=story, summary=summary,
        classified_at=NOW.isoformat())


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

    def test_snippet_chars(self):
        long = b"<rss><channel><item><title>T</title><link>https://x</link><description>" + b"a" * 900 + b"</description></item></channel></rss>"
        self.assertEqual(len(digest.parse_feed(long, 500)[0]["snippet"]), 500)


class MigrationTests(unittest.TestCase):
    def test_old_database_gets_new_columns(self):
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE items (id TEXT PRIMARY KEY, url TEXT, title TEXT, source TEXT, topic TEXT, "
                  "published TEXT, snippet TEXT, first_seen TEXT, sent_at TEXT)")
        digest.migrate(c)
        cols = {r[1] for r in c.execute("PRAGMA table_info(items)")}
        self.assertTrue({"assigned_topic", "score", "summary", "story", "classified_at"} <= cols)
        digest.migrate(c)  # idempotent


class SelectTests(unittest.TestCase):
    def test_uses_llm_topic_and_score_and_skips_none_sent_old_low(self):
        c = db()
        classified(c, 1, "t1", "t2", 1, 9)       # hint t2 but the model says t1
        classified(c, 2, "t1", "t1", 2, 7)
        classified(c, 3, "t1", "t1", 3, 6)       # over the per-topic cap
        classified(c, 4, "none", "t1", 1, 9)     # not relevant
        classified(c, 5, "t2", "t2", 1, 3)       # score too low
        classified(c, 6, "t2", "t2", 100, 9)     # too old
        classified(c, 7, "t2", "t2", 1, 9)
        add(c, 8, "t2", "A", 1, sent="x", assigned_topic="t2", score=9, classified_at="x")
        add(c, 9, "t2", "A", 1)                  # never classified
        picked = digest.select(c, CONFIG, NOW)
        self.assertEqual([(t["key"], r["id"]) for t, r in picked], [("t1", "1"), ("t1", "2"), ("t2", "7")])

    def test_same_story_kept_once(self):
        c = db()
        classified(c, 1, "t1", "t1", 1, 9, story="big event")
        classified(c, 2, "t1", "t1", 2, 8, story="big event")
        classified(c, 3, "t1", "t1", 3, 7, story="other")
        picked = digest.select(c, CONFIG, NOW)
        self.assertEqual([r["id"] for _, r in picked], ["1", "3"])

    def test_fallback_without_llm_uses_hint_topic(self):
        c = db()
        add(c, 1, "t1", "A", 1)
        add(c, 2, "t2", "A", 1)
        self.assertEqual(digest.select(c, CONFIG, NOW), [])
        picked = digest.select(c, CONFIG, NOW, include_unclassified=True)
        self.assertEqual([r["id"] for _, r in picked], ["1", "2"])

    def test_topic_override_and_cap_keeps_every_topic_represented(self):
        c = db()
        cfg = {"settings": dict(SETTINGS, max_total=3),
               "topics": [dict(CONFIG["topics"][0], per_topic=3), CONFIG["topics"][1]]}
        classified(c, 1, "t1", "t1", 1, 6)
        classified(c, 2, "t1", "t1", 2, 6.5)
        classified(c, 3, "t1", "t1", 3, 7)
        classified(c, 4, "t2", "t2", 1, 9)
        picked = digest.select(c, cfg, NOW)
        self.assertEqual(len(picked), 3)
        self.assertIn("4", [r["id"] for _, r in picked])  # lowest scores are dropped, not the last topic

    def test_topic_overrides_for_window_and_threshold(self):
        c = db()
        cfg = {"settings": SETTINGS,
               "topics": [dict(CONFIG["topics"][0], max_age_hours=96, min_score=4), CONFIG["topics"][1]]}
        classified(c, 1, "t1", "t1", 80, 4.5)   # old and low, but inside this topic's own limits
        classified(c, 2, "t2", "t2", 80, 4.5)   # same numbers, default limits: excluded
        picked = digest.select(c, cfg, NOW)
        self.assertEqual([r["id"] for _, r in picked], ["1"])
        lines = digest.report(c, cfg, NOW)
        self.assertIn("t1", lines[0])
        self.assertIn("unsent=  1", lines[0])

    def test_candidates_interleave_sources_and_skip_classified(self):
        c = db()
        add(c, 1, "t1", "A", 1)
        add(c, 2, "t1", "A", 2)
        add(c, 3, "t1", "B", 3)
        classified(c, 4, "t1", "t1", 1, 5)
        cfg = {"settings": dict(SETTINGS, candidates_per_topic=2), "topics": CONFIG["topics"]}
        self.assertEqual([r["id"] for r in digest.candidates(c, cfg, NOW)], ["1", "3"])


class LlmTests(unittest.TestCase):
    def rows(self):
        c = db()
        add(c, 1, "t1", "A", 1)
        add(c, 2, "t1", "A", 2)
        add(c, 3, "t2", "A", 3)
        return c, c.execute("SELECT * FROM items ORDER BY id").fetchall()

    def test_parse_tolerates_wrapping_text_and_bad_entries(self):
        _, rows = self.rows()
        text = 'Here you go:\n[{"i":1,"topic":"t1","score":11,"story":"A B","summary":"One."},' \
               '{"i":2,"topic":"bogus","score":3,"summary":"Two."},{"i":99,"topic":"t1","score":1},{"nope":1}]'
        res = digest.parse_llm_json(text, rows, {"t1", "t2"})
        self.assertEqual(res["1"]["score"], 10.0)      # clamped
        self.assertEqual(res["1"]["story"], "a b")
        self.assertEqual(res["2"]["topic"], "none")    # unknown topic becomes none
        self.assertEqual(len(res), 2)

    def test_parse_salvages_a_truncated_reply(self):
        _, rows = self.rows()
        text = '[{"i":1,"topic":"t1","score":8,"story":"a","summary":"Done."},\n{"i":2,"topic":"t2","score":7,"sto'
        res = digest.parse_llm_json(text, rows, {"t1", "t2"})
        self.assertEqual(list(res), ["1"])

    def test_parse_rejects_garbage(self):
        _, rows = self.rows()
        with self.assertRaises(ValueError):
            digest.parse_llm_json("sorry, cannot", rows, {"t1"})

    def test_classify_batches_stores_results_and_survives_a_failed_batch(self):
        c, rows = self.rows()
        calls = []

        def fake(api_key, system, user):
            calls.append(user)
            if len(calls) == 2:
                raise RuntimeError("boom")
            return json.dumps([{"i": 1, "topic": "t1", "score": 8, "story": "s", "summary": "Resumen."},
                               {"i": 2, "topic": "none", "score": 2, "story": "x", "summary": "n/a"}])

        ok, errors = digest.classify(c, CONFIG, rows, "key", NOW, call=fake)
        self.assertEqual((ok, len(errors), len(calls)), (2, 1, 2))  # batch size 2 -> 2 batches
        r = c.execute("SELECT * FROM items WHERE id='1'").fetchone()
        self.assertEqual((r["assigned_topic"], r["score"], r["summary"]), ("t1", 8, "Resumen."))
        self.assertIsNone(c.execute("SELECT classified_at FROM items WHERE id='3'").fetchone()[0])

    def test_system_prompt_lists_only_described_topics(self):
        cfg = {"settings": SETTINGS, "topics": CONFIG["topics"] + [{"key": "data", "label": "D", "feeds": []}]}
        system = digest.build_system(cfg)
        self.assertIn("- t1: first", system)
        self.assertNotIn("data:", system)


class MonitorArgyTests(unittest.TestCase):
    SERIES = [
        {"id": "ipc_mensual", "nombre": "IPC var. mensual", "unidad": "pct", "decimales": 1, "frecuencia": "M",
         "ultimaFecha": "2026-09-01", "ultimoValor": 1.93361, "variacionUltimo": 0.274404},
        {"id": "dolar", "nombre": "Dolar", "unidad": "ars", "decimales": 0, "frecuencia": "D",
         "ultimaFecha": "2026-11-06", "ultimoValor": 1500.0, "variacionUltimo": 5.0},
    ]

    def test_first_run_stores_baseline_only(self):
        changes, items = digest.monitor_argy_items(self.SERIES, {})
        self.assertEqual(len(changes), 2)
        self.assertEqual(items, [])

    def test_announces_changed_non_daily_series_in_spanish(self):
        seen = {"ipc_mensual": "2026-08-01", "dolar": "2026-11-05"}
        changes, items = digest.monitor_argy_items(self.SERIES, seen)
        self.assertEqual(len(changes), 2)
        self.assertEqual(len(items), 1)  # the daily series is skipped
        self.assertEqual(items[0]["summary"],
                         "Nuevo dato, IPC var. mensual: 1.9% (2026-09), +0.3 respecto del dato anterior.")

    def test_unchanged_series_are_ignored(self):
        seen = {"ipc_mensual": "2026-09-01", "dolar": "2026-11-06"}
        self.assertEqual(digest.monitor_argy_items(self.SERIES, seen), ([], []))


class FormatTests(unittest.TestCase):
    def test_whole_sentence_is_the_link_and_text_is_escaped(self):
        c = db()
        classified(c, 1, "t1", "t1", 1, 9, summary="Riesgo país sube <900> puntos & preocupa.")
        picked = digest.select(c, CONFIG, NOW)
        msg = digest.build_messages(picked, NOW)[0]
        self.assertIn('<a href="https://x/1">Riesgo país sube &lt;900&gt; puntos &amp; preocupa. <i>(A)</i></a>', msg)

    def test_falls_back_to_title_when_no_summary(self):
        c = db()
        add(c, 1, "t1", "A", 1)
        picked = digest.select(c, CONFIG, NOW, include_unclassified=True)
        self.assertIn("Title 1", digest.build_messages(picked, NOW)[0])

    def test_splits_long_digests(self):
        many = [(CONFIG["topics"][0], {"title": "x" * 300, "url": "https://x/" + str(i), "source": "S"})
                for i in range(30)]
        msgs = digest.build_messages(many, NOW)
        self.assertGreater(len(msgs), 1)
        self.assertTrue(all(len(m) <= 4096 for m in msgs))

    def test_sections_are_not_split_from_their_header(self):
        topics = CONFIG["topics"]
        long_a = [(topics[0], {"title": "a" * 280, "url": f"https://x/a{i}", "source": "S"}) for i in range(10)]
        long_b = [(topics[1], {"title": "b" * 280, "url": f"https://x/b{i}", "source": "S"}) for i in range(10)]
        msgs = digest.build_messages(long_a + long_b, NOW)
        self.assertGreater(len(msgs), 1)
        for m in msgs[1:]:
            self.assertTrue(m.startswith("<b>"), m[:40])  # a new message opens with a section header
        self.assertTrue(all(len(m) <= 4096 for m in msgs))

    def test_empty(self):
        self.assertIn("Nothing new", digest.build_messages([], NOW)[0])


if __name__ == "__main__":
    unittest.main()
