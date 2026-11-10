#!/usr/bin/env bash
# Le quatrieme detecteur : tes tests touchent-ils toutes les regles du contrat ?
#
#   ./scripts/coverage.sh          # contrat + tous les exercices
#   ./scripts/coverage.sh 1        # module 1 seulement (informatif)

set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

MODULE="${1:-}"
# Difference volontaire avec les autres detecteurs : sans argument, on mesure
# `exercises` SEUL, jamais `tests/contract`. Les tests de contrat atteignent
# 100 % a eux tout seuls ; les inclure noierait la couverture du participant
# dans la leur et la commande repondrait toujours vert.
if [ -z "$MODULE" ]; then
  TARGET="exercises"
  LABEL="exercises (tes tests seuls -- tests/contract est exclu de la mesure)"
else
  TARGET="$(resolve_target "$MODULE")"
  LABEL="$(target_label "$MODULE")"
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

titre "COVERAGE -- quelles regles du contrat tes tests n'atteignent jamais ?"
info "cible : $LABEL"
info ""
info "La surface mesuree est l'implementation pilotee, plus les providers, les"
info "erreurs et la tarification. En sont exclus la route de debug -- que le"
info "cadre t'interdit d'appeler -- et quelques gardes inatteignables par HTTP."
info ""
info "La barre est a 100 %, et elle n'est pas arbitraire : tests/contract/"
info "l'atteint en ne passant que par les routes documentees."
echo

STATUS=0
SUITE_RED=0
MEASURED=""

for impl in a b; do
  LOG="$TMP/pytest-$impl.log"
  JSON="$TMP/coverage-$impl.json"
  SHOP_IMPL="$impl" $PYTEST $TARGET \
    --cov --cov-report= "--cov-report=json:$JSON" > "$LOG" 2>&1
  RUN_STATUS=$?

  if [ ! -f "$JSON" ]; then
    rouge "implementation ${impl}  (la suite n'a pas pu etre mesuree)"
    tail -n 12 "$LOG" | sed 's/^/      /'
    STATUS=1
    continue
  fi

  PERCENT=$($PYTHON -c "import json,sys; d=json.load(open(sys.argv[1])); print(f\"{d['totals']['percent_covered']:.2f}\")" "$JSON")
  MEASURED="$MEASURED $impl:$PERCENT"

  if [ "$RUN_STATUS" -ne 0 ]; then
    rouge "implementation ${impl}  la suite ne passe pas -- mesure sans valeur"
    grep '^FAILED' "$LOG" | head -5 | sed 's/^/      /'
    STATUS=1
    SUITE_RED=1
  elif [ "$PERCENT" = "100.00" ]; then
    vert "implementation ${impl}  ${PERCENT} %"
  else
    rouge "implementation ${impl}  ${PERCENT} %"
    STATUS=1
  fi

  # On ne nomme les regles manquantes que si la suite est verte : sur une suite
  # rouge, les lignes non atteintes sont celles des tests qui ont casse, pas
  # celles des regles oubliees. Lister les deux ensemble induirait en erreur.
  if [ "$RUN_STATUS" -eq 0 ] && [ "$PERCENT" != "100.00" ]; then
    info ""
    info "  Regles du contrat qu'aucun de tes tests n'atteint :"
    $PYTHON scripts/coverage_rules.py "$JSON"
    info ""
  fi
done

if [ $STATUS -eq 0 ]; then
  soustitre "Verdict : COVERAGE VERT"
  info "Chaque regle du contrat est touchee par au moins un de tes tests, sur"
  info "les deux implementations."
  info ""
  info "Attention a ce que ce vert ne dit PAS. Une suite de tests SANS AUCUNE"
  info "assertion atteint elle aussi 100 % : il suffit d'appeler les routes."
  info ""
  info "  Moins de 100 %  =  une regle n'est testee par personne."
  info "  100 %           =  ne prouve rien tout seul."
  info ""
  info "C'est pour ca que cette commande vient en plus de \`make swap\` et de"
  info "\`make sabotage\`, jamais a leur place."
  echo
  exit 0
fi

if [ $SUITE_RED -eq 1 ]; then
  soustitre "Verdict : MESURE IMPOSSIBLE"
  info "La couverture ne se lit que sur une suite verte : une suite qui casse"
  info "n'execute pas le code qu'elle aurait du executer, et le pourcentage ne"
  info "veut plus rien dire."
  info ""
  info "Rends d'abord la suite verte sur les deux implementations -- c'est le"
  info "travail de \`make swap\` -- puis reviens ici."
  echo
  exit 1
fi

soustitre "Verdict : COVERAGE ROUGE --${MEASURED}"
info "Une ligne jamais executee, c'est une regle du contrat que personne ne"
info "verifie. Pas un detail de style : un pan du contrat sans filet."
info ""
info "Pour chaque regle listee ci-dessus, la question est la meme :"
info "  \"si je cassais cette regle dans l'application, un seul de mes tests"
info "   tomberait-il ?\""
info "Si la reponse est non, ecris le test qui manque."
info ""
info "Relis docs/CONTRAT_HTTP.md : tout ce qu'il garantit merite un test."
echo
exit 1
