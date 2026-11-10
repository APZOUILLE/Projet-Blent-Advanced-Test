#!/usr/bin/env bash
# Le detecteur de couplage : la meme suite, contre les deux implementations.
#
#   ./scripts/swap.sh        # contrat + tous les exercices
#   ./scripts/swap.sh 1      # module 1 seulement

set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh

MODULE="${1:-}"
TARGET="$(resolve_target "$MODULE")"
LOG_A="$(mktemp)"
LOG_B="$(mktemp)"
trap 'rm -f "$LOG_A" "$LOG_B"' EXIT

titre "SWAP -- la meme suite de tests, contre l'autre implementation"
info "cible : $(target_label "$MODULE")"
info ""
info "Les deux implementations repondent au meme contrat HTTP, avec des"
info "architectures internes radicalement differentes. Un test qui passe sur"
info "l'une et casse sur l'autre ne teste pas le contrat : il teste du code."
echo

# --tb=short : pour chaque echec, la ligne du test et l'erreur, sans la pile
# interne du framework. C'est cette sortie qu'on affiche plus bas.
SHOP_IMPL=a $PYTEST $TARGET --tb=short > "$LOG_A" 2>&1
STATUS_A=$?
SHOP_IMPL=b $PYTEST $TARGET --tb=short > "$LOG_B" 2>&1
STATUS_B=$?

# Ce que pytest a dit, tel quel : echecs, erreurs de collecte, erreurs
# d'usage. Deux bruits seulement sont retires : la ligne de progression, et
# la section "warnings summary" (une depreciation interne a starlette, sans
# rapport avec tes tests).
pytest_output() {
  awk '
    /^[.FEsxX]+ +\[ *[0-9]+%\]$/ { next }
    /^=+ warnings summary =+$/ { skip = 1; next }
    skip && /^=+ / { skip = 0 }
    skip { next }
    /^$/ { if (printed) blank = 1; next }
    { if (blank) print ""; blank = 0; printed = 1; print "  " $0 }
  ' "$1"
}

soustitre "Resultats"
if [ $STATUS_A -eq 0 ]; then vert "implementation A  ($(tail -n 1 "$LOG_A" | tr -s ' '))"
else rouge "implementation A  ($(tail -n 1 "$LOG_A" | tr -s ' '))"; fi
if [ $STATUS_B -eq 0 ]; then vert "implementation B  ($(tail -n 1 "$LOG_B" | tr -s ' '))"
else rouge "implementation B  ($(tail -n 1 "$LOG_B" | tr -s ' '))"; fi

if [ $STATUS_A -eq 0 ] && [ $STATUS_B -eq 0 ]; then
  soustitre "Verdict : SWAP VERT"
  info "Ta suite ne sait pas quelle implementation elle pilote -- et c'est"
  info "exactement ce qu'on cherche. On peut reecrire l'application derriere"
  info "les memes routes sans toucher a un seul de tes tests."
  echo
  exit 0
fi

soustitre "Verdict : SWAP ROUGE"
if [ $STATUS_A -ne 0 ]; then
  info "Attention : la suite est deja rouge sur l'implementation A."
  info "Commence par la rendre verte avant de t'occuper du swap."
  soustitre "Erreurs sur A (sortie de pytest)"
  pytest_output "$LOG_A"
fi

if [ $STATUS_B -ne 0 ]; then
  soustitre "Erreurs sur B (sortie de pytest)"
  if [ $STATUS_A -ne 0 ] && [ "$(pytest_output "$LOG_A" | sed -E "s/ in [0-9.]+s//")" = \
       "$(pytest_output "$LOG_B" | sed -E "s/ in [0-9.]+s//")" ]; then
    info "(les memes que sur A, ci-dessus)"
  else
    pytest_output "$LOG_B"
  fi

  soustitre "Types de couplage detectes dans la sortie"
  FOUND=0
  hint() { info "* $1"; FOUND=1; }
  grep -q "object has no attribute 'carts'" "$LOG_B" && \
    hint "acces a l'etat interne de l'application (app.state) -- passe par GET /carts/{id}"
  grep -qE "unexpected keyword argument|missing [0-9]+ required" "$LOG_B" && \
    hint "appel direct d'un handler -- passe par client.post(...)/client.get(...)"
  grep -q "_debug_impl" "$LOG_B" && \
    hint "egalite stricte sur un corps de reponse -- n'affirme que les champs garantis"
  grep -q "no such table" "$LOG_B" && \
    hint "requete SQL directe -- relis la commande par GET /orders/{id}"
  grep -q "KeyError: 'detail'" "$LOG_B" && \
    hint "dependance a la charge utile d'un 422 -- seul le code de statut est garanti"
  grep -q "KeyError: 'carts'" "$LOG_B" && \
    hint "usage d'une route de debug hors contrat -- elle n'existe pas partout"
  grep -qE "assert 'ORD-[^']*' == |assert 1[0-9] == 12" "$LOG_B" && \
    hint "assertion sur le format d'un order_id -- le contrat le declare opaque"
  grep -qE "Cart is empty|Cannot check out" "$LOG_B" && \
    hint "assertion sur la prose d'un message -- affirme error.code, pas error.message"
  grep -qE "assert 'SKU-[^']*' == 'SKU-" "$LOG_B" && \
    hint "dependance a l'ordre des lignes -- indexe-les par sku"
  # Deux motifs qui se lisent mieux dans le source que dans la sortie.
  grep -rqE 'monkeypatch\.(setattr|setitem)\(\s*"shop\.impl_' $TARGET 2>/dev/null && \
    hint "monkeypatch d'une constante interne -- utilise dependency_overrides"
  grep -rqE '^\s*(from|import) shop\.impl_' $TARGET 2>/dev/null && \
    hint "import direct d'une implementation -- passe par shop.create_app()"
  # Un champ que A renvoie et que B ne renvoie pas est hors contrat, par
  # definition : les champs garantis existent dans les deux reponses. On ne
  # retient que les KeyError levees depuis un fichier de test.
  while IFS='|' read -r field where; do
    case "$field" in
      detail|carts) ;;  # deja diagnostiques ci-dessus, plus precisement
      *) hint "lecture du champ '$field' ($where), absent chez B -- hors contrat : voir docs/CONTRAT_HTTP.md, section Vues" ;;
    esac
  done < <(awk -v q="'" '
    / in [A-Za-z_][A-Za-z0-9_]*$/ && $1 ~ /:[0-9]+:$/ {
      w = $1; sub(/:$/, "", w); n = split(w, p, "/"); where = p[n]; next
    }
    $0 ~ ("^E +KeyError: " q) && where ~ /^test_/ {
      f = substr($0, index($0, q) + 1); print substr(f, 1, index(f, q) - 1) "|" where
    }
  ' "$LOG_B" | sort -u)
  [ $FOUND -eq 0 ] && info "(aucun motif connu : lis les echecs ci-dessus)"
fi

soustitre "Ce qu'il faut faire"
info "Pour chaque test rouge : quelle regle metier protege-t-il vraiment ?"
info "Reecris-le pour affirmer cette regle-la, depuis docs/CONTRAT_HTTP.md."
info "Et si tu ne trouves aucune regle metier derriere : supprime-le."
echo
exit 1
