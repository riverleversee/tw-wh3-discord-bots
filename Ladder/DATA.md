# Ladder data files

## Committed (sanitized fixtures)

JSON in this folder uses **synthetic Discord user IDs** (`100000000000000001`, …) for demo and upload. Ratings, match types, and structure are preserved; real player identities are not.

## Local production data (`_live_data/`)

Real community data was backed up to `_live_data/` when sanitizing. That folder is **gitignored**. To run against production data locally:

```bash
cp _live_data/*.json .
```

Restore fixtures before committing:

```bash
python ../scripts/sanitize_ladder_data.py
```

(Requires `_live_data/` backup from a prior sanitization run.)
