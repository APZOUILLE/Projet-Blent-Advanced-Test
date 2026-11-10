#!/usr/bin/env bash
# Fonctions partagees par les scripts de l'atelier : cadres, verdicts, cibles.
# Aucune couleur ANSI obligatoire : la sortie doit rester lisible dans un
# fichier de log comme dans un terminal.

set -uo pipefail

# Commande pytest. Surchargeable : PYTEST="python -m pytest" ./scripts/swap.sh
PYTEST="${PYTEST:-poetry run pytest}"

# Interpreteur Python. Surchargeable de la meme facon.
PYTHON="${PYTHON:-poetry run python}"

WIDTH=74

rule() { printf '%*s\n' "$WIDTH" '' | tr ' ' "${1:-=}"; }

titre() {
  echo
  rule '='
  printf '  %s\n' "$1"
  rule '='
  echo
}

soustitre() {
  echo
  printf '  %s\n' "$1"
  printf '  %s\n' "$(printf '%*s' "${#1}" '' | tr ' ' '-')"
}

info()  { printf '  %s\n' "$1"; }
vert()  { printf '  [ VERT  ] %s\n' "$1"; }
rouge() { printf '  [ ROUGE ] %s\n' "$1"; }

# resolve_target <module|vide> -> chemin(s) pytest
# 0|1|2|3 -> le module correspondant ; vide -> contrat + tous les exercices.
resolve_target() {
  case "${1:-}" in
    0) echo "exercises/00_testclient" ;;
    1) echo "exercises/01_decoupling" ;;
    2) echo "exercises/02_doubles" ;;
    3) echo "exercises/03_independence" ;;
    "") echo "tests/contract exercises" ;;
    *) echo "$1" ;;
  esac
}

target_label() {
  case "${1:-}" in
    "") echo "tests/contract + tous les exercices" ;;
    *) echo "$(resolve_target "$1")" ;;
  esac
}
