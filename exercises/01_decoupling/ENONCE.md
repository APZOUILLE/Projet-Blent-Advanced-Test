# Module 1 : Découpler les tests des routes (60 min)

**Fichier de travail** : [`test_cart_legacy.py`](test_cart_legacy.py), dix tests qui passent tous sur
l'implémentation A et cassent tous sur l'implémentation B.

**Règle du jeu, non négociable** :

> **N'ouvre pas `src/shop/impl_a/` ni `src/shop/impl_b/`.**
> Écris tes tests depuis [docs/CONTRAT_HTTP.md](../../docs/CONTRAT_HTTP.md).

Tu as le droit de lire [`src/shop/deps.py`](../../src/shop/deps.py), [`src/shop/ports.py`](../../src/shop/ports.py) et
[`src/shop/errors.py`](../../src/shop/errors.py) : ce sont des frontières publiques, pas des
implémentations.

---

## Le décor (5 min)

```bash
make test M=1     # vert : 10 tests passent
make swap M=1     # rouge : les 10 cassent sur l'implémentation B
```

Les deux implémentations répondent au **même contrat HTTP** avec des
architectures internes radicalement différentes. `tests/contract/` le prouve :
mêmes montants au centime, mêmes codes de statut, mêmes `code` d'erreur, même
surface OpenAPI.

Donc si un test passe sur l'une et casse sur l'autre, il ne teste pas le
contrat. Il teste du code. Le swap est un **détecteur de couplage**.

Chacun des dix tests porte en commentaire le vice qu'il incarne.

---

## Étape 1 : Réparer huit tests (35 min)

Pour chaque test, dans l'ordre, pose-toi la question :

> **Quelle règle métier ce test protège-t-il vraiment ?**

Puis réécris-le pour affirmer cette règle-là, en passant **uniquement par les
routes HTTP**. L'intention métier doit survivre intacte : ne remplace pas un
test précis par un test flou.

Repères :

| Vice | Ce qu'il faut faire à la place |
|---|---|
| lire `app.state.carts` | `GET /carts/{cart_id}` |
| appeler le handler comme une fonction | `client.post(...)` |
| `monkeypatch.setattr("shop.impl_a...")` | rien : la règle est dans le contrat, affirme-la |
| `assert response.json() == {...}` | affirmer champ par champ, seulement les champs garantis |
| `lines[0]["sku"]` | indexer par `sku` |
| `assert message == "Cart is empty"` | `assert error["code"] == "EMPTY_CART"` |
| `json()["detail"][0]["loc"]` | `assert response.status_code == 422`, et rien de plus |
| `SELECT total FROM orders` | `GET /orders/{order_id}` |

<details><summary>Indice : indexer les lignes par sku</summary>

```python
def _lines_by_sku(view):
    return {line["sku"]: line for line in view["lines"]}
```

Une fonction de trois lignes en haut du fichier, et le problème d'ordre
disparaît de tous tes tests d'un coup.

</details>

<details><summary>Indice : le test qui lisait la base en SQL</summary>

Son intention est : « le checkout persiste la commande ». Ce qui s'observe très
bien par les routes de lecture :

```python
order_id = client.post(f"/carts/{cart_id}/checkout").json()["order_id"]
assert client.get(f"/orders/{order_id}").json()["total_cents"] == 3590
assert client.get(f"/customers/{CUSTOMER}/orders").json()["count"] == 1
```

Et tu peux supprimer le `tmp_path`, le fichier SQLite et la surcharge de dépôt
qui allaient avec : la base en mémoire de `create_app()` suffit.

</details>

<details><summary>Indice : le test qui affirmait tout le corps</summary>

Une implémentation ajoute `_debug_impl` et `raw_total`. Le contrat autorise
explicitement les champs supplémentaires. Donc l'égalité stricte est perdue
d'avance. Pas seulement fragile : **fausse**. Affirme les champs garantis, un
par un.

</details>

---

## Étape 2 : Supprimer deux tests (10 min)

**Tous les tests couplés ne se réparent pas. Certains se jettent.**

Deux des dix ne protègent aucune règle métier. Trouve-les, supprime-les, et
**remplace-les par un commentaire** qui explique :

- ce qu'il affirmait ;
- pourquoi ce n'était pas une règle métier ;
- où l'intention utile est couverte, si elle l'est.

<details><summary>Indice : comment reconnaître un test à jeter</summary>

Relis la liste des **zones non garanties** du contrat. Si tout ce qu'un test
affirme figure dans cette liste, alors il protège un choix d'implémentation, pas
une décision métier. Le réparer produirait au mieux un doublon d'un autre test.

