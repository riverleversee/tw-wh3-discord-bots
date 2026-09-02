# Buildhelper / Pickban Bot

Discord bot for Total War: Warhammer III land-battle tooling. The core pick/ban feature is a **numerically optimized decision helper**: it searches a faction matchup matrix under your constraints and returns **optimal pick and ban options** with expected matchup outcomes.

Also includes matchup build help (`!MUhelp`), custom MU matrix uploads, and faction win-rate stats.

## Pick/ban as constrained optimization

Commands `!pick3`, `!pick2`, `!pick1`, `!counterpick3`, and `!counterpick2` model pick/ban as an optimization problem:

- **Objective:** maximize expected matchup value from a win-rate / advantage matrix
- **Constraints:** unplayable factions, opponent unplayables, global bans, prior bans in a series, must-include factions, avoid lists, and custom uploaded matrices
- **Output:** all tied-optimal pick/ban combinations and the expected matchups for each

Use `!info` / `!infopick3` (and language variants) for full option documentation.

## Requirements

- Python 3.10+
- See `requirements.txt`

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and set your Discord bot token and role IDs.
3. Run from this directory:

```bash
python discordbotwstatsbeta.py
```

## Data layout

- `MUmatrix.csv`, `MUmatrixstrat.csv` — default matchup matrices
- `documentation/` — command help text
- `factionstats/` — win stat files
- `buildhelp/<FAC1>/<FAC2>/buildtext.txt` and `IMAG*.jpg` — full build library (~224 images)

This repo includes only **samples/** under `buildhelp`-style paths. Commands that need the full image tree require copying `buildhelp/` from the path in `SOURCE.txt`.

## Notes

- No Discord server links in this repo.
- See `REVIEW_NOTES.md` for deferred improvements.
