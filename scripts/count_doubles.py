"""Compte les doubles de test dans un dossier. C'est un miroir, pas une note.

Aucun seuil n'est bon dans l'absolu : deux doubles justifies valent mieux que
zero double et un scenario intestable. Ce script ne juge pas, il rend visible
ce qu'on a tendance a ne plus voir.

Usage :
    python scripts/count_doubles.py [dossier ...]
"""

from __future__ import annotations

import io
import sys
import token
import tokenize
from collections import Counter
from pathlib import Path

MOCK_NAMES = ("MagicMock", "Mock", "AsyncMock", "patch")
PROVIDERS = ("get_clock", "get_id_generator", "get_order_repository")
WIDTH = 74


def significant_names(source: str) -> list[str]:
    """Renvoie les identifiants du source, commentaires et chaines exclus.

    Sans cela, une docstring qui *parle* de `MagicMock` serait comptee comme un
    usage -- et le miroir mentirait.
    """
    names: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (token.STRING, tokenize.COMMENT, tokenize.NL):
                continue
            if tok.type in (token.NAME, token.OP):
                names.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    return names


def scan(paths: list[Path]) -> tuple[Counter, Counter, list[Path]]:
    mocks: Counter = Counter()
    overrides: Counter = Counter()
    files: list[Path] = []
    for root in paths:
        candidates = sorted(root.rglob("*.py")) if root.is_dir() else [root]
        for path in candidates:
            tokens = significant_names(path.read_text(encoding="utf-8"))
            files.append(path)
            for index, name in enumerate(tokens):
                following = tokens[index + 1] if index + 1 < len(tokens) else ""
                # Un mock ne compte que s'il est appele : l'import ne fait rien.
                if name in MOCK_NAMES and following in ("(", "."):
                    mocks[name] += 1
                # Une surcharge, c'est `dependency_overrides[<provider>] = ...`
                if name == "dependency_overrides":
                    window = tokens[index : index + 6]
                    for provider in PROVIDERS:
                        if provider in window:
                            overrides[provider] += 1
    return mocks, overrides, files


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv[1:]] or [Path("exercises")]
    missing = [path for path in paths if not path.exists()]
    if missing:
        print("Chemin introuvable : " + ", ".join(str(p) for p in missing))
        return 2

    mocks, overrides, files = scan(paths)

    print()
    print("=" * WIDTH)
    print("  COUNT-DOUBLES -- combien de doubles y a-t-il dans tes tests ?")
    print("=" * WIDTH)
    print()
    print("  cible : " + ", ".join(str(p) for p in paths))
    print(f"  fichiers analyses : {len(files)}")
    print()
    print("  Mocks et patches (commentaires et chaines exclus)")
    print("  " + "-" * 48)
    for name in MOCK_NAMES:
        print(f"    {name:<16} {mocks[name]:>4}")
    total_mocks = sum(mocks.values())
    print(f"    {'TOTAL':<16} {total_mocks:>4}")
    print()
    print("  Providers surcharges (cles de dependency_overrides)")
    print("  " + "-" * 48)
    for provider in PROVIDERS:
        print(f"    {provider:<24} {overrides[provider]:>4}")
    print()
    print("  Le critere")
    print("  " + "-" * 48)
    print("    Un double se justifie s'il donne acces a un etat ou a un")
    print("    comportement que le vrai composant ne peut pas produire a la")
    print("    demande, ou s'il permet de verifier une interaction attendue.")
    print("    Sinon, on utilise le vrai.")
    print()
    print("  Trois questions a te poser, pas un score a atteindre")
    print("  " + "-" * 48)
    if total_mocks:
        print(f"    * {total_mocks} mock(s) ou patch(es). Pour chacun : quel scenario le")
        print("      vrai composant ne savait-il pas produire ?")
    else:
        print("    * aucun mock, aucun patch : les doubles restants sont des")
        print("      classes lisibles, dont on voit ce qu'elles simulent.")
    if overrides["get_id_generator"]:
        print("    * `get_id_generator` est surcharge. L'identifiant est opaque :")
        print("      transporte-le depuis la reponse plutot que de le predire.")
    else:
        print("    * `get_id_generator` n'est jamais surcharge. Bien.")
    if overrides["get_clock"]:
        print(f"    * `get_clock` surcharge {overrides['get_clock']} fois. Chacune de ces")
        print("      surcharges est-elle dans un test a regle horaire ?")
    print()
    print("  Ce compte n'est pas une note. C'est un miroir.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
