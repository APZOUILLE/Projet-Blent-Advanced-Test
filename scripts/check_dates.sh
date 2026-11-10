#!/usr/bin/env bash
# La suite complete sous 4 dates gelees, choisies pour leurs pieges.
#
#   ./scripts/check_dates.sh      # contrat + tous les exercices
#   ./scripts/check_dates.sh 3    # module 3 seulement

set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

# Quatre instants FIXES, en heure de Paris. Chacun casse une classe de test.
DATES=(
  "2027-01-01 00:05:00+01:00|1er janvier, 00h05 -- changement d'annee ET de date UTC"
  "2026-12-31 23:59:00+01:00|31 decembre, 23h59 -- dernier instant de l'annee"
  "2026-12-05 19:00:00+01:00|samedi 19h00 -- week-end ET happy hour"
  "2027-01-12 10:00:00+01:00|mardi 10h00 -- ni week-end, ni happy hour"
)

MODULE="${1:-}"
TARGET="$(resolve_target "$MODULE")"

titre "CHECK-DATES -- la suite sous 4 dates gelees"
info "cible : $(target_label "$MODULE")"
info ""
info "L'horloge du processus est gelee avec freezegun, pour simuler le jour ou"
info "la nuit ou ta CI tournera vraiment. Un test qui ne passe qu'un mardi"
info "apres-midi n'est pas un test : c'est un rendez-vous."
echo

FAILED=()
for entry in "${DATES[@]}"; do
  instant="${entry%%|*}"
  label="${entry#*|}"
  LOG="$(mktemp)"
  SHOP_FREEZE_AT="$instant" $PYTEST $TARGET > "$LOG" 2>&1
  if [ $? -eq 0 ]; then
    vert "$label"
  else
    rouge "$label"
    FAILED+=("$instant")
    grep '^FAILED' "$LOG" | head -4 | sed 's/^/      /'
  fi
  rm -f "$LOG"
done

if [ ${#FAILED[@]} -eq 0 ]; then
  soustitre "Verdict : CHECK-DATES VERT"
  info "Aucun test ne depend de l'instant ou tu le lances."
  echo
  exit 0
fi

soustitre "Verdict : CHECK-DATES ROUGE sur ${#FAILED[@]} date(s) sur 4"
info "Tu as un probleme d'HORLOGE, pas un probleme de logique metier."
echo
info "Pour rejouer une date precise :"
info ""
info "    SHOP_FREEZE_AT=\"${FAILED[0]}\" $PYTEST $TARGET"
echo
soustitre "Ce qu'il faut faire"
info "* aucun \`datetime.now()\` ni \`date.today()\` dans un test ;"
info "* injecte l'horloge : \`app.dependency_overrides[deps.get_clock]\` ;"
info "* choisis une date de reference PAR INTENTION, pas une pour tout le"
info "  fichier : un samedi 18h30 pour tester une validite, un mardi 10h00"
info "  pour tester un refus ;"
info "* et n'affirme jamais une valeur que tu recalcules avec l'heure reelle."
echo
info "Note : ce script gele l'horloge globale pour te MONTRER le probleme."
info "Ce n'est pas la solution."
echo
exit 1
