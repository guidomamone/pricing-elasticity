import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import monitor

BUILDINGS = json.loads(monitor.CONFIG_PATH.read_text())["buildings"]


def listing(id_, line1, unit="#1512", price=3200, bedrooms=2):
    return {"id": id_, "addressLine1": line1, "addressLine2": unit, "price": price,
            "bedrooms": bedrooms, "bathrooms": 2, "daysOnMarket": 4, "squareFootage": 1100,
            "formattedAddress": f"{line1}, {unit}, Miami, FL 33129", "listedDate": "2026-10-14T00:00:00.000Z"}


class MatchTests(unittest.TestCase):
    def test_exact_number(self):
        self.assertEqual(monitor.match_building(listing("a", "2333 Brickell Ave"), BUILDINGS)["name"], "Brickell Bay Club")

    def test_range_and_street_variants(self):
        self.assertEqual(monitor.match_building(listing("a", "1901 Brickell Avenue"), BUILDINGS)["name"], "Brickell Place")
        self.assertEqual(monitor.match_building(listing("a", "900 Brickell Key Blvd"), BUILDINGS)["name"], "Asia Brickell Key")

    def test_no_match(self):
        self.assertIsNone(monitor.match_building(listing("a", "2200 Brickell Ave"), BUILDINGS))
        self.assertIsNone(monitor.match_building(listing("a", "1918 Brickell Ave"), BUILDINGS))
        self.assertIsNone(monitor.match_building(listing("a", "2333 SW 8th St"), BUILDINGS))
        self.assertIsNone(monitor.match_building({"addressLine1": None}, BUILDINGS))


class FilterTests(unittest.TestCase):
    CFG = {"max_price": 4200, "min_bedrooms": 2}

    def check(self, **kw):
        return monitor.check_filters(listing("a", "2333 Brickell Ave", **kw), self.CFG)

    def test_pass_and_boundaries(self):
        self.assertEqual(self.check(price=4200, bedrooms=2), (None, []))

    def test_skips(self):
        self.assertIn("price", self.check(price=4201)[0])
        self.assertIn("bedrooms", self.check(bedrooms=1)[0])
        self.assertIn("bedrooms", self.check(bedrooms=0)[0])  # studio is a real 0, not missing

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

    def test_message_has_days_on_market_and_warning(self):
        msg = monitor.format_message(listing("a", "2333 Brickell Ave"), BUILDINGS[0], ["bedrooms missing"])
        self.assertIn("Days on market: 4", msg)
        self.assertIn("⚠️ bedrooms missing", msg)


class RunTests(unittest.TestCase):
    def run_main(self, listings, tmp, argv=()):
        env = {"RENTCAST_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}
        with mock.patch.object(monitor, "STATE_PATH", Path(tmp) / "state.json"), \
             mock.patch.dict("os.environ", env), \
             mock.patch.object(monitor, "fetch_listings", return_value=listings), \
             mock.patch.object(monitor, "send_telegram") as send:
            monitor.main(list(argv))
        return send, json.loads((Path(tmp) / "state.json").read_text())

    def test_alerts_once(self):
        data = [listing("a", "2333 Brickell Ave"), listing("b", "10 Other St")]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(state["quota"]["used"], 1)
            send, state = self.run_main(data, tmp)
            self.assertEqual(send.call_count, 0)
            self.assertEqual(state["quota"]["used"], 2)

    def test_filters_and_skipped_digest(self):
        data = [listing("a", "2333 Brickell Ave", price=4200),
                listing("b", "2333 Brickell Ave", price=4201),
                listing("c", "2333 Brickell Ave", bedrooms=1)]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            self.assertEqual(list(state["seen"]), ["a"])
            texts = [c.args[2] for c in send.call_args_list]
            self.assertEqual(len(texts), 2)  # 1 alert + 1 digest
            self.assertIn("Filtered out", texts[1])
            self.assertEqual(sorted(state["skipped_reported"]), ["b", "c"])
            send, _ = self.run_main(data, tmp)  # same data next day: nothing new to report
            self.assertEqual(send.call_count, 0)

    def test_schema_change_warning(self):
        data = [listing(str(i), "2333 Brickell Ave", bedrooms=None) for i in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            send, state = self.run_main(data, tmp)
            texts = [c.args[2] for c in send.call_args_list]
            self.assertEqual(len(state["seen"]), 4)  # still alerted, with warnings
            self.assertTrue(any("data format may have changed" in t for t in texts))

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
