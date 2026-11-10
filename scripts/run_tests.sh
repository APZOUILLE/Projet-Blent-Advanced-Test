#!/usr/bin/env bash
# Lance la suite sur une implementation, avec un verdict lisible.
#
#   ./scripts/run_tests.sh a      # implementation A, contrat + exercices
#   ./scripts/run_tests.sh b 1    # implementation B, module 1

set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

IMPL="${1:-a}"
IMPL_UPPER="$(echo "$IMPL" | tr "[:lower:]" "[:upper:]")"
MODULE="${2:-}"
TARGET="$(resolve_target "$MODULE")"
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

titre "TEST -- implementation $IMPL_UPPER"
info "cible : $(target_label "$MODULE")"
echo

SHOP_IMPL="$IMPL" $PYTEST $TARGET 2>&1 | tee "$LOG"
STATUS=${PIPESTATUS[0]}

soustitre "Verdict"
if [ $STATUS -eq 0 ]; then
  vert "suite verte sur l'implementation $IMPL_UPPER"
  info ""
  info "Verte sur une implementation ne veut pas dire decouplee."
  info "La question suivante est : \`make swap\`."
else
  rouge "suite rouge sur l'implementation $IMPL_UPPER"
  info ""
  grep '^FAILED' "$LOG" | head -12 | sed 's/^/      /'
  info ""
  if [ "$IMPL" = "a" ]; then
    info "Un echec sur l'implementation A est un vrai echec : soit ton test se"
    info "trompe, soit il a trouve quelque chose. Relis d'abord le contrat :"
    info "docs/CONTRAT_HTTP.md."
  else
    info "Ces tests passent sur A et cassent sur B : ce n'est pas une"
    info "regression de l'application, c'est du couplage dans les tests."
    info "Lance \`make swap\` pour le diagnostic detaille."
  fi
fi
echo
exit $STATUS
