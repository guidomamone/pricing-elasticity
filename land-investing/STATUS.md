# STATUS

Update this file at the end of every work session. Keep it under 40 lines.

**Current phase:** 1, Prove it in Marion. **Next task:** T5 in `TASKS.md`.

## Done
- Phase 0: Marion map (`map/index.html`) with population by block group, new construction by year (1980+), and 82,147 vacant lots with price filters.
- Data: all 286,275 Marion parcels from the Florida Statewide Cadastral layer, 2026 tax roll (`scripts/fetch_parcels.py`, output in `data/raw/`, not committed).
- Private preview: https://claude.ai/artifact/2JcXrKPJm5ht1nvdzvCM9i (no street basemap there).

## Known issues
- Netlify site `marion-growth-map` exists but is empty. The account is out of credits.
- Sale codes 01 and 02 verified as arm's length in the DOR 2026 guide (see `reports/01_audit.md`).
- The roll's sale fields only hold 2025 and 2026 sales. No historical prices until past SDF files are loaded (T7).

## Task log
| Task | Status | Date | Notes |
|---|---|---|---|
| T1 | done | 2026-11-21 | Codes from DOR 2026 guide, 100% acre coverage. 285,947 unique parcels (layer now 286,216 rows). LAST_FULL_YEAR 2024. Roll holds 2025+ sales only |
| T2 | done | 2026-11-21 | 6,533 hexes x 10 origins. homes_T matches audit exactly. No labels past 2024 |
| T3 | done | 2026-11-21 | 30 features. As-of test passes (erase and scramble), negative control fails as it should. Roads are 2020, a known leak |
| T4 | done | 2026-11-21 | 2 baselines, logreg, LightGBM (with and without roads). Split checks pass. Frozen at git 43f3d46 |
| T5 | todo | | |
| T6 | todo | | |
| T7 | todo | | |
| T8 | todo | | |
