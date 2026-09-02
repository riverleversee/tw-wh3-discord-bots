# Ladder Bot

Discord slash-command bot for competitive matchmaking: queue join/leave, Elo and Dahv Elo ratings, match reporting, leaderboards, and player preference settings.

## Bilateral preference optimization

When two players meet in the queue, the bot does not pick match settings arbitrarily. Each player configures preferences (`Preferred`, `Allowed`, or `Never`) across:

- Game mode (Cap Point, Domination, Land Battle)
- Series length (Bo3, Bo1)
- Pick format (matrix 3×3, pick-3-ban-1, blind, pick-1-ban-3, monthly fun)
- Visibility (anonymous vs standard)
- Global-ban rules
- Unit size

These labels are converted to numeric weights and used in `check_match()`:

1. **Compatibility filter** — players only pair when at least one mutually acceptable option exists in every category (neither player has `Never` on the other's only viable choices).
2. **Joint optimization** — for each category, the selected setting maximizes the **combined preference score** for both players (`weight_A + weight_B`, with sign checks so incompatible options are excluded).
3. **Fair tie-breaking** — when multiple settings tie for the best combined score, one is chosen at random.

The result is a match configuration that respects both players' stated preferences as much as the rules allow.

## Requirements

- Python 3.10+
- See `requirements.txt`

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and set your Discord bot token.
3. Run from this directory so JSON state files resolve correctly:

```bash
python ladder.py
```

## Data files

Runtime state lives alongside the script: `elo.json`, `elodahv.json`, `match_record.json`, `parameters.json`, `ongoing.json`, `dodges.json`, `banned_players.json`, plus `Maps/` and `MatchFoundText/`.

JSON in this repo uses **sanitized fixtures** (synthetic user IDs). See [DATA.md](DATA.md).

## Notes

- No Discord server invite or community links in this repo.
- See `SOURCE.txt` for original file locations on disk.
- See `REVIEW_NOTES.md` for intentional deferrals (pass 2).
