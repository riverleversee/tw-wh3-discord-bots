# Public readiness checklist

Verified before changing repo visibility to **public**.

## Secrets

- [x] No `DISCORD_BOT_TOKEN` or bot secrets in tracked files
- [x] No tokens in git history (all commits scanned)
- [x] `.env` gitignored; `.env.example` has empty placeholders only

## Personal / community data

- [x] Ladder JSON uses synthetic Discord user IDs (`100000000000000001`, …)
- [x] Live player data in `Ladder/_live_data/` is gitignored
- [x] No Discord server invite links
- [x] Admin references in docs use generic “server admin” wording

## Make public

```bash
gh repo edit riverleversee/tw-wh3-discord-bots --visibility public
```

To run bots locally: copy `.env.example` → `.env` and add your own Discord bot token (never commit).
