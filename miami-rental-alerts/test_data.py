import csv
import unittest
from pathlib import Path

DATA = Path(__file__).parent / "data"


def load(name):
    with open(DATA / name) as f:
        return list(csv.DictReader(f))


class DataTests(unittest.TestCase):
    def test_compass_rows_are_consistent(self):
        rows = load("compass_past_rentals_2451.csv")
        self.assertEqual(len(rows), 33)
        units = [r["unit"] for r in rows]
        self.assertEqual(len(units), len(set(units)))
        for r in rows:
            self.assertRegex(r["month"], r"^\d{4}-\d{2}$")
            self.assertTrue(r["unit"].endswith(r["line"]))
            self.assertGreater(float(r["contract_price"]), 0)

    def test_views_follow_the_line_table(self):
        views = {r["line"]: r["view"] for r in load("line_views_2451.csv")}
        for r in load("compass_past_rentals_2451.csv"):
            self.assertEqual(r["view"], views.get(r["line"], "unknown"), r["unit"])
        self.assertEqual(views["M"], "parking_lot")

    def test_target_unit_is_in_the_active_file(self):
        active = {r["unit"]: r for r in load("active_listings_2451.csv")}
        self.assertEqual(active["20M"]["asking_price"], "3950")
        self.assertEqual(active["20M"]["view"], "parking_lot")


if __name__ == "__main__":
    unittest.main()
