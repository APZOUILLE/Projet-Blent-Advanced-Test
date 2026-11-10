# Module 3 : Tests indépendants (50 min)

**Fichier de travail** : [`test_orders_flaky.py`](test_orders_flaky.py), quatorze tests qui passent
tous… tant qu'on ne les dérange pas.

Chaque test passe **seul**. La suite passe **dans l'ordre du fichier**, **un
mardi après-midi**. C'est exactement le profil du test qui casse en CI un
dimanche à minuit, et que personne n'arrive à reproduire le lundi.

---

## Le décor (5 min)

```bash
make test M=3           # Au moins un test rate
make shuffle M=3        # rouge sur les 5 seeds
make check-dates M=3    # rouge sur les 4 dates
```

> **Commence par regarder le test rouge.** Ce n'est pas une panne, et personne
> n'a touché à l'application.
>
> Ce test passait. Son auteur l'a écrit un jour de 2025, il était vert, il a
> été mergé, la CI était verte. Puis le 1er janvier est arrivé, et il est
> devenu rouge tout seul sans que le comportement de la boutique change.
>
> Les deux autres tests temporels ne sont pas encore rouges, mais ils sont du
> même bois : ils attendent seulement la bonne heure. Tu peux les faire tomber
> à la demande :
>
> ```bash
> SHOP_FREEZE_AT='2026-12-09 19:00:00+01:00' make test M=3   # un mercredi 19h00
> ```

Deux familles de bugs, mélangées comme dans la vraie vie :

**État partagé et ordre d'exécution**. Les trois premiers sont les bugs de
test FastAPI les plus fréquents en production :

1. `app = create_app()` au niveau du **module**, et un `client` en fixture
   `scope="session"` : l'état des paniers et la base survivent d'un test à
   l'autre.
2. Un `dependency_overrides` posé dans un test et **jamais nettoyé** : il fuit
   sur tous les tests suivants, qui deviennent verts **pour la mauvaise
   raison**.
3. Le dépôt SQLite sur un **fichier temporaire partagé** :
   `GET /customers/{id}/orders` renvoie un compte différent selon ce qui a
   tourné avant.
4. Un `customer_id` en dur, partagé par tous les tests. L'un d'eux dépend de
   `WELCOME10`, donc du fait qu'aucune commande n'existe encore pour ce client.
   Pire : la fonction d'aide `_cart_with` **reprend le panier en cours** quand
   `POST /carts` répond `409 CART_ALREADY_EXISTS`. Les lignes et le coupon d'un
   test se transmettent donc silencieusement au suivant.
5. Un `SpyOrderRepository` **partagé au niveau du module** : le compteur
   accumule les appels des tests précédents, et l'assertion `== 1` casse selon
   l'ordre. Un espion est un objet à état, donc lui aussi doit être neuf à
   chaque test.
6. Un test qui « prépare » le panier du suivant, avec un commentaire innocent.

**Fragilité temporelle**

7. `assert placed_at.date() == date.today()` : casse à minuit.
8. Un test de `HAPPYHOUR` dont l'attente dépend de l'heure réelle.
9. Un test de `WEEKEND` dont l'attente dépend du jour réel.
10. Un test de `NEWYEAR` qui compare à `date.today().year` **celui-là a déjà
    pourri**.
11. Un test qui recalcule la valeur attendue avec `datetime.now()` dans son
    propre corps.

---

## Étape 1 : Reprendre le contrôle de l'état (25 min)

L'objectif : **une application neuve par test**.

- `create_app()` dans une fixture **`function`-scoped**, plus aucune variable
  d'application au niveau du module ;
- base **`:memory:`** par test, qui supprime le fichier temporaire partagé ;
- **surcharges portées par la fixture qui les pose**, donc défaites avec elle ;
- **espion neuf** par test ;
- **identifiant client unique** par test ;
- **aucun test qui prépare le panier d'un autre**.

