# Handoff (state as of 2026-11-07)

## What this is
Daily RentCast check of Brickell rentals, sent to Telegram as ONE message with two lists (tennis-court buildings, then other Brickell zips 33129/33130/33131) plus a numbered map photo. Runs from GitHub Actions Mon, Tue, Thu, Fri, Sat (no Wednesdays or Sundays). Repo: guidomamone/pricing-elasticity. Work branch: claude/kind-pascal-7a6gcy.

## Pending, needs the owner
- Branch has UNMERGED commits (Edgewater/Downtown/Midtown tennis buildings, 3.5 mi circle, 2nd page when the first is full, comps tool offline mode, 2451 CSV data and offer analysis, no-Sunday cron). Nothing here is live until merged to main. Merge with a PR (squash); the owner approves each merge.
- After merging: trigger one real run and check the Telegram message.
- Telegram bot token was pasted in chat (bot RentHunt). Owner must /revoke in @BotFather and run: gh secret set TELEGRAM_BOT_TOKEN --repo guidomamone/pricing-elasticity
- Secrets already in GitHub: RENTCAST_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (chat id 1642622577).

## Settings (miami-rental-alerts/buildings.json)
max_price 4200, min_bedrooms 2, min_sqft 1000 (missing data passes with a warning), search circle 25.776,-80.192 radius 3.5 mi, daysOld 3, limit 500 (second page if full, MAX_PAGES 2), cap 45 requests/month (RentCast Developer plan: 50 free, then $0.20). Tennis buildings are matched by address anywhere in the circle; non-tennis listings only in the Brickell zips.

## Gotchas learned
- GitHub only dispatches a NEW workflow file from main; an existing one can be dispatched on a branch ref (uses the branch's version).
- The sandbox cannot reach Telegram, Compass, OSM or artifact blobs. Run things through Actions and read logs with the GitHub tools.
- RentCast gives asking prices only, not contract prices. Compass "Past Rentals" has contract prices (owner pastes screenshots).
- Chain test and push with && (twice a push went out with a failing test).
- Owner preferences: no em dashes (use a period or comma), now chatting in English, CSVs should be plain tables with no prose.

## Offer work for unit 20M, 2451 Brickell Ave (owner's own lease offer)
Data in miami-rental-alerts/data/ (compass_past_rentals_2451.csv, line_views_2451.csv, active_listings_2451.csv). Run: python3 -I miami-rental-alerts/offer_analysis.py. 20M faces the parking lot (M line). Asking 3,950, on market since 2026-08-07 (earlier listing 2026-06-28 at 4,380). Ph M (same line) leased 3,600 in May 2026. 2bd contracts: water view n=9 median 4,200, mean 4,083, range 3,600-4,500; parking lot n=5 median 3,100, mean 3,340, range 3,000-4,000. Defensible range about 3,450-3,780. Owner anchors at 3,600 on a 12 month lease; ceiling 3,750. Offer text was drafted with three bullets (time on market, comps, view premium). Line views: water B C E F G H J S U, limited water T, parking K L M N P.

## Tools
- comps.py (workflow "Rent comps"): RentCast AVM, building history, nearby closed rentals; input from_run re-reads a saved run with no API requests.
- monitor.py --dry-run [--days N] prints without sending; the workflow input dry_run does the same and saves last_map.png as an artifact.
- Tests: cd miami-rental-alerts && python3 -m unittest -v test_monitor test_mapview test_comps test_data
