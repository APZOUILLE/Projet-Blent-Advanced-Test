# Tester une API Python sans se mentir

Ce lab est conçu pour se faire en **3h30, en autonomie.** Le repo est
auto-porté, chaque exercice a un critère de réussite vérifiable par une
commande.


## Ce que tu vas apprendre

Trois objectifs, dans cet ordre :

1. **Découpler tes tests de l'implémentation** passer par les interfaces
   publiques, jamais par le code applicatif.
2. **Utiliser des doubles de test minimes et pertinents** savoir quand un
   double se justifie, et surtout **quand le vrai composant suffit**.
3. **Rendre tes tests indépendants** de l'ordre d'exécution, de l'état
   partagé et de l'horloge.

> Un terme du lab n'est pas clair ? → [docs/VOCABULAIRE.md](docs/VOCABULAIRE.md)

---

## Deux applications, un seul contrat

Le domaine métier (panier / commande e-commerce) est implémenté **deux fois**,
avec des architectures internes radicalement différentes mais **exactement le
même contrat d'interface**.

Le but est de vérifier de manière empyrique et automatisée que les tests ne sont
pas couplés à l'implémentation.

Ecris tes tests normalement, c'est l'implémentation A qui est utilisée. À la fin
de chaque module, lances le **swap** :
```bash
make swap
```
La même suite, doit passer sur l'implémentation B.

Les deux implémentations sont différentes mais suivent le même contrat déclaré
dans `tests/contract/`.

---

## Mise en route

Prérequis : **Python 3.12+** et **Poetry**.

```bash
make install
make doctor
```

`make doctor` vérifie tout : versions, dépendances, fuseau `Europe/Paris`,
construction des deux applications, et testes les providers partagés.

Pour lancer l'API et voir le Swagger :

```bash
make serve      # ouvre http://127.0.0.1:8000/docs dans le navigateur
```

### Sur Windows, ou si tu n'as pas `make`

Tous les scripts sont en bash et fonctionnent dans Git Bash ou WSL. Un
équivalent du Makefile est fourni, avec les mêmes cibles :

```bash
./make.sh help
./make.sh swap M=1
```

`make help` (ou `./make.sh help`) liste toutes les commandes.

---

## Cadre de travail

1. **Les implémentations n'ont pas besoin d'être lues.** `src/shop/impl_a/` et
   `src/shop/impl_b/` n'apportent pas d'infomation nécéssaire à la complétion du
   lab. [Le contrat](docs/CONTRAT_HTTP.md) apporte toutes les informations.
   [`src/shop/deps.py`](src/shop/deps.py), [`src/shop/ports.py`](src/shop/ports.py) et [`src/shop/errors.py`](src/shop/errors.py) peuvent être
   lues si besoin.
2. **Les tests passent par les interfaces publiques.** Pas d'import
   d'implémentation, pas d'appel de handler, pas de requête SQL, pas de route
   de debug.
3. **Une application neuve par test.** Aucune variable `app` n'est importable :
   `create_app()` est le seul point d'entrée.

---

## Déroulé

Il y a quatre modules, à faire dans l'ordre. Chaque `ENONCE.md` propose un
palier bonus pour celles et ceux qui finissent tôt, et cache ses indices dans
des blocs dépliables. (Pour profiter de ce mécanisme il faut lire les documents
au format rendu pas la source directement)

### Module 0 : `TestClient` et injection ([Enoncé](exercises/00_testclient/ENONCE.md))

Les bases courtes et guidées.

### Module 1 : Découpler les tests des routes ([Enoncé](exercises/01_decoupling/ENONCE.md))

Tu hérites une suite de tests, elle est couplée à l'implémentation A et ne
marche pas bien sur la B.  
Chaque test y est couplé d'une façon différente : certains se réparent, d'autres
se **jettent**. Et quelques règles du contrat ne sont couvertes par personne.  
**Critère** : `make swap M=1` vert.

### Module 2 : Doubles minimes et pertinents ([Enoncé](exercises/02_doubles/ENONCE.md))

Une suite où tout est mocké, tout passe mais rien n'est testé : `make sabotage`
plante un vrai bug et la suite ne le voit pas. À toi de detecter le bug.  
**Critères** : `make swap M=2` vert, `make sabotage` rouge, et le moins de
doubles de test possible.

### Module 3 : Tests indépendants ([Enoncé](exercises/03_independence/ENONCE.md))

Une suite qui passe test par test et casse en groupe, ou selon la date.  
**Critères** : `make shuffle M=3`, `make check-dates M=3` et `make swap M=3`
verts.

### Clôture

Tu peux confirmer que le lab est fini avec `make all-checks`.
[CHECKLIST.md](CHECKLIST.md) est une page de questions que tu peux utiliser pour
revoir tes tests dans le lab ou ailleurs.

---

## Les quatre détecteurs

Ce sont les quatre commandes à retenir pour l'atelier. Chacune répond à une
question précise, et donne un diagnostic.

| Commande | La question posée |
|---|---|
| `make swap` | tes tests connaissent-ils l'implémentation ? |
| `make shuffle` | tes tests connaissent-ils leurs voisins ? (5 seeds fixées) |
| `make check-dates` | tes tests connaissent-ils l'heure qu'il est ? (4 dates gelées) |
| `make coverage` | tes tests touchent-ils **toutes** les règles du contrat ? |

Un mot sur le dernier, parce qu'il se lit à l'envers des trois autres. La barre
est à **100 %**, et elle n'est pas arbitraire : `tests/contract/` l'atteint en ne
passant que par les routes documentées. Mais la règle ne vaut que dans un sens :

> **Moins de 100 % = une règle du contrat n'est testée par personne.
> 100 % = ne prouve rien.**

Une suite sans la moindre assertion atteint elle aussi 100 % : il suffit
d'appeler les routes. C'est pour ça que `make coverage` vient **en plus** de
`make swap` et de `make sabotage`, jamais à leur place.

Plus deux outils propres au module 2 :

| Commande | Ce qu'elle fait |
|---|---|
| `make sabotage` | plante un vrai bug et demande : ta suite le voit-elle ? |
| `make count-doubles` | compte tes mocks et tes surcharges. Un miroir, pas une note. |

---

## Structure du repo

```
.
├── README.md                  # tu es ici
├── CHECKLIST.md               # « un bon test », à garder ouvert
├── Makefile / make.sh         # point d'entrée unique
├── conftest.py                # option --impl, fixtures app/client
├── docs/
│   ├── VOCABULAIRE.md         # le dictionnaire du lab
│   ├── CONTRAT_HTTP.md        # LE contrat, et ses zones non garanties
│   ├── TESTCLIENT.md          # TestClient & dependency_overrides, 1 page
│   └── QUAND_DOUBLER.md       # le critère de justification, 1 page
├── src/shop/
│   ├── __init__.py            # create_app() + bascule A/B
│   ├── deps.py                # providers PARTAGÉS (clés des surcharges)
│   ├── ports.py               # Clock, IdGenerator, OrderRepository
│   ├── errors.py              # erreurs métier + mapping HTTP partagé
│   ├── impl_a/                # à ne pas ouvrir
│   └── impl_b/                # à ne pas ouvrir
├── tests/contract/            # FOURNI, NE PAS MODIFIER : prouve que A ≡ B
├── exercises/                 # ton travail
└── scripts/                   # les détecteurs (doctor, swap, shuffle, dates…)
```
