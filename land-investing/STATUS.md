# STATUS

Update this file at the end of every work session. Keep it under 40 lines.

**Current phase:** 1, Prove it in Marion. **Gate: PASS on the 5-year 2015 cell, reported to Guido 2026-11-21. Waiting for his review.** Do not start T6 or T8 before he answers.

## Done
- Phase 0: Marion map (`map/index.html`) with population, new construction by year (1980+), 82,147 vacant lots.
- Phase 1 T1 to T5 and T7. Verdict in `reports/05_backtest.md`: LightGBM top 10% lift 7.96x and capture 73.8% (5y from 2015) versus best baseline 4.72x and 55.6%. 3 of 4 test cells pass; 15y from 2009 ties the front baseline.
- Private preview: https://claude.ai/artifact/2JcXrKPJm5ht1nvdzvCM9i (no street basemap there).

## Known issues
- Netlify site `marion-growth-map` exists but is empty. The account is out of credits.
- The roll's sale fields only hold 2025 and 2026 sales. No historical prices (T7: DOR removes past years; public records request needed).
- `excluded_share` leaks a little through 009 and 094 codes. Small effect, v2 should drop them (`reports/05_backtest.md`, Leakage review).
- Probabilities are off in level (training windows were the crash or the 2000s boom). Rankings hold. Recalibrate before using probabilities as numbers.
- Parcel layer now has 286,216 rows (was 286,275). 285,947 unique parcels after dissolving multipart pieces.

## Task log
| Task | Status | Date | Notes |
|---|---|---|---|
| T1 | done | 2026-11-21 | Codes from DOR 2026 guide, 100% acre coverage. LAST_FULL_YEAR 2024 |
| T2 | done | 2026-11-21 | 6,533 hexes x 10 origins. homes_T matches audit exactly |
| T3 | done | 2026-11-21 | 30 features. As-of test passes, negative control works. Roads are 2020 |
| T4 | done | 2026-11-21 | Baselines, logreg, LightGBM (+ no-roads). Frozen at git 43f3d46 |
| T5 | done | 2026-11-21 | PASS on gate cell. Leakage review added |
| T6 | todo | | Waits for Guido |
| T7 | done | 2026-11-21 | Past NAL/SDF not public. `scripts/fetch_dor_history.py` archives yearly |
| T8 | todo | | Waits for Guido |
