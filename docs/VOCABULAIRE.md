# Vocabulaire de l'atelier

Cette page est un **dictionnaire**. Pas besoin de la lire en entier.

---

## Pytest

### Fixture

Une fonction décorée par `@pytest.fixture` **prépare quelque chose** pour un
test : une application, un client, une base. Un test la réclame en la **nommant
dans ses paramètres**. Pytest la retrouve par son nom et l'appelle.

```python
@pytest.fixture  # La fonction est décorée
def client():
    return TestClient(create_app())


def test_an_unknown_cart_is_not_found(client):  # Pytest passe la fixture ici
    assert client.get("/carts/nope").status_code == 404
```

### Scope (portée) d'une fixture

**Combien de temps le résultat est réutilisé** avant d'être refabriqué. Quatre
valeurs : `function` (une par test, c'est le défaut), `class`, `module`,
`session` (une seule pour tout les tests).

Attention, la réutilisation d'un objet ne doit pas lier l'execution des test
entre eux.

```python
@pytest.fixture   # function : une application neuve par test
@pytest.fixture(scope="session")   # session  : LA MÊME pour tout les tests
```

### `autouse=True`

Une fixture qui s'applique à **tous les tests du fichier**, voir à tout les tests
si elle se trouve dans le conftest, de manière **implicite**.

Pratique mais il est facile de l'oublier. Mieux vaut passer ses fixtures
explicitement.

### `conftest.py`

Le fichier où pytest va chercher les fixtures **sans qu'on les importe**. On y
met les fixtures souvent réutilisées.

```python
# conftest.py
@pytest.fixture
def client(app):  # une fixture peut en demander une autre
    with TestClient(app) as test_client:
        yield test_client  # rendu au test, puis refermé après coup


# n'importe quel fichier de test, plus bas dans l'arborescence
def test_an_unknown_cart_is_not_found(client):  # pytest la retrouve tout seul
    assert client.get("/carts/nope").status_code == 404
```

### `monkeypatch`

Une fixture pytest qui **remplace un attribut** (fonction, constante, variable
d'environnement) le temps d'un test. Légitime ailleurs ; ici elle sert surtout
d'anti-exemple, parce que patcher `shop.impl_a.main.PRICING_TABLE` revient à
écrire un test qui connaît l'implémentation.

---

## FastAPI

### Provider

Ce n'est pas vraiment un terme FastAPI, dans ce repo, un **provider** est l'une
des trois fonctions de [`src/shop/deps.py`](../src/shop/deps.py) : `get_clock`, `get_id_generator`,
`get_order_repository`.
FastAPI les appelle à chaque requête pour **fournir** l'objet dont la route a
besoin.

### `dependency_overrides`

Le dictionnaire, porté par **une application donnée** (app), qui permet de
surcharger l'appel d'une fonction par une autre.

```python
app.dependency_overrides[deps.get_clock] = lambda: FixedClock(instant)
#                        └ la clé est la fonction elle-même, pas son nom
#                                          └ la valeur est le callable remplaçant
```

### Modèle Pydantic

Une classe qui décrit **la forme attendue d'un corps JSON**, champ par champ,
avec son type et ses contraintes :

```python
class AddItemBody(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)  # strictement positif
    unit_price_cents: int = Field(ge=0)  # positif ou nul
```

Pydantic est une dépendence de FastAPI qui valide le corps de la requête
**avant** d'entrer dans le code de la route. Si ça ne colle pas, la route n'est jamais appelée et le client reçoit un `422`.

### `TestClient`

Le client de test de FastAPI. **Ce n'est pas un mock**, c'est une manière de
contourner la couche de transport qui traduit `client.post(...)` en appel direct
à l'application. La requête traverse le vrai routage et la vraie validation.

---

## Les mots d'autres domaines

### Port

Dans l'architecture hexagonale, un **port** est une interface définie par le
cœur de l'application pour communiquer avec l'extérieur, par exemple enregistrer
une commande ou lire l'heure. Un **adaptateur** branche une technologie concrète
sur ce port : SQLite, l'horloge système, ou un double de test. Le cœur ne dépend
que du port, jamais de l'adaptateur.

### Contrat

Ce que l'API garantit, et rien de plus [CONTRAT_HTTP.md](CONTRAT_HTTP.md).
Tout ce qui n'y figure pas, la forme d'un identifiant, l'ordre d'une liste, le
contenu d'un message n'est **pas garanti**, donc un test se basant dessus sera
fragile.

### `datetime` naïf / aware

Un `datetime` **aware** porte un fuseau (`tzinfo=`), un `datetime` **naïf** n'en
porte pas.

```python
datetime(2026, 3, 14, 18, 30)  # naïf, à éviter
datetime(2026, 3, 14, 18, 30, tzinfo=PARIS)  # aware, explicite
```

## Les mots propres à ce repo

### Swap

Changer l'implémentation sur laquelle les tests sont lancés. Ce lab se base sur
deux implémentation différentes avec un contrat identique. `make swap` permet
de valider que les test ne sont pas couplés à l'implémentation.

### `:memory:`

Un argument spécifique au lab qui demande à SQLite une base **en mémoire vive**,
détruite à la fermeture.

---

## Les types de doubles de test

### Stub

Un objet qui répond une valeur décidée d'avance.

```python
@dataclass
class StubOrderRepository:
    order_count: int

    def count_for_customer(self, customer_id):
        return self.order_count
```

### Fake

Une vraie implémentation mais simplifiée.
Par exemple une base de donnée in memory.
Il à la partie du comportement qui nous intéresse, pas plus.

### Spy

Il qui enregistre ce qu'on lui a fait.
Il observe les appels, et laisse le vrai composant travailler.

```python
@dataclass
class SpyOrderRepository:
    inner: OrderRepository
    saved: list = field(default_factory=list)

    def save(self, order):
        self.saved.append(order)
        self.inner.save(order)
```

### Mock

Quelque part entre le stub, le fake et le spy.
Il permet de répondre de la manière la plus simple possible aux exigence du
système testé soit en renvoyant une valeur soit en implémentant un comportement.
Il enregistre également les appels qui lui sont fait pour pouvoir les vérifier
par la suite.

```python
class MockOrderRepository:
    def __init__(self, expected_order):
        self.expected_order = expected_order  # l'attente, posée AVANT
        self.calls = 0

    def save(self, order):
        self.calls += 1
        assert order == self.expected_order  # échoue PENDANT l'appel
        assert self.calls == 1, "save appelé plus d'une fois"

    def verify(self):
        assert self.calls == 1, "save n'a jamais été appelé"  # et à la fin
```

Le `MagicMock` de unittest en Python est piègeux. Il accepte **tout**, n'importe
quel attribut, n'importe quel appel. Un `MagicMock` mal configuré ne casse pas,
et peut cacher des erreurs.
