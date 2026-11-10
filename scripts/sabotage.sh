#!/usr/bin/env bash
# Plante un vrai bug dans l'application et demande a la suite : tu le vois ?
#
#   ./scripts/sabotage.sh             # module 2 (defaut)
#
# Sort 0 si le bug est DETECTE (la suite devient rouge), 1 sinon.

set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

MODULE="${1:-2}"
TARGET="$(resolve_target "$MODULE")"
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

titre "SABOTAGE -- un bug est plante, la suite le voit-elle ?"
info "cible : $(target_label "$MODULE")"
info ""
info "Bug injecte (SHOP_BUG=1) : le seuil de livraison gratuite passe de"
info "5000 a 500 centimes. Autrement dit, la boutique offre les frais de port"
info "a tout le monde. C'est une regression facturable, pas une subtilite."
echo

SHOP_BUG=1 $PYTEST $TARGET > "$LOG" 2>&1
STATUS=$?

soustitre "Resultat avec le bug actif"
info "$(tail -n 1 "$LOG" | tr -s ' ')"

if [ $STATUS -ne 0 ]; then
  soustitre "Verdict : LE BUG EST DETECTE -- c'est le bon resultat"
  info "Avant, le bug passait. Maintenant, il est detecte."
  info ""
  info "Ces tests-la touchent le vrai calcul de prix. Ils ont une valeur :"
  grep '^FAILED' "$LOG" | head -8 | sed 's/^/      /'
  info ""
  info "Verifie quand meme que la suite est verte SANS le bug :"
  info ""
  info "    $PYTEST $TARGET"
  echo
  exit 0
fi

soustitre "Verdict : LE BUG PASSE INAPERCU"
info "La suite est verte alors que l'application facture faux."
info ""
info "Ce que ca demontre : ces tests ne testent pas l'application. Ils"
info "testent les doubles qu'on a mis a sa place. Le calcul de livraison est"
info "remplace par un mock, donc le mock repond juste -- pendant que le vrai"
info "code se trompe."
info ""
info "C'est l'etat de depart attendu du module 2. Ton objectif : rendre cette"
info "commande ROUGE, en supprimant les doubles qui ne se justifient pas."
info ""
info "Le critere, une derniere fois :"
info ""
info "  Un double se justifie s'il donne acces a un etat ou a un comportement"
info "  que le vrai composant ne peut pas produire a la demande, ou s'il"
info "  permet de verifier une interaction attendue. Sinon, on utilise le vrai."
echo
exit 1
