# TW WH3 Discord Bots

Two Discord bots for the Total War: Warhammer III competitive community:

| Folder | Purpose |
|--------|---------|
| [Ladder/](Ladder/) | Matchmaking queue with **bilateral preference optimization** — pairs players and selects match settings that maximize combined satisfaction for both sides |
| [Buildhelper-Pickban/](Buildhelper-Pickban/) | **Numerically optimized pick/ban decision helper** — recommends optimal picks and bans under constraints, plus matchup build help and faction stats |

## Pick/ban optimization

The Buildhelper bot treats pick/ban as a constrained optimization problem over a faction matchup matrix. Commands like `!pick3`, `!pick2`, and `!pick1` take your constraints (unplayable factions, global bans, series history, must-include lists, avoid lists, and custom matrices) and enumerate the valid decision space to surface **optimal pick and ban options** with expected matchup outcomes.

## Matchmaking optimization

The Ladder bot stores each player's preferences as numeric weights (`Preferred` / `Allowed` / `Never`) across game mode, series length, pick format, anonymity, global-ban rules, and unit size. When two players are paired, the matcher:

1. Requires **compatible** option sets for both players (no option either player marked `Never`)
2. Chooses settings that **maximize the combined preference score** for both players, with fair tie-breaking when multiple options score equally well

Both players' preferences are weighted equally in the final match configuration.

## Setup

Each bot has its own `requirements.txt` and `.env.example`. Copy `.env.example` to `.env` and fill in your Discord bot token and IDs.

```bash
cd Ladder
pip install -r requirements.txt
cp .env.example .env   # edit with your values
python ladder.py
```

```bash
cd Buildhelper-Pickban
pip install -r requirements.txt
cp .env.example .env
python discordbotwstatsbeta.py
```

## External data

- **Buildhelper** `!MUhelp` images require the full `buildhelp/` tree (~153 MB), not bundled in this repo. See `Buildhelper-Pickban/SOURCE.txt` for the original path.

## Notes

- **Ladder** JSON files in git are **sanitized fixtures** (synthetic user IDs). Real data lives in `Ladder/_live_data/` (gitignored). See [Ladder/DATA.md](Ladder/DATA.md).
- Bots load secrets from `.env` (never commit tokens).
- No videos or Discord server invite links in this repository.
- Provenance: see [GROUPING.md](GROUPING.md).
