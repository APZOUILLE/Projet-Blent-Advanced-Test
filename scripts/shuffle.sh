#!/usr/bin/env bash
# La suite complete sous 5 seeds d'ordre d'execution, fixees en dur.
#
#   ./scripts/shuffle.sh      # contrat + tous les exercices
#   ./scripts/shuffle.sh 3    # module 3 seulement

set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

# Seeds FIXES : un echec doit etre reproductible a l'identique.
SEEDS=(1 7 42 1337 20260908)

MODULE="${1:-}"
TARGET="$(resolve_target "$MODULE")"

titre "SHUFFLE -- la suite dans 5 ordres d'execution differents"
info "cible : $(target_label "$MODULE")"
info ""
info "pytest-randomly rejoue les memes tests dans un autre ordre. Un test qui"
info "passe dans un ordre et casse dans un autre partage de l'etat avec un"
info "voisin : application, base de donnees, surcharge oubliee, espion, panier."
echo

FAILED_SEEDS=()
for seed in "${SEEDS[@]}"; do
  LOG="$(mktemp)"
  $PYTEST $TARGET -p randomly --randomly-seed="$seed" > "$LOG" 2>&1
  if [ $? -eq 0 ]; then
    vert "seed $seed  ($(tail -n 1 "$LOG" | tr -s ' '))"
  else
    rouge "seed $seed  ($(tail -n 1 "$LOG" | tr -s ' '))"
    FAILED_SEEDS+=("$seed")
    FIRST_FAILURES="$(grep '^FAILED' "$LOG" | head -4 | sed 's/^/      /')"
    [ -n "$FIRST_FAILURES" ] && echo "$FIRST_FAILURES"
  fi
  rm -f "$LOG"
done

if [ ${#FAILED_SEEDS[@]} -eq 0 ]; then
  soustitre "Verdict : SHUFFLE VERT"
  info "Aucun test ne depend de ce qui a tourne avant lui."
  echo
  exit 0
fi

soustitre "Verdict : SHUFFLE ROUGE sur ${#FAILED_SEEDS[@]} seed(s) : ${FAILED_SEEDS[*]}"
info "Tu as un probleme d'ORDRE D'EXECUTION, pas un probleme de logique metier."
info "Le meme test passe seul et casse en groupe : quelque chose survit d'un"
info "test a l'autre."
echo
info "Pour rejouer un ordre precis, et donc reproduire l'echec :"
info ""
info "    $PYTEST $TARGET -p randomly --randomly-seed=${FAILED_SEEDS[0]}"
echo
soustitre "Les cinq suspects, dans l'ordre de frequence"
info "1. une application construite au niveau du module (\`app = create_app()\`)"
info "2. une fixture \`scope=\"session\"\` ou \`scope=\"module\"\` qui porte de l'etat"
info "3. une base de donnees dans un fichier partage au lieu de \`:memory:\`"
info "4. un \`dependency_overrides\` pose et jamais nettoye"
info "5. un objet a etat partage : espion, compteur, panier \`prepare\` pour le voisin"
echo
exit 1
