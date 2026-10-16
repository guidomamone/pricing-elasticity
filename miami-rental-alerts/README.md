# Miami rental alerts

Daily Telegram alerts for new rental listings in specific Brickell buildings, using the RentCast API (no scraping).

- `buildings.json`: search area, monthly request cap, and the tracked buildings. Add a building by appending an entry (`numbers` or `number_range`, plus `street`).
- `monitor.py`: one API request per run, matched locally to the buildings. New listings go to Telegram. `state.json` stores seen listings and the monthly request count.
- The RentCast Developer plan includes 50 requests/month, then $0.20 each. The script stops at `max_requests_per_month` (45) so it cannot generate overage fees.

Local test (prints alerts, sends nothing):

    read -rs RENTCAST_API_KEY && export RENTCAST_API_KEY
    python3 miami-rental-alerts/monitor.py --dry-run

Unit tests: `cd miami-rental-alerts && python3 -m unittest -v test_monitor`

Note: GitHub only runs scheduled workflows from the default branch, so this must be merged there to start running.
