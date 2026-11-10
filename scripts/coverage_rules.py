"""Traduit les lignes non couvertes en regles du contrat non testees.

Un rapport de couverture brut dit « ligne 232 non couverte ». Ca ne se repare
pas : le participant ne lit pas `src/shop/`, et c'est le cadre de l'atelier qui
le lui interdit. Ce script fait la traduction pour lui, en remontant de la ligne
a la fonction qui la contient, puis de la fonction a la regle de
`docs/CONTRAT_HTTP.md` qu'elle implemente.

Usage :
    python scripts/coverage_rules.py <rapport.json>

Le rapport JSON est produit par `pytest --cov --cov-report=json:<fichier>`.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

#: Symbole du code -> (regle du contrat, ce qu'il manque comme test).
#:
#: Les cles sont cherchees de la plus precise a la moins precise :
#: "Classe.methode", puis "Classe", puis "fonction". Les deux implementations
#: nomment les choses differemment ; les deux jeux de noms sont ici, et c'est
#: normal : ce fichier est de l'outillage d'atelier, pas du code applicatif.
RULES: dict[str, tuple[str, str]] = {
    # --- 404 CART_NOT_FOUND ---------------------------------------------
    "_cart_or_404": (
        "404 CART_NOT_FOUND",
        "aucun test ne demande un panier qui n'existe pas",
    ),
    "require": (
        "404 CART_NOT_FOUND",
        "aucun test ne demande un panier qui n'existe pas",
    ),
    # --- 404 ORDER_NOT_FOUND --------------------------------------------
    "read_order": (
        "404 ORDER_NOT_FOUND",
        "aucun test ne demande une commande qui n'existe pas",
    ),
    "CartService.order_view": (
        "404 ORDER_NOT_FOUND",
        "aucun test ne demande une commande qui n'existe pas",
    ),
    "SqliteOrderRepository.get": (
        "404 ORDER_NOT_FOUND",
        "aucun test ne demande une commande qui n'existe pas",
    ),
    # --- 409 CART_ALREADY_EXISTS ----------------------------------------
    "_active_cart_of": (
        "409 CART_ALREADY_EXISTS",
        "aucun test ne demande un second panier pour un client qui en a deja un",
    ),
    "find_for_customer": (
        "409 CART_ALREADY_EXISTS",
        "aucun test ne demande un second panier pour un client qui en a deja un",
    ),
    "create_cart": (
        "409 CART_ALREADY_EXISTS",
        "aucun test ne demande un second panier pour un client qui en a deja un",
    ),
    "CartAlreadyExists": (
        "409 CART_ALREADY_EXISTS (error.cart_id et le header Location)",
        "le refus n'est jamais declenche, donc l'identifiant qu'il rend n'est "
        "jamais verifie",
    ),
    # --- DELETE /carts/{cart_id}/items/{sku} -----------------------------
    "remove_item": (
        "DELETE /carts/{cart_id}/items/{sku}",
        "aucun test ne retire une ligne d'un panier",
    ),
    "Cart.remove": (
        "DELETE /carts/{cart_id}/items/{sku}",
        "aucun test ne retire une ligne d'un panier",
    ),
    "CartService.remove_item": (
        "DELETE /carts/{cart_id}/items/{sku}",
        "aucun test ne retire une ligne d'un panier",
    ),
    # --- suppression du panier au checkout -------------------------------
    "discard": (
        "le checkout reussi supprime le panier",
        "aucun test ne verifie que le panier disparait apres un checkout",
    ),
    # --- 503 PERSISTENCE_UNAVAILABLE -------------------------------------
    "PersistenceUnavailable": (
        "503 PERSISTENCE_UNAVAILABLE",
        "aucun test ne provoque une panne du stockage (palier bonus du module 2)",
    ),
    # --- coupons ----------------------------------------------------------
    "check_coupon_is_applicable": (
        "refus d'un coupon hors conditions (409 COUPON_NOT_APPLICABLE)",
        "au moins un coupon n'est jamais refuse",
    ),
    "set_coupon": (
        "pose et refus d'un coupon",
        "au moins un chemin de `PUT /carts/{cart_id}/coupon` n'est jamais pris",
    ),
    # --- validation de corps ---------------------------------------------
    "handle_invalid_body": (
        "422 sur un corps invalide",
        "aucun test n'envoie un corps que le schema refuse "
        "(quantite negative, champ manquant)",
    ),
}


def _scope_of(tree: ast.AST, line: int) -> str | None:
    """Renvoie le symbole englobant le plus precis pour une ligne donnee."""
    best: str | None = None
    best_size = None
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        if not start <= line <= end:
            continue
        size = end - start
        if best_size is None or size <= best_size:
            best, best_size = node.name, size
    return best


def _qualified_scopes(source: Path, line: int) -> list[str]:
    """Renvoie les cles candidates pour une ligne, de la plus precise a la moins."""
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):  # pragma: no cover - outillage defensif
        return []

    chain: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        if node.lineno <= line <= end:
            chain.append(node.name)

    candidates = []
    if len(chain) >= 2:
        candidates.append(chain[-2] + "." + chain[-1])
    candidates.extend(reversed(chain))
    return candidates


def rules_not_covered(report_path: Path, root: Path) -> tuple[list[str], list[str]]:
    """Renvoie (regles non couvertes, lignes non identifiees)."""
    report = json.loads(report_path.read_text(encoding="utf-8"))

    found: dict[str, str] = {}
    orphans: list[str] = []

    for filename, payload in sorted(report.get("files", {}).items()):
        missing = payload.get("missing_lines") or []
        if not missing:
            continue
        source = root / filename
        for line in missing:
            label = None
            for key in _qualified_scopes(source, line):
                if key in RULES:
                    label = key
                    break
            if label is None:
                orphans.append(f"{filename}:{line}")
            else:
                rule, why = RULES[label]
                found.setdefault(rule, why)

    return [f"{rule} : {why}" for rule, why in found.items()], orphans


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python scripts/coverage_rules.py <rapport.json>")
        return 2

    report_path = Path(argv[1])
    if not report_path.exists():
        print(f"rapport introuvable : {report_path}")
        return 2

    root = Path(__file__).resolve().parent.parent
    rules, orphans = rules_not_covered(report_path, root)

    for rule in rules:
        print(f"    * {rule}")
    for orphan in orphans:
        print(f"    * {orphan} : regle non identifiee, lis le code de cette ligne")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
