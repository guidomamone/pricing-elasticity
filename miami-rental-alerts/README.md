# Miami rental alerts

Daily Telegram alerts for new rentals in Brickell, using the RentCast API (no scraping). Each run sends two lists: (1) new listings in the tennis-court buildings, and (2) new listings in the Brickell zip codes that are not in a tennis-court building, so nothing is repeated.

- `buildings.json`: search area, filters (`max_price`, `min_bedrooms`), `brickell_zips` (33129, 33130, 33131), monthly request cap, and the tennis-court buildings. Add a building by appending an entry (`numbers` or `number_range`, plus `street`).
- `monitor.py`: one API request per run, matched locally to the buildings. New listings go to Telegram. `state.json` stores seen listings and the monthly request count.
- The RentCast Developer plan includes 50 requests/month, then $0.20 each. The script stops at `max_requests_per_month` (45) so it cannot generate overage fees.

Local test (prints alerts, sends nothing):

    read -rs RENTCAST_API_KEY && export RENTCAST_API_KEY
    python3 miami-rental-alerts/monitor.py --dry-run

Unit tests: `cd miami-rental-alerts && python3 -m unittest -v test_monitor`

Note: GitHub only runs scheduled workflows from the default branch, so this must be merged there to start running.

## Tennis-court building list

`tennis_buildings.csv` keeps every building with tennis courts from the source lists (condoblackbook, tennislocal), including the ones not tracked, so nothing is lost if the area changes. `status` shows what is currently in `buildings.json`. To track more buildings, add an entry to `buildings.json` (street plus `numbers`) using the address from the CSV.

Sources: condoblackbook "Complete List of Miami Condos with Tennis Courts", tennislocal "Downtown & Brickell". Court counts are marketing data and may be outdated.
