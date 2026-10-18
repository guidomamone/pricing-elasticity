import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import monitor

BUILDINGS = json.loads(monitor.CONFIG_PATH.read_text())["buildings"]


def listing(id_, line1, unit="#1512", price=3200, bedrooms=2, zip_="33129", sqft=1100):
    return {"id": id_, "addressLine1": line1, "addressLine2": unit, "price": price, "zipCode": zip_,
            "bedrooms": bedrooms, "bathrooms": 2, "daysOnMarket": 4, "squareFootage": sqft,
            "formattedAddress": f"{line1}, {unit}, Miami, FL 33129", "listedDate": "2026-10-14T00:00:00.000Z"}


class MatchTests(unittest.TestCase):
    def test_exact_number(self):
        self.assertEqual(monitor.match_building(listing("a", "2333 Brickell Ave"), BUILDINGS)["name"], "Brickell Bay Club")

    def test_range_and_street_variants(self):
        self.assertEqual(monitor.match_building(listing("a", "1901 Brickell Avenue"), BUILDINGS)["name"], "Brickell Place")
        self.assertEqual(monitor.match_building(listing("a", "900 Brickell Key Blvd"), BUILDINGS)["name"], "Asia Brickell Key")

    def test_streets_with_ordinals_and_directions(self):
        for line1, name in [("175 SE 25 Rd", "Una"), ("175 SE 25th Rd", "Una"), ("200 SE 15th Rd", "Brickell Harbour"),
                            ("10 SW South River Dr", "Neo Lofts"), ("68 SE 6th St", "Reach Brickell City Centre"),
                            ("801 S Miami Ave", "SLS Lux Brickell"), ("850 N Miami Ave", "Madison Downtown"),
                            ("851 NE 1st Ave", "Paramount Miami Worldcenter"), ("888 Brickell Key Dr", "One Tequesta Point"),
                            ("901 Brickell Key Blvd", "Carbonell"), ("1450 Brickell Bay Dr", "Costa Bella")]:
            self.assertEqual(monitor.match_building(listing("a", line1), BUILDINGS)["name"], name, line1)

    def test_no_duplicate_buildings(self):
        keys = [(tuple(monitor.normalize_street(b["street"])), n) for b in BUILDINGS for n in b.get("numbers", [])]
        self.assertEqual(len(keys), len(set(keys)))

    def test_no_match(self):
        self.assertIsNone(monitor.match_building(listing("a", "2200 Brickell Ave"), BUILDINGS))
        self.assertIsNone(monitor.match_building(listing("a", "1918 Brickell Ave"), BUILDINGS))
        self.assertIsNone(monitor.match_building(listing("a", "2333 SW 8th St"), BUILDINGS))
        self.assertIsNone(monitor.match_building({"addressLine1": None}, BUILDINGS))


class FilterTests(unittest.TestCase):
    CFG = {"max_price": 4200, "min_bedrooms": 2, "min_sqft": 1000}

    def check(self, **kw):
        return monitor.check_filters(listing("a", "2333 Brickell Ave", **kw), self.CFG)

    def test_pass_and_boundaries(self):
        self.assertEqual(self.check(price=4200, bedrooms=2), (None, []))

    def test_skips(self):
        self.assertIn("price", self.check(price=4201)[0])
        self.assertIn("bedrooms", self.check(bedrooms=1)[0])
        self.assertIn("bedrooms", self.check(bedrooms=0)[0])  # studio is a real 0, not missing

    def test_sqft_filter(self):
        self.assertEqual(self.check(sqft=1000), (None, []))
        self.assertIn("999 sqft < 1,000", self.check(sqft=999)[0])
        reason, warns = self.check(sqft=None)  # often absent in real listings: pass with a warning
        self.assertIsNone(reason)
        self.assertEqual(len(warns), 1)

    def test_missing_or_garbage_never_filters_out(self):
        for bad in (None, "", "N/A", True):
            reason, warns = self.check(bedrooms=bad)
            self.assertIsNone(reason)
            self.assertEqual(len(warns), 1)
            reason, warns = self.check(price=bad)
            self.assertIsNone(reason)
            self.assertEqual(len(warns), 1)

    def test_numeric_strings_parse(self):
        self.assertEqual(self.check(price="3500", bedrooms="2"), (None, []))

    def test_entry_has_days_on_market_and_warning(self):
        msg = monitor.format_entry(listing("a", "2333 Brickell Ave"), "Brickell Bay Club", ["bedrooms missing"])
        self.assertIn("4d on market", msg)
        self.assertIn("⚠️ bedrooms missing", msg)
        self.assertIn("<b>Brickell Bay Club #1512</b>", msg)

    def test_general_brickell_entry_uses_address_as_title(self):
        msg = monitor.format_entry(listing("a", "1050 Brickell Ave"), None)
        self.assertIn("<b>1050 Brickell Ave, #1512</b>", msg)
        self.assertIn("Search on Zillow", msg)

    def test_digest_single_message_with_empty_sections(self):
        self.assertEqual(monitor.build_digest([("A", []), ("B", [])]),
                         [("A\n\nNothing new today.\n\nB\n\nNothing new today.", [])])

    def test_digest_chunking(self):
        items = [(listing(str(i), "2333 Brickell Ave"), "x" * 1000) for i in range(10)]
        parts = monitor.build_digest([("HEAD1", items), ("HEAD2", [])], limit=3800)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(text) <= 3800 for text, _ in parts))
        self.assertEqual(sum(len(g) for _, g in parts), 10)
        self.assertIn("HEAD1 (cont.)", parts[1][0])
        self.assertTrue(parts[-1][0].endswith("HEAD2\n\nNothing new today."))