<details><summary>Indice : la fixture qui règle 80 % du fichier</summary>

```python
@pytest.fixture
def app():
    application = create_app()
    yield application
    application.dependency_overrides.clear()

@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
```

Comme l'application est jetée après chaque test, le `clear()` est une ceinture
en plus des bretelles. Mais il documente l'intention, et il te sauve le jour où
quelqu'un remet un `scope=` quelque part.

</details>

<details><summary>Indice : l'identifiant client unique</summary>

```python
@pytest.fixture
def customer(request):
    return "customer-" + request.node.name
```

Deux tests ne peuvent plus se marcher dessus, et le nom qui apparaît dans les
logs dit de quel test vient la commande.

Effet de bord : chaque test ouvre son propre panier, donc la branche « on
reprend le panier en cours » de `_cart_with` devient morte. Supprime-la : un
`POST /carts` doit répondre `201`, et un `409` doit être un échec de test, pas
un cas à rattraper.

</details>

<details><summary>Indice : le test qui en préparait un autre</summary>

Ne cherche pas à « passer le panier » proprement d'un test à l'autre. Fais
l'inverse : chaque test construit **son** panier, de bout en bout. Trois lignes
dupliquées valent mieux qu'un couplage invisible, et une fonction d'aide
locale supprime la duplication sans réintroduire le couplage.

</details>

---

## Étape 2 : Reprendre le contrôle de l'horloge (15 min)

- **aucun `datetime.now()` ni `date.today()`** dans un test ;
- l'horloge est **injectée**, avec une **date de référence explicite** ;
- **une date de référence par intention**, pas une date unique pour tout le
  fichier : un samedi 18h30 de décembre pour tester une validité, un mardi
  10h00 de janvier pour tester un refus.

Une date par intention, c'est aussi de la documentation : quand un test
s'appelle `test_weekend_is_accepted_on_a_saturday` et qu'on lit
`SATURDAY_DECEMBER_1830` dans son corps, il n'y a plus rien à deviner.

<details><summary>Indice : geler l'horloge d'une application</summary>

```python
def _freeze(app, instant):
    app.dependency_overrides[deps.get_clock] = lambda: FixedClock(instant)
```

Et dans le test :

```python
def test_weekend_is_accepted_on_a_saturday(app, client, customer):
    _freeze(app, SATURDAY_DECEMBER_1830)
    ...
```

</details>

<details><summary>Indice : le test qui affirmait « la commande est d'aujourd'hui »</summary>

Son intention réelle était : « `placed_at` vient bien de l'horloge de
l'application ». Une fois l'horloge injectée, l'assertion devient exacte au lieu
d'être approximative :

```python
assert datetime.fromisoformat(order["placed_at"]) == SATURDAY_DECEMBER_1830
```

Plus de `date.today()`, plus de minuit, plus de fuseau à deviner.

</details>

---

## Un mot sur `freezegun` (5 min)

`make check-dates` gèle l'horloge globale du processus avec `freezegun`. C'est
un outil de **diagnostic** ici, pas la solution.

> **`freezegun` est l'outil du code qu'on ne peut pas changer.
> L'injection est l'outil du code qu'on écrit.**

Geler l'horloge globale masque le vrai problème (une dépendance non injectée)
et ne survit pas au refactoring.

---

## Palier bonus : si tu as fini avant les autres

Ajoute un test qui prouve que **deux instants différents** cohabitent dans le
même test : `WEEKEND` accepté un samedi, refusé un mardi, dans une seule
fonction. C'est précisément ce que `@freeze_time` ne sait pas faire proprement,
et ça se lit en cinq lignes avec deux applications.

---

## Critères de réussite

```bash
make shuffle M=3      # vert sur les 5 seeds
make check-dates M=3  # vert sur les 4 dates
make swap M=3         # vert sur A et sur B
```

Les trois d'un coup :

```bash
make all-checks M=3
```
