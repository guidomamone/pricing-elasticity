# land-investing: instructions for Claude sessions

Read in this order, and stop when you have what you need:
1. `README.md`: what this is and the map of files.
2. `STATUS.md`: what is done and what is next. Update it when you finish a task.
3. `TASKS.md`: the work list. Do the first task not marked done.
4. `PLAN.md`: the strategy and phase gates. `docs/BACKTEST.md`: how the model is trained and tested.

Rules:
- `docs/reference/` is background. `docs/archive/` is dead. Never execute tasks from either.
- Work only inside `land-investing/`. Other folders in this repo are unrelated projects.
- No em-dashes in prose. Use a period or a comma.
- Never commit `data/raw/`. Never commit API keys.
- Verify, don't guess. Mark any URL or data claim you could not open as `UNVERIFIED`.
- Do not start a later phase before the current phase's gate in `PLAN.md` has been reported to Guido.
