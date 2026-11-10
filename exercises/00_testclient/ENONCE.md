# Module 0 : `TestClient` et injection (25 min, non sautable)

C'est le prix d'entrée. Sans ces deux notions, aucun des trois modules
suivants n'est faisable. Si tu testes déjà des API FastAPI au quotidien, lis
[docs/TESTCLIENT.md](../../docs/TESTCLIENT.md) (une page) et passe directement
à l'étape 2.

**Fichier de travail** : [`test_first_steps.py`](test_first_steps.py)

---

## Étape 1 : Voir l'API (8 min)

```bash
make serve
```

Dans un autre terminal (tout ça peut aussi se faire depuis le Swagger) :

```bash
curl -s -X POST http://127.0.0.1:8000/carts -H 'content-type: application/json' -d '{"customer_id":"alice"}'
```

Relance exactement la même commande. Tu obtiens un `409` : un client n'a qu'un
panier à la fois. L'identifiant de ton panier est quand même renvoyé dans le
body pour que le client ne soit pas bloqué.

Récupère le `cart_id` renvoyé, puis :

```bash
curl -s -X POST http://127.0.0.1:8000/carts/COLLE_LE_CART_ID_ICI/items -H 'content-type: application/json' -d '{"sku":"SKU-1","quantity":2,"unit_price_cents":1500}' -i
```

```bash
curl -s http://127.0.0.1:8000/carts/COLLE_LE_CART_ID_ICI
```

Je t'encourage à faire tout les tests qui te paraissent pertinnent pour bien
comprendre les règles de l'API avant de commencer à la tester. Puis tu peux 
arrêter le serveur (`Ctrl+C`).

---

## Étape 2 : Un premier test par les routes (7 min)

```bash
make test M=0
```

Trois tests passent, deux sont marqués `skip` : ce sont ceux que tu dois
implémenter.

Lis [`test_a_new_cart_is_empty`](test_first_steps.py#L37), c'est le modèle. Puis
écris les deux tests marqués `TODO` en retirant leur décorateur
`@pytest.mark.skip` pour qu'il soient executés :

1. `test_adding_an_item_shows_up_in_the_cart` : ajoute 2 unités à 1500
   centimes, vérifie le sous-total par `GET /carts/{cart_id}`.
2. `test_checking_out_an_empty_cart_is_refused` : vérifie le `409` et le
   `code` d'erreur.

<details><summary>Indice : quel champ affirmer sur l'erreur ?</summary>

Le corps d'une erreur métier est
`{"error": {"code": "...", "message": "..."}}`. `code` est **stable**,
`message` est de la prose qui change d'une implémentation à l'autre. Affirme
`response.json()["error"]["code"] == "EMPTY_CART"`.

</details>

<details><summary>Indice : comment récupérer le cart_id ?</summary>

```python
cart_id = client.post("/carts", json={"customer_id": "alice"}).json()["cart_id"]
```

</details>

---

## Étape 3 : Surcharger l'horloge (7 min)

Lis `test_the_clock_can_be_replaced_for_one_application` puis
`test_the_frozen_clock_also_drives_the_business_rules`. Ces deux tests sont
fournis, complets. Ne les modifie pas : comprends-les.

Ce qu'il faut en retenir :

- la **clé** de `dependency_overrides` est le provider lui-même
(`deps.get_clock`), comparé par identité.
- la **valeur** est un callable sans argument qui renvoie le remplaçant ;
- l'`instant` injecté doit être **timezone-aware** ;
- **une application neuve par test**, donc rien à nettoyer.

Vérifie que tout passe :

```bash
make test M=0
```

---

## Étape 4 : L'encadré à ne pas sauter (3 min)

> ### `TestClient` n'est pas un double de test
>
> C'est un **transport en processus**. Il ne lance aucun serveur, n'ouvre aucun
> port, ne fait aucun appel réseau : il traduit `client.post(...)` en un appel
> ASGI direct sur l'application. La requête traverse le vrai routage, la vraie
> validation, les vrais handlers, la vraie base.
>
> **On ne mocke donc jamais HTTP ici.** Inutile de mocker `httpx`, `requests`
> ou `urllib` : il n'y a aucun appel réseau à intercepter. Si tu te surprends à
> chercher comment mocker le client HTTP, c'est le signe que tu confonds le
> transport avec la dépendance.

---

## Palier bonus : si tu as fini avant les autres

Écris un test qui vérifie que `POST /carts/{cart_id}/checkout` renvoie un
header `Location` **utilisable** : récupère-le dans la réponse et fais un `GET`
dessus. Deux assertions, aucune valeur en dur.

<details><summary>Indice</summary>

```python
checkout = client.post(f"/carts/{cart_id}/checkout")
location = checkout.headers["Location"]
assert location == "/orders/" + checkout.json()["order_id"]
assert client.get(location).status_code == 200
```

Remarque ce que ce test ne fait **pas** : il n'affirme rien sur la forme de
l'`order_id`. Il le transporte. Garde ce réflexe pour le module 2.

</details>

---

## Critère de réussite

```bash
make test M=0     # vert, sans skip
make swap M=0     # vert sur A et sur B
```

Si `make swap M=0` est vert, tes quatre tests ne savent pas quelle
implémentation ils pilotent. Bon départ.
