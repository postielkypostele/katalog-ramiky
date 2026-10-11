#!/bin/bash
# Denne spustenie: stiahne feed z e-shopu, nakresli ramiky a nahra ich na GitHub.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO="$HOME/katalog-ramiky"
LOG="$HOME/Library/Logs/katalog-ramiky.log"
exec >>"$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') start"
cd "$REPO" || { echo "chyba: nenajdeny $REPO"; exit 1; }
git pull --rebase --quiet || echo "upozornenie: git pull zlyhal"
python3 generate.py || { echo "chyba: generate.py zlyhal"; exit 1; }
git add -A site config.json
if git diff --cached --quiet; then
  echo "bez zmien"
else
  git commit --quiet -m "Ramiky $(date '+%Y-%m-%d')" && git push --quiet && echo "nahrane na GitHub"
fi
echo "=== koniec"