class RunTests(unittest.TestCase):
    def run_main(self, listings, tmp, argv=()):
        env = {"RENTCAST_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}
        with mock.patch.object(monitor, "STATE_PATH", Path(tmp) / "state.json"), \
             mock.patch.dict("os.environ", env), \
             mock.patch.object(monitor, "fetch_listings", return_value=listings), \
             mock.patch.object(monitor, "send_telegram") as send:
            monitor.main(list(argv))
        return send, json.loads((Path(tmp) / "state.json").read_text())

    def texts(self, send):
        return [c.args[2] for c in send.call_args_list]

    def test_two_lists_one_message_no_repeats(self):
        data = [listing("a", "2333 Brickell Ave"),                       # tennis building
                listing("b", "1627 Brickell Ave", zip_="33131"),         # tennis building, other zip
                listing("c", "1050 Brickell Ave", zip_="33131"),         # general Brickell
                listing("d", "10 Other St", zip_="33140")]               # outside Brickell
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            texts = self.texts(send)
            self.assertEqual(len(texts), 1)
            tennis, brickell = texts[0].split("🏙")
            self.assertIn("Tennis-court buildings: 2 new", tennis)
            self.assertIn("Brickell, other buildings: 1 new", brickell)
            self.assertIn("2333 Brickell Ave", tennis)
            self.assertIn("1627 Brickell Ave", tennis)
            self.assertNotIn("2333 Brickell Ave", brickell)
            self.assertNotIn("1627 Brickell Ave", brickell)
            self.assertIn("1050 Brickell Ave", brickell)
            self.assertEqual(sorted(state["seen"]), ["a", "b", "c"])
            self.assertEqual(state["quota"]["used"], 1)
            send, state = self.run_main(data, tmp)
            texts = self.texts(send)  # nothing new: still one message, both lists saying so
            self.assertEqual(len(texts), 1)
            self.assertEqual(texts[0].count("Nothing new today."), 2)
            self.assertIn("Tennis-court buildings: 0 new", texts[0])
            self.assertEqual(state["quota"]["used"], 2)

    def test_lists_sorted_by_price(self):
        data = [listing("a", "2333 Brickell Ave", price=4000), listing("b", "2333 Brickell Ave", price=3000)]
        with tempfile.TemporaryDirectory() as tmp:
            send, _ = self.run_main(data, tmp)
            text = self.texts(send)[0]
            self.assertLess(text.index("$3,000"), text.index("$4,000"))

    def test_general_brickell_filtered_silently(self):
        data = [listing("a", "1050 Brickell Ave", zip_="33131", price=5000),
                listing("b", "1060 Brickell Ave", zip_="33131", bedrooms=1)]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            texts = self.texts(send)  # both lists empty, and no "filtered out" digest for non-tennis
            self.assertEqual(len(texts), 1)
            self.assertEqual(texts[0].count("Nothing new today."), 2)
            self.assertEqual(state["seen"], {})

    def test_filters_and_skipped_digest(self):
        data = [listing("a", "2333 Brickell Ave", price=4200),
                listing("b", "2333 Brickell Ave", price=4201),
                listing("c", "2333 Brickell Ave", bedrooms=1)]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            self.assertEqual(list(state["seen"]), ["a"])
            texts = self.texts(send)
            self.assertEqual(len(texts), 2)  # the two lists, then the filtered-out digest
            self.assertIn("Tennis-court buildings: 1 new", texts[0])
            self.assertIn("Brickell, other buildings: 0 new", texts[0])
            self.assertIn("Filtered out", texts[1])
            self.assertEqual(sorted(state["skipped_reported"]), ["b", "c"])
            send, _ = self.run_main(data, tmp)  # same data next day: no repeated filtered-out digest
            texts = self.texts(send)
            self.assertEqual(len(texts), 1)
            self.assertEqual(texts[0].count("Nothing new today."), 2)

    def test_schema_change_warning(self):
        data = [listing(str(i), "2333 Brickell Ave", bedrooms=None) for i in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            texts = [c.args[2] for c in send.call_args_list]
            self.assertEqual(len(state["seen"]), 4)  # still alerted, with warnings
            self.assertTrue(any("data format may have changed" in t for t in texts))

    def test_missing_sqft_alerts_with_warning_but_no_schema_alarm(self):
        data = [listing(str(i), "2333 Brickell Ave", sqft=None) for i in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            texts = self.texts(send)
            self.assertEqual(len(state["seen"]), 4)
            self.assertEqual(texts[0].count("sqft missing"), 4)
            self.assertFalse(any("data format may have changed" in x for x in texts))

    def test_small_units_filtered(self):
        data = [listing("a", "2333 Brickell Ave", sqft=999), listing("b", "2333 Brickell Ave", sqft=1000)]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            self.assertEqual(list(state["seen"]), ["b"])
            self.assertIn("999 sqft &lt; 1,000", self.texts(send)[1])  # filtered-out digest

    def test_dry_run_does_not_mark_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main([listing("a", "2333 Brickell Ave")], tmp, ["--dry-run"])
            self.assertEqual(send.call_count, 0)
            self.assertEqual(state["seen"], {})

    def test_cap_blocks_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            from datetime import date
            (Path(tmp) / "state.json").write_text(json.dumps(
                {"quota": {"month": date.today().strftime("%Y-%m"), "used": 45}, "seen": {}}))
            with mock.patch.object(monitor, "fetch_listings") as fetch:
                env = {"RENTCAST_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}
                with mock.patch.object(monitor, "STATE_PATH", Path(tmp) / "state.json"), \
                     mock.patch.dict("os.environ", env), mock.patch.object(monitor, "send_telegram"):
                    monitor.main([])
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
