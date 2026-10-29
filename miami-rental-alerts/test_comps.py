import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import comps
import monitor


def row(addr2, status, price, beds=2, sqft=1100, listed="2026-04-20", removed=None, dom=180, line1="2451 Brickell Ave", **kw):
    r = {"id": f"{line1}-{addr2}-{listed}", "addressLine1": line1, "addressLine2": addr2, "status": status,
         "price": price, "bedrooms": beds, "bathrooms": 2, "squareFootage": sqft, "listedDate": listed,
         "removedDate": removed, "daysOnMarket": dom}
    r.update(kw)
    return r


class HelperTests(unittest.TestCase):
    def test_unit_key(self):
        for text in ("Apt 20M", "Unit 20M", "#20-M", "20m", "APARTMENT 20M"):
            self.assertEqual(comps.unit_key(text), "20m", text)
        self.assertNotEqual(comps.unit_key("Apt 2OM1"), "20m")

    def test_median_ignores_missing(self):
        self.assertEqual(comps.median([3000, None, 4000, 5000]), 4000)
        self.assertIsNone(comps.median([None]))


class EndToEnd(unittest.TestCase):
    def test_full_run_with_canned_responses(self):
        target = row("Apt 20M", "Active", 3950, history={
            "2026-04-20": {"event": "Rental Listing", "price": 4100, "daysOnMarket": 1},
            "2026-07-01": {"event": "Price Change", "price": 3950, "daysOnMarket": 72}})
        building = [target, row("Apt 6C", "Inactive", 3400, listed="2026-02-01", removed="2026-03-15", dom=42),
                    row("Apt 9A", "Inactive", 3300, beds=1, sqft=800, listed="2026-01-10", removed="2026-02-02", dom=23),
                    row("Unit 5", "Inactive", 2900, line1="2475 Brickell Ave")]  # other building: ignored
        responses = iter([
            {"rent": 3650, "rentRangeLow": 3300, "rentRangeHigh": 4000, "latitude": 25.75, "longitude": -80.2,
             "comparables": [{"price": 3600, "bedrooms": 2, "bathrooms": 2, "squareFootage": 1150, "distance": 0.1,
                              "correlation": 0.98, "formattedAddress": "2475 Brickell Ave, Apt 5"}]},
            [r for r in building if r["status"] == "Inactive"],   # building, past
            [target],                                              # building, active
            [row("Unit 7", "Inactive", 3500, line1="2475 Brickell Ave"), row("Apt 6C", "Inactive", 3400)],  # nearby
        ])
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(monitor, "STATE_PATH", Path(tmp) / "state.json"), \
             mock.patch.object(comps, "RAW_PATH", Path(tmp) / "raw.json"), \
             mock.patch.dict("os.environ", {"RENTCAST_API_KEY": "k"}), \
             mock.patch.object(comps.Budget, "call", side_effect=lambda path, params: next(responses)), \
             mock.patch.object(sys, "argv", ["comps.py"]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                comps.main()
            text = out.getvalue()
            self.assertTrue((Path(tmp) / "raw.json").exists())
        self.assertIn("estimate $3,650", text)
        self.assertIn("<== TARGET UNIT", text)
        self.assertIn("2026-07-01: Price Change at $3,950", text)
        self.assertIn("2451 Brickell Ave, 2bd only", text.replace("=== ", ""))
        self.assertNotIn("2475 Brickell Ave Unit 5", text)
        self.assertIn("Closed 2bd rentals within 0.5 mi", text.replace("=== ", ""))


if __name__ == "__main__":
    unittest.main()
