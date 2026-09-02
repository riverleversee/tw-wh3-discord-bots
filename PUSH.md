# Push to GitHub (private)

Local git is initialized and committed. Run once:

```bash
gh auth login
```

Then from this directory:

```bash
gh repo create tw-wh3-discord-bots --private --source=. --remote=origin --push
```

Or if the repo already exists on GitHub:

```bash
git remote add origin git@github.com:YOUR_USER/tw-wh3-discord-bots.git
git push -u origin main
```
