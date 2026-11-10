# `TestClient` et `dependency_overrides` (une page, tout est là)

## Construire une application

Il n'existe **aucune variable `app` importable** dans `shop`. La seule façon
d'obtenir une application, c'est la fabrique :

```python
from fastapi.testclient import TestClient
from shop import create_app

client = TestClient(create_app())
```

`create_app()` construit une application neuve : paniers vides, base SQLite
en mémoire vierge, horloge et générateur d'identifiants neufs. C'est
volontaire, et c'est la règle numéro un de l'atelier :

> **Une application neuve par test.**

Une application au niveau du module est de l'état partagé. C'est le sujet
entier du module 3.

L'implémentation construite (A ou B) dépend de la variable d'environnement
`SHOP_IMPL`, positionnée par le `Makefile`. Ton code de test n'a pas à le
savoir : c'est tout l'intérêt.

## Appeler des routes

```python
created = client.post("/carts", json={"customer_id": "alice"})
assert created.status_code == 201
cart_id = created.json()["cart_id"]

client.post(f"/carts/{cart_id}/items",
            json={"sku": "SKU-1", "quantity": 2, "unit_price_cents": 1500})

cart = client.get(f"/carts/{cart_id}").json()
assert cart["subtotal_cents"] == 3000
```

Le client suit l'API de `httpx` : `.status_code`, `.json()`, `.headers`,
`.text`. Les routes sont synchrones, le client est synchrone. Il n'y a ni
`async` ni `await` dans cet atelier.

Un piège à connaître avant le premier test : **un client n'a qu'un panier à la
fois**. Un second `POST /carts` pour le même `customer_id` répond
`409 CART_ALREADY_EXISTS`, et rend l'identifiant du panier existant dans
`error.cart_id`. Si ton test a besoin de deux paniers, il a besoin de deux
`customer_id`.

## `TestClient` n'est pas un double de test

C'est le point le plus mal compris de FastAPI, alors autant l'écrire en gras :

> **`TestClient` est un transport en processus, pas un mock.**

Il ne lance aucun serveur, n'ouvre aucun port, ne fait aucun appel réseau. Il
traduit ton `client.post(...)` en un appel ASGI direct sur l'application, dans
le même processus. La requête traverse le vrai routage, la vraie validation,
les vrais handlers, la vraie base.

Conséquences pratiques :

- **On ne mocke jamais HTTP ici.** Inutile de mocker `httpx`, `requests` ou
  `urllib` : il n'y a aucun appel réseau à intercepter.
- **Ce n'est pas « du test unitaire déguisé ».** C'est un test qui passe par la
  frontière publique de l'application, ce qui est exactement ce qu'on veut.
- **C'est rapide.** Quelques millisecondes par requête. Tu peux te permettre
  une application et une base neuves à chaque test.

## Surcharger une dépendance

Trois dépendances sont injectables, déclarées dans [`src/shop/deps.py`](../src/shop/deps.py) :

| Provider | Fournit | Port |
|---|---|---|
| `deps.get_clock` | l'instant courant | `Clock` |
| `deps.get_id_generator` | les `order_id` | `IdGenerator` |
| `deps.get_order_repository` | la persistance des commandes | `OrderRepository` |

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from shop import create_app, deps

PARIS = ZoneInfo("Europe/Paris")

class FixedClock:
    def __init__(self, instant): self.instant = instant
    def now(self): return self.instant

app = create_app()
app.dependency_overrides[deps.get_clock] = lambda: FixedClock(
    datetime(2026, 3, 14, 18, 30, tzinfo=PARIS)   # un samedi, 18h30
)
client = TestClient(app)
```

Quatre choses à savoir :

1. **La clé est le callable lui-même**, comparé par identité : pas son nom, pas
   une chaîne. C'est pour cette raison que [`shop/deps.py`](../src/shop/deps.py) est **partagé** par
   les deux implémentations : si chacune avait ses propres providers, ta
   surcharge cesserait silencieusement de s'appliquer après le swap.
2. **La valeur est un callable sans argument** qui renvoie le remplaçant. D'où
   le `lambda:`. Si ta classe se construit sans argument, tu peux passer la
   classe elle-même : `overrides[deps.get_order_repository] = MyRepository`.
   L'oubli le plus fréquent est d'écrire `FixedClock(instant)` au lieu de
   `lambda: FixedClock(instant)`. FastAPI tente alors d'analyser l'*instance*
   comme une dépendance, et le message d'erreur ne dit pas du tout ça.
3. **La surcharge appartient à l'application**, pas au processus. Comme
   l'application est neuve à chaque test, il n'y a rien à nettoyer. Si tu
   réutilises une application entre deux tests (ne le fais pas), il faut
   nettoyer, et tu l'oublieras.
4. **Un `datetime` injecté doit être timezone-aware.** Les règles de coupon sont
   évaluées en heure de Paris ; un datetime naïf change la décision métier sans
   rien dire.

## Le vrai dépôt, en mémoire

Pas besoin de doubler la persistance pour la plupart des tests :

```python
from shop import create_order_repository

repository = create_order_repository(":memory:")   # la vraie, sur SQLite
```

Cette fabrique construit le dépôt de l'implémentation sélectionnée. Elle
existe précisément pour que tes tests n'aient pas à importer
`shop.impl_a.repository` : les schémas SQL diffèrent entre A et B, le port non.

## Les erreurs, côté test

```python
response = client.post(f"/carts/{cart_id}/checkout")
assert response.status_code == 409
assert response.json()["error"]["code"] == "EMPTY_CART"   # stable
# jamais : response.json()["error"]["message"]            # prose
```

## Ce qu'il ne faut pas faire

```python
# variable d'application au niveau du module
app = create_app()

# client partagé entre tous les tests
@pytest.fixture(scope="session")
def client(): return TestClient(app)

# monkeypatch d'un attribut interne au lieu d'une surcharge
monkeypatch.setattr("shop.impl_a.main.PRICING_TABLE", {...})

# lecture de l'état interne
cart = app.state.carts[cart_id]

# appel du handler comme une fonction
from shop.impl_a.main import add_item
add_item(request=..., cart_id=..., body=...)

# requête SQL directe
sqlite3.connect(path).execute("SELECT total FROM orders WHERE id = ?", (oid,))
```

Chacune de ces cinq lignes est verte aujourd'hui et morte demain. `make swap`
te le dira en dix secondes.
