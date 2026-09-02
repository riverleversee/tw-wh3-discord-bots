# Review notes — Ladder

## Done (sanitize pass)

- Tokens and channel IDs via `.env`
- `DISCORD_OWNER_ID` for `/sync`; admin commands use `DISCORD_APPROVED_IDS`
- Player data sanitized: synthetic IDs in committed JSON; live backup in `_live_data/` (gitignored)
- Dated `elodahv_*.json` snapshots removed from repo (kept in `_live_data/` only)

## Remaining

- Monolith structure unchanged (acceptable for side-project repo)
- Restore production JSON from `_live_data/` when running live bot locally
