"""Snapshot Florida DOR NAL (parcels) and SDF (sales) files for one county and roll year.

DOR keeps only the current roll year on its data portal and removes older years (2025 was already
gone in November 2026). Run this once a year after the final roll is posted (about October) so a
history builds up in data/raw/dor/. Older years need a public records request (reports/07).

Usage: python scripts/fetch_dor_history.py [--year 2026] [--county "Marion 52"] [--kind F]
"""
import argparse
from pathlib import Path
from urllib.parse import quote

import requests

BASE = ("https://floridarevenue.com/property/dataportal/Documents/PTO Data Portal/"
        "Tax Roll Data Files/{file}/{year}{kind}/{county} {label} {file} {year}.zip")
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "dor"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--county", default="Marion 52", help='"<County name> <DOR county number>"')
    ap.add_argument("--kind", default="F", choices=["F", "P"], help="F final, P preliminary")
    a = ap.parse_args()
    label = "Final" if a.kind == "F" else "Preliminary"
    OUT.mkdir(parents=True, exist_ok=True)
    for file in ("NAL", "SDF"):
        url = BASE.format(file=file, year=a.year, kind=a.kind, county=a.county, label=label)
        dest = OUT / f"{a.county.replace(' ', '_')}_{file}_{a.year}{a.kind}.zip"
        if dest.exists():
            print(f"have {dest.name}")
            continue
        r = requests.get(quote(url, safe=":/"), timeout=300)
        if r.status_code != 200:
            print(f"{file} {a.year}{a.kind}: HTTP {r.status_code}, not on the portal")
            continue
        dest.write_bytes(r.content)
        print(f"{file} {a.year}{a.kind}: {len(r.content) / 1e6:.1f} MB -> {dest}")


if __name__ == "__main__":
    main()
