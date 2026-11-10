#!/usr/bin/env bash
# Equivalent du Makefile pour les machines sans `make` (Windows, Git Bash).
# Memes cibles, meme option M :
#
#     ./make.sh help
#     ./make.sh swap M=1
#     ./make.sh test

set -uo pipefail
cd "$(dirname "$0")"

TARGET="${1:-help}"
shift || true

M=""
for arg in "$@"; do
  case "$arg" in
    M=*) M="${arg#M=}" ;;
  esac
done

export PYTEST="${PYTEST:-poetry run pytest}"
export PYTHON="${PYTHON:-poetry run python}"

case "$TARGET" in
  help)
    # On rejoue les `@echo` de la cible help du Makefile : une seule source.
    sed -n '/^help:/,/^install:/p' Makefile \
      | sed -n 's/^\t@echo "\(.*\)"$/\1/p; s/^\t@echo ""$//p'
    echo "  Sans make : ./make.sh <cible> [M=n]   (ex. ./make.sh swap M=1)"
    echo
    ;;
  install)          poetry install ;;
  doctor)           $PYTHON scripts/doctor.py ;;
  serve)
    DOCS_URL="${DOCS_URL:-http://127.0.0.1:8000/docs}"
    echo
    echo "  API sur http://127.0.0.1:8000  --  documentation : /docs"
    echo "  Implementation A. Ctrl+C pour arreter."
    echo
    # Laisse a uvicorn le temps de repondre, puis ouvre /docs dans le navigateur.
    ( sleep 2; ./scripts/open_browser.sh "$DOCS_URL" ) &
    SHOP_IMPL=a poetry run uvicorn shop:create_app --factory --port 8000
    ;;
  test)             ./scripts/run_tests.sh a "$M" ;;
  test-b)           ./scripts/run_tests.sh b "$M" ;;
  swap)             ./scripts/swap.sh "$M" ;;
  shuffle)          ./scripts/shuffle.sh "$M" ;;
  check-dates)      ./scripts/check_dates.sh "$M" ;;
  coverage)         ./scripts/coverage.sh "$M" ;;
  sabotage)         ./scripts/sabotage.sh "${M:-2}" ;;
  count-doubles)
    if [ -n "$M" ]; then $PYTHON scripts/count_doubles.py exercises/0"$M"_*
    else $PYTHON scripts/count_doubles.py exercises; fi ;;
  all-checks)       ./scripts/all_checks.sh "$M" ;;
  *)
    echo "Cible inconnue : $TARGET"
    echo "Lance ./make.sh help pour la liste."
    exit 2
    ;;
esac
