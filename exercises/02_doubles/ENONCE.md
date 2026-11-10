# Module 2 : Doubles minimes et pertinents (45 min)

> **Un double se justifie s'il donne accès à un état ou à un comportement que
> le vrai composant ne peut pas produire à la demande, ou s'il permet de
> vérifier une interaction attendue. Sinon, on utilise le vrai.**

Ce module apprend à **compter combien ses doubles et à en supprimer**.

**Fichiers de travail** : [`test_checkout_mockfest.py`](test_checkout_mockfest.py) et [`doubles.py`](doubles.py).

Pour plus de détails sur les subtilités entre stub, fake, spy et mock consulte
[le vocabulaire du lab](../../docs/VOCABULAIRE.md).

---

## Démonstration (5 min)

```bash
make test M=2          # vert : 12 tests passent
make sabotage          # un vrai bug est planté... et tout reste vert
```

Le bug (`SHOP_BUG=1`) fait tomber le seuil de livraison gratuite de 5000 à 500
centimes : la boutique offre les frais de port à tout le monde. Une régression
facturable, pas une subtilité.

Douze tests verts. Zéro détection.

La raison est dans le fichier : les trois providers sont remplacés par des
`MagicMock` dans chaque test, et deux `patch` neutralisent les fonctions de
calcul de prix. Il ne reste plus rien de réel sous les routes. **La suite décrit
ses propres mocks.**

Ton objectif pour ce module : rendre `make sabotage` **rouge**.

---

## Étape 1 : Instruire les dépendances (10 min)

Sur papier ou en commentaires, **avant d'écrire une ligne de code**. Pour
chaque dépendance : *le vrai composant peut-il produire le scénario dont j'ai
besoin ?*

| Dépendance | Verdict | Pourquoi |
|---|---|---|
| `Clock` | | |
| `IdGenerator` | | |
| `OrderRepository` | | |

<details><summary>Correction : à ouvrir seulement après avoir rempli le tableau</summary>

| Dépendance | Verdict | Pourquoi |
|---|---|---|
| `Clock` | **Double indispensable, mais pas partout** | On ne peut pas attendre samedi 18h30 pour tester `WEEKEND` ou `HAPPYHOUR` : le double est la seule voie d'accès au scénario. En revanche, dans les tests de `QUANTITY_LIMIT_EXCEEDED` ou de gratuité de livraison, aucune règle temporelle n'intervient : le doubler n'apporte rien et ajoute du bruit. **Même dépendance, verdict opposé selon le scénario.** |
| `IdGenerator` | **Aucun double** | Le vrai fait l'affaire. L'identifiant n'est jamais une valeur attendue : il sort du corps de la réponse au checkout et on le réinjecte dans `GET /orders/{id}`. Et le contrat le déclare opaque : l'assertion dessus a déjà été supprimée au module 1. |
| `OrderRepository` | **Le vrai, plus un espion sur un seul test** | L'état « client ayant déjà commandé » se construit très bien avec la vraie base en `:memory:` et un `POST /checkout`. En revanche, *la persistance a bien eu lieu* est une **interaction attendue** : c'est le seul endroit de l'atelier où un espion est justifié. |

</details>

---

## Étape 2 : Le générateur d'ID est un appât, retire-le (5 min)

Dans la mockfest, `get_id_generator` est surchargé et **deux tests affirment la
valeur produite** (`test_checkout_returns_the_generated_order_id` et
`test_an_order_can_be_read_back`).

Fais ces trois gestes, dans cet ordre :

1. supprime la surcharge de `get_id_generator` ;
2. supprime les deux assertions sur `"ORD-deadbeef"` ;
3. reformule les deux tests pour qu'ils **transportent** l'identifiant au lieu
   de le prédire.

Apprendre à *retirer* un double, pas seulement à le remplacer. C'est le geste
que ce module doit graver.

<details><summary>Indice : transporter plutôt que prédire</summary>

```python
checkout = client.post(f"/carts/{cart_id}/checkout")
order_id = checkout.json()["order_id"]          # on le reçoit
read_back = client.get(f"/orders/{order_id}")   # on le réinjecte
assert read_back.status_code == 200
assert read_back.json()["total_cents"] == checkout.json()["total_cents"]
```