</details>

---

## Étape 3 : Trois tests à écrire depuis le contrat (10 min)

Trois règles du contrat ne sont couvertes par aucun test. Couvre-les, en lisant
**uniquement** [le contrat de l'API](../../docs/CONTRAT_HTTP.md) :

1. **`QUANTITY_LIMIT_EXCEEDED` sur un cumul** : un panier ne peut pas contennir
   plus de 10 fois le même SKU. Vérifie aussi qu'une requête d'ajout refusée ne
   modifie pas le panier.
2. **La gratuité de livraison au seuil exact** : le contrat dit *strictement
   au-dessus de 5000*. Écris les deux côtés du seuil. Attention : un client n'a
   qu'un panier à la fois, donc deux paniers dans un même test, c'est deux
   `customer_id`.
3. **`UNKNOWN_COUPON` contre `COUPON_NOT_APPLICABLE`** : vérifie qu'aucun des
   deux refus n'applique le coupon sur le panier.

<details><summary>Indice : pour le troisième, il faut une horloge</summary>

`HAPPYHOUR` n'est valable qu'entre 18h et 20h. Pour tester son refus de façon
déterministe, il faut choisir l'instant :

```python
app = create_app()
app.dependency_overrides[deps.get_clock] = lambda: FixedClock(
    datetime(2026, 3, 10, 10, 0, tzinfo=PARIS)  # un mardi, 10h00
)
```

</details>

---

## Étape 4 : Demander à l'outil ce qui manque encore (10 min)

Tu viens d'écrire trois tests que tu as choisis en lisant le contrat. Mais
comment savoir ce que tu n'as **pas** pensé à couvrir ?

```bash
make coverage
```

La commande mesure quelles lignes de l'application tes tests font réellement
exécuter, sur les deux implémentations, et traduit chaque ligne jamais atteinte
en **règle du contrat que personne ne vérifie**. Tu n'as pas à lire
`src/shop/` pour ça, c'est elle qui fait la traduction.

Écris les tests qu'elle réclame, jusqu'à ce qu'elle passe au vert.

> **Le coverage seul n'est pas un indicateur de la qualité des test.**
> Une suite sans assertions ou couverte de mocks atteint elle aussi 100 % : il
> suffit d'appeler les routes. *La règle à retenir c'est qu'à moins de 100% une
> règle n'est testée par personne.* Atteindre 100% ne prouve pas en revanche
> que les tests sont qualitatifs. C'est pour ça que `make coverage` ne remplace
> ni `make swap`, ni `make sabotage`.
>
> Si tu veux t'en convaincre :
> écris quatre tests qui appellent les routes **sans un seul `assert`**, lance
> `make coverage` puis `make sabotage` sur le même fichier. Le bug passe
> comme une lettre à la poste. Supprime ces tests ensuite.

<details><summary>Indice : par où commencer</summary>

Les règles qui manquent le plus souvent sont les **chemins d'échec** et les
routes qu'on oublie parce qu'on ne s'en sert pas soi-même : demander une
ressource qui n'existe pas, retirer une ligne d'un panier, se voir refuser une
action qu'on croyait acquise.

Relis le tableau des codes d'erreur du contrat, ligne par ligne, et demande-toi
pour chacun : *ai-je un test qui provoque celui-là ?*

</details>

---

## Critères de réussite

```bash
make swap M=1     # vert sur A et sur B
make coverage     # 100 % sur A et sur B
```

**`make swap M=1` vert**, c'est la même suite, sans une ligne modifiée entre les
deux exécutions. **`make coverage` vert**, c'est qu'aucune règle du contrat n'est
laissée sans filet.

---

## Palier bonus : si tu as fini avant les autres

Écris un test qui affirme le comportement du `DELETE` sur un `sku` absent. Le
contrat dit que l'opération est **idempotente** : `204`, et le panier
inchangé. Combien de tests de ton propre projet auraient supposé un `404` ?

Deuxième bonus, plus retors : écris un test qui affirme que `PUT
/carts/{id}/coupon` **remplace** le coupon actif au lieu de l'ajouter. Vérifie
la remise après le remplacement, pas seulement le champ `coupon`.

Troisième bonus, celui qui compte le plus : un client n'a qu'un panier à la
fois, et un second `POST /carts` renvoie `409 CART_ALREADY_EXISTS`. Écris le
test qui prouve que ce refus **n'enferme pas le client dehors**, c'est-à-dire
que l'identifiant qu'il rend est réellement utilisable. Puis écris celui qui
prouve qu'un checkout réussi supprime le panier, et qu'un checkout raté le
laisse intact.
