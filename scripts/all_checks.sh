#!/usr/bin/env bash
# Le defi final : les trois detecteurs d'un coup, sur tes exercices.
#
#   ./scripts/all_checks.sh          # tous les exercices
#   ./scripts/all_checks.sh 3        # un seul module

set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

MODULE="${1:-}"

titre "ALL-CHECKS -- les quatre detecteurs, d'un coup"
info "cible : $(target_label "$MODULE")"
info ""
info "swap        : tes tests connaissent-ils l'implementation ?"
info "shuffle     : tes tests connaissent-ils leurs voisins ?"
info "check-dates : tes tests connaissent-ils l'heure qu'il est ?"
info "coverage    : tes tests touchent-ils toutes les regles du contrat ?"

RESULTS=()
STATUS=0

run() {
  local label="$1"; shift
  if "$@" > /dev/null 2>&1; then
    RESULTS+=("VERT  $label")
  else
    RESULTS+=("ROUGE $label")
    STATUS=1
  fi
}

run "swap" ./scripts/swap.sh "$MODULE"
run "shuffle" ./scripts/shuffle.sh "$MODULE"
run "check-dates" ./scripts/check_dates.sh "$MODULE"
run "coverage" ./scripts/coverage.sh "$MODULE"

soustitre "Tableau de bord"
for line in "${RESULTS[@]}"; do
  case "$line" in
    VERT*) vert "${line#VERT  }" ;;
    *) rouge "${line#ROUGE }" ;;
  esac
done

if [ $STATUS -eq 0 ]; then
  soustitre "Verdict : TOUT EST VERT"
  info "Ta suite ne depend ni de l'implementation, ni de l'ordre d'execution,"
  info "ni de l'heure a laquelle elle tourne. C'est l'objectif de l'atelier."
  info ""
  info "Derniere etape : relis CHECKLIST.md en pensant a ta propre base de code."
else
  soustitre "Verdict : IL RESTE DU TRAVAIL"
  info "Relance le detecteur rouge tout seul pour avoir le diagnostic detaille :"
  info ""
  info "    make swap        # ou make shuffle, ou make check-dates"
fi
echo
exit $STATUS