Ce test est plus fort que celui qu'il remplace : il vérifie que l'identifiant
renvoyé est *utilisable*, ce qui est la seule chose que le contrat en dit.

</details>

---

## Étape 3 : Réécrire la suite avec le minimum (20 min)

Deux artefacts seulement à implémenter dans [`doubles.py`](doubles.py) (squelettes fournis,
avec docstrings) :

- **`FixedClock(instant)`** : renvoie toujours le même instant, timezone-aware.
- **`SpyOrderRepository(inner)`** : **enveloppe** un vrai dépôt, enregistre les
  appels à `save`, et **délègue tout le reste**.

Tout le reste passe par la vraie `create_order_repository(":memory:")` et le
vrai générateur d'identifiants.

Et surtout : **une application neuve et une base neuve par test.** Sinon le
module 3 va faire mal.

Écris aussi **le test qui manquait** : `WELCOME10` refusé quand le client a
déjà une commande, en **passant une vraie commande via l'API**, pas en stubant
une valeur de retour. C'est une ligne de plus à écrire, et infiniment plus
fiable : ça teste aussi que le comptage marche.

<details><summary>Indice : l'espion par délégation</summary>

```python
def save(self, order):
    self.saved.append(order)   # on observe
    self.inner.save(order)     # et on laisse faire

def get(self, order_id):
    return self.inner.get(order_id)   # délégation pure
```

On observe sans rien simuler : le comportement réel est préservé, donc le test
reste sensible aux vrais bugs.

</details>

<details><summary>Indice : construire l'état « client ayant déjà commandé »</summary>

```python
first_cart = _cart_with(client, ("SKU-1", 1, 3000))
assert client.post(f"/carts/{first_cart}/checkout").status_code == 201

second_cart = _cart_with(client, ("SKU-1", 1, 10000))
response = client.put(f"/carts/{second_cart}/coupon", json={"code": "WELCOME10"})
assert response.status_code == 409
```

</details>

---

## Étape 4 : La seule assertion d'interaction de tout l'atelier (5 min)

Avec `SpyOrderRepository`, vérifie qu'un checkout réussi **persiste la commande
exactement une fois**, avec un objet dont l'identifiant correspond à celui du
corps de la réponse.

**Query / command** : on vérifie l'**état** pour les requêtes, l'**interaction**
pour les commandes, et jamais l'inverse.

Pourquoi l'état ne suffit pas ici : un `GET /orders/{id}` qui répond `200`
prouve que la commande est *lisible*, pas qu'elle est passée par le chemin de
persistance attendu. La nuance devient critique le jour où la lecture a un
cache.

> ### Encadré propre au REST
>
> Passer par HTTP ne dispense pas de doubles, mais en réduit le nombre. Le
> contrat HTTP est **déjà une frontière**. Mocker ce qui est derrière, c'est
> poser une frontière derrière une frontière : on décrit deux fois la même
> chose, et on vérifie la seconde description au lieu du code.

---

## Paliers bonus : deux exceptions qui valident le critère

Deux cas où le vrai composant est réellement incapable de produire le
scénario. Les squelettes sont dans [`doubles.py`](doubles.py).

1. **`StubOrderRepository(order_count=300)`** : tester le refus de `WELCOME10`
   pour un gros client, sans passer 300 checkouts.
2. **`FailingOrderRepository`** : `save` lève
   `shop.errors.PersistenceUnavailable`. Tester le `503
   PERSISTENCE_UNAVAILABLE`, impossible à provoquer avec la vraie base.
   Affirme le **code de statut** et le **`code`** documentés, pas la prose du
   message, ni un `500` non spécifié. Vérifie aussi qu'**aucune commande n'a
   été créée**.

---

## Critères de réussite

```bash
make swap M=2          # vert sur A et sur B
make sabotage          # ROUGE : le bug est maintenant détecté
make count-doubles M=2 # le miroir
```

Et un compte de doubles vérifiable. Ta suite corrigée doit contenir :

- **aucun `MagicMock`, aucun `patch`** ;
- **au plus deux providers surchargés** : `get_clock` sur les seuls tests à
  règle temporelle, `get_order_repository` dans le test d'interaction et les
  bonus ;
- **`get_id_generator` jamais surchargé**.

L'inversion à obtenir, en une phrase : *avant, le bug passait ; maintenant, il
est détecté.*
