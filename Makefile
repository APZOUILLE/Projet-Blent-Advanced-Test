# Atelier tests Python -- point d'entree unique.
# Sans `make` (Windows sans WSL), utilise ./make.sh avec les memes cibles :
#     ./make.sh swap M=1
SHELL := /bin/bash
.DEFAULT_GOAL := help

# Surchargeables : make test PYTEST="python -m pytest"
PYTEST ?= poetry run pytest
PYTHON ?= poetry run python
export PYTEST
export PYTHON

# M=0|1|2|3 restreint la cible a un module. Sans M : contrat + tous les exercices.
M ?=

# Page ouverte automatiquement par `make serve`.
DOCS_URL ?= http://127.0.0.1:8000/docs

.PHONY: help install doctor serve test test-b swap shuffle check-dates \
        coverage sabotage count-doubles all-checks

help:
	@echo ""
	@echo "  Atelier tests Python -- 3h30, en autonomie"
	@echo "  ========================================="
	@echo ""
	@echo "  Mise en route"
	@echo "    make install           installe les dependances (poetry)"
	@echo "    make doctor            verifie que l'atelier est jouable ici"
	@echo "    make serve             lance l'API et ouvre /docs sur http://127.0.0.1:8000/docs"
	@echo ""
	@echo "  Lancer les tests"
	@echo "    make test              la suite sur l'implementation A"
	@echo "    make test-b            la suite sur l'implementation B"
	@echo "    make swap              A puis B, avec le verdict de couplage"
	@echo ""
	@echo "  Les quatre detecteurs"
	@echo "    make swap              tes tests connaissent-ils l'implementation ?"
	@echo "    make shuffle           ... connaissent-ils leurs voisins ? (5 seeds)"
	@echo "    make check-dates       ... connaissent-ils l'heure ? (4 dates gelees)"
	@echo "    make coverage          ... touchent-ils toutes les regles du contrat ?"
	@echo "    make all-checks        les quatre d'un coup"
	@echo ""
	@echo "  Module 2 -- les doubles"
	@echo "    make sabotage          plante un vrai bug : ta suite le voit-elle ?"
	@echo "    make count-doubles     compte tes mocks et tes surcharges"
	@echo ""
	@echo "  Astuce : M=1 restreint la cible a un module."
	@echo "           make swap M=1     make shuffle M=3     make all-checks M=2"
	@echo ""

install:
	poetry install

doctor:
	@$(PYTHON) scripts/doctor.py

serve:
	@echo ""
	@echo "  API sur http://127.0.0.1:8000  --  documentation : /docs"
	@echo "  Implementation A. Ctrl+C pour arreter."
	@echo ""
	@( sleep 2; ./scripts/open_browser.sh "$(DOCS_URL)" ) &
	@SHOP_IMPL=a poetry run uvicorn shop:create_app --factory --port 8000

test:
	@./scripts/run_tests.sh a "$(M)"

test-b:
	@./scripts/run_tests.sh b "$(M)"

swap:
	@./scripts/swap.sh "$(M)"

shuffle:
	@./scripts/shuffle.sh "$(M)"

check-dates:
	@./scripts/check_dates.sh "$(M)"

coverage:
	@./scripts/coverage.sh "$(M)"

sabotage:
	@./scripts/sabotage.sh "$(if $(M),$(M),2)"

count-doubles:
	@$(PYTHON) scripts/count_doubles.py $(if $(M),exercises/0$(M)_*,exercises)

all-checks:
	@./scripts/all_checks.sh "$(M)"
