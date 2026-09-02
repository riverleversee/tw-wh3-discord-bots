# Discord Bots — Grouping Summary

Staged from a local `DiscordBo` archive on 2026-09-01. Originals remain on the source machine.

## Bot types identified

| Folder | Bot type | Chosen latest | Dest size |
|--------|----------|---------------|-----------|
| `Buildhelper-Pickban/` | Warhammer land-battle MU help + pick/ban | `discordbotwstatsbeta.py` (121,598 B, Apr 2024) | ~7.8 MB |
| `Ladder/` | Competitive ladder: queue, Elo, slash commands | `ladder.py` (52,666 B, May 2024) | ~320 KB |
| `LibManager/` | YouTube VOD scrape, OCR, ML build library | `LibManagerBot.py` (34,714 B, Oct 2024) | ~2.0 MB |

## Version selection method

1. Collected all candidate `.py` files across source trees, backups, and deployment forks.
2. Compared byte size and content; preferred larger files when later-dated copies were smaller.
3. Logged winners and rejections in each bot's archived `_history/` (local only).

## What was copied

### Buildhelper-Pickban
- Latest script + MU CSVs + documentation/ + factionstats/
- 8 sample buildhelp images (8 faction pairs) with one buildtext.txt example

### Ladder
- Full `ladder/` tree: script, JSON state, Maps/, MatchFoundText/

### LibManager
- Latest `LibManagerBot.py` + helper/training scripts
- 8 sample StoreBuilds screenshots
- No videos in repo

## What was left behind (bulk data)

| Location | Reason |
|----------|--------|
| `buildhelp/` (~153 MB) | Bulk matchup media; samples only in repo |
| `MachineLearningBuilds/` (~11 GB) | Training images + .pth models |
| Deployment forks (MLsenddust, sendsipa) | Local recovery only |

## Security note

Bots use `.env` for tokens and IDs. Ladder JSON in git is sanitized; live data is gitignored.
