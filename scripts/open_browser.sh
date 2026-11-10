#!/usr/bin/env bash
# Ouvre une URL dans le navigateur par defaut, sur Linux, macOS, WSL et Git Bash.
# Utilise par `make serve` pour poser directement le participant sur /docs.
#
#   ./scripts/open_browser.sh http://127.0.0.1:8000/docs
#
# Si aucun ouvreur n'est disponible (serveur sans interface graphique), on sort
# en silence : l'URL est de toute facon affichee par `make serve`.

set -u
URL="${1:-}"
[ -z "$URL" ] && exit 0

for opener in wslview xdg-open open; do
  if command -v "$opener" > /dev/null 2>&1; then
    "$opener" "$URL" > /dev/null 2>&1 && exit 0
  fi
done

# WSL sans wslu, ou Git Bash : on passe par Windows.
if command -v powershell.exe > /dev/null 2>&1; then
  powershell.exe -NoProfile -Command "Start-Process '$URL'" > /dev/null 2>&1 && exit 0
fi

# Dernier recours : le module webbrowser de la stdlib.
if command -v python3 > /dev/null 2>&1; then
  python3 -m webbrowser -t "$URL" > /dev/null 2>&1 && exit 0
fi

exit 0
