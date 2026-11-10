# Contrat HTTP de la boutique

C'est **la seule source de vérité** de cet atelier. Tes tests doivent s'écrire
depuis ce document, pas depuis le code de `src/shop/impl_*`.

Deux implémentations différentes répondent à ce contrat, et le repo prouve
qu'elles sont interchangeables (`tests/contract/`). Tout ce que ce document ne
garantit pas explicitement peut changer d'une implémentation à l'autre, et
changera.

---

## Routes

| Méthode | Route | Corps de requête | Réponse |
|---|---|---|---|
| `POST` | `/carts` | `{"customer_id": str}` | `201` `{"cart_id": str}`, ou `409` si le client a déjà un panier |
| `GET` | `/carts/{cart_id}` | aucun | `200` vue de panier |
| `POST` | `/carts/{cart_id}/items` | `{"sku": str, "quantity": int, "unit_price_cents": int}` | `204` |
| `DELETE` | `/carts/{cart_id}/items/{sku}` | aucun | `204` |
| `PUT` | `/carts/{cart_id}/coupon` | `{"code": str}` | `204` |
| `POST` | `/carts/{cart_id}/checkout` | aucun | `201` vue de commande + header `Location` |
| `GET` | `/orders/{order_id}` | aucun | `200` vue de commande |
| `GET` | `/customers/{customer_id}/orders` | aucun | `200` `{"count": int, "orders": [vue de commande]}` |

Précisions :

- **Un client a au plus un panier en cours.** `POST /carts` renvoie `201` s'il
  n'en a aucun, et `409 CART_ALREADY_EXISTS` sinon. Ce `409` **porte l'identifiant
  du panier existant**, à deux endroits : dans le corps (`error.cart_id`) et
  dans le header `Location`. Un client n'est donc jamais enfermé hors de son
  propre panier.
- `POST /carts/{cart_id}/items` **cumule** les unités d'un même `sku`. Le
  dernier `unit_price_cents` reçu remplace le précédent pour ce `sku`.
- `DELETE` d'un `sku` absent renvoie `204` : l'opération est idempotente.
- `PUT /carts/{cart_id}/coupon` **remplace** le coupon actif. Un panier n'a
  jamais plus d'un coupon.
- L'applicabilité d'un coupon est vérifiée **au moment du `PUT`**, pas au
  checkout. Un panier peut donc changer de contenu après avoir reçu un coupon.
- **Un checkout réussi supprime le panier.** La commande porte sa propre copie
  des lignes, le panier n'a plus de raison d'exister. Conséquences :
  `GET /carts/{cart_id}` renvoie alors `404 CART_NOT_FOUND`, un second checkout
  sur le même `cart_id` renvoie `404` lui aussi, et le client peut ouvrir un
  nouveau panier par `POST /carts`.
- **Un checkout qui échoue ne touche pas au panier.** Après un
  `409 EMPTY_CART` ou un `503 PERSISTENCE_UNAVAILABLE`, le panier est intact et
  toujours lisible.
- `Location` vaut exactement `/orders/{order_id}` au checkout, et
  `/carts/{cart_id}` sur le `409` de `POST /carts`.

## Vues

**Vue de panier**, champs garantis :
`cart_id`, `customer_id`, `lines`, `coupon`, `subtotal_cents`,
`discount_cents`, `shipping_cents`, `total_cents`.

**Vue de commande**, champs garantis :
`order_id`, `customer_id`, `lines`, `subtotal_cents`, `discount_cents`,
`shipping_cents`, `total_cents`, `placed_at` (ISO 8601 avec offset).

**Ligne**, champs garantis : `sku`, `quantity`, `unit_price_cents`.

`coupon` vaut `null` quand aucun coupon n'est posé.

---

## Zones NON garanties

C'est la partie la plus importante du document. Un test qui s'appuie sur l'un
de ces points est un test couplé, même s'il passe aujourd'hui.

1. **L'ordre des éléments de `lines`** n'est pas garanti. Une implémentation
   renvoie l'ordre d'insertion, l'autre trie par `sku`. Indexe tes lignes par
   `sku`, jamais par position.
2. **Des champs supplémentaires** peuvent être présents dans n'importe quelle
   réponse. Une implémentation expose `_debug_impl` et `raw_total`. Un client
   ne doit pas en dépendre, donc un test non plus. Corollaire : pas d'égalité
   stricte (`==`) sur un corps de réponse entier.
   La règle se lit dans ce sens et pas dans l'autre : **ce que ce document
   déclare garanti l'est**, y compris `error.cart_id` sur un
   `CART_ALREADY_EXISTS`. Tout le reste est du bonus, et peut disparaître.
3. **`order_id` est une chaîne opaque**, préfixée `ORD-`, d'au plus 32
   caractères. Ni sa longueur exacte, ni sa casse, ni son alphabet ne sont
   garantis. Une implémentation produit `ORD-` + 8 hexadécimaux minuscules,
   l'autre `ORD-` + 12 caractères base32 majuscules. Transporte-le, ne le
   prédis pas.
4. **`cart_id` est également opaque.**
5. **Le champ `message` des erreurs est de la prose non stable.** Il est là
   pour un humain qui lit un log. Le champ stable, c'est `code`.
6. **Les headers hors `Location` et `Content-Type` ne sont pas garantis.** Une
   implémentation renvoie un `X-Impl` maison ; l'autre non. `Location`, lui, est
   garanti aux deux endroits où le contrat le mentionne : la réponse du checkout
   et le `409` de `POST /carts`.
7. **L'ordre de la liste `orders`** de `GET /customers/{id}/orders` n'est pas
   garanti. Seul `count` l'est, et le fait que la liste contienne exactement
   ces commandes-là.
8. **Les erreurs de validation de corps** (champ manquant, quantité négative,
   type invalide) renvoient `422`. **La structure du corps d'un `422` n'est pas
   garantie** : une implémentation renvoie la charge utile par défaut de
   FastAPI (`{"detail": [...]}`), l'autre la sienne
   (`{"error": {"code": "INVALID_BODY", ...}}`). Appuie-toi sur le **code de
   statut**, jamais sur la forme du corps.
9. **Les routes de debug ne font pas partie du contrat.** Une implémentation
   expose `GET /_internal/state`, hors schéma OpenAPI. Elle peut disparaître
   sans préavis, et disparaît effectivement dans l'autre implémentation.

---

## Erreurs métier

Corps garanti : `{"error": {"code": "...", "message": "..."}}`.
`code` est stable. `message` ne l'est pas. Certains codes ajoutent une clé
documentée dans `error` : la seule aujourd'hui est `cart_id`, sur
`CART_ALREADY_EXISTS`.

| Statut | `code` | Quand |
|---|---|---|
| `404` | `CART_NOT_FOUND` | le panier n'existe pas, ou a été supprimé par un checkout |
| `404` | `ORDER_NOT_FOUND` | la commande n'existe pas |
| `404` | `UNKNOWN_COUPON` | le code de coupon n'existe pas |
| `409` | `CART_ALREADY_EXISTS` | le client a déjà un panier en cours |
| `409` | `EMPTY_CART` | checkout d'un panier sans ligne |
| `409` | `QUANTITY_LIMIT_EXCEEDED` | plus de 10 unités cumulées d'un même `sku` |
| `409` | `COUPON_NOT_APPLICABLE` | le coupon existe, ses conditions ne sont pas réunies |
| `503` | `PERSISTENCE_UNAVAILABLE` | le stockage est injoignable au checkout |

**Sur le `409 CART_ALREADY_EXISTS`** : un refus qui ne dirait pas *où* est le
panier existant enfermerait le client dehors, sans recours. La réponse porte donc
l'identifiant du panier en cours, dans `error.cart_id` **et** dans le header
`Location`. Les deux sont garantis et désignent le même panier.

**Sur le `404 UNKNOWN_COUPON` contre le `409 COUPON_NOT_APPLICABLE`** : la
distinction est délibérée et utile au client. « Ce code n'existe pas » et
« ce code existe mais pas pour vous, pas maintenant » n'appellent pas la même
réaction côté interface.

**Sur le `503 PERSISTENCE_UNAVAILABLE`** : quand le stockage des commandes est
injoignable au moment du checkout, l'API répond `503` et **aucune commande
n'est créée**. C'est une réalité que toute API doit gérer, donc c'est dans le
contrat, et ça donne aux tests une cible garantie à affirmer, au lieu d'un
`500` non spécifié. Côté code, toute implémentation d'`OrderRepository` peut
lever `shop.errors.PersistenceUnavailable` ; le mapping HTTP est dans
[`shop/errors.py`](../src/shop/errors.py), partagé par les deux implémentations.

---

## Règles métier

Tous les montants sont des **entiers de centimes**.

### Cycle de vie du panier

Un client a **au plus un panier en cours**. Il l'ouvre par `POST /carts`, le
remplit, puis le consomme par un checkout, qui le **supprime**. Il peut alors
en ouvrir un nouveau.

Tant qu'un panier est ouvert, `POST /carts` refuse d'en créer un second
(`409 CART_ALREADY_EXISTS`) et rend l'identifiant de celui qui existe. Un
checkout qui échoue laisse le panier ouvert et intact.

Il n'existe pas de route pour abandonner un panier : le seul moyen de le faire
disparaître est un checkout réussi. Les détails de réponse sont dans
[Routes](#routes) et [Erreurs métier](#erreurs-métier).

### Calcul

```
sous-total   = somme(quantity * unit_price_cents)
remise       = sous-total * pourcentage_du_coupon // 100      (arrondi INFÉRIEUR)
à_payer      = sous-total - remise
livraison    = 0 si à_payer > 5000, sinon 590
total        = sous-total - remise + livraison
```

**Le seuil est strict.** À 5000 centimes exactement après remise, la livraison
est encore facturée. À 5001, elle est offerte.

**Conséquence assumée** : un panier vide affiche `shipping_cents = 590` et
`total_cents = 590`, puisque 0 n'atteint pas le seuil. Ce cas ne devient jamais
une commande, le checkout d'un panier vide étant refusé (`409 EMPTY_CART`).

### Quantités

Maximum **10 unités cumulées par `sku`** dans un panier. La 11ᵉ est refusée par
`409 QUANTITY_LIMIT_EXCEEDED`, et le panier n'est pas modifié. Le plafond porte
sur le cumul, pas sur une requête isolée : 4 puis 7 est refusé.

`quantity` doit être strictement positif et `unit_price_cents` positif ou nul,
sinon `422`.

### Coupons

Un seul coupon actif par panier. Toutes les conditions horaires et calendaires
sont évaluées en **heure de Paris** (`Europe/Paris`), à l'instant fourni par
l'horloge de l'application.

| Code | Remise | Condition | Dépend de |
|---|---|---|---|
| `WELCOME10` | −10 % | le client n'a **aucune** commande passée | le dépôt de commandes |
| `HAPPYHOUR` | −5 % | il est entre **18h00 inclus et 20h00 exclu** | l'horloge |
| `WEEKEND` | −15 % | on est **samedi ou dimanche** | l'horloge |
| `NEWYEAR` | −20 % | **jusqu'au 31 décembre inclus de l'année en cours** | l'horloge |

Les codes sont **sensibles à la casse** : `welcome10` est un coupon inconnu.

Un coupon absent de cette table → `404 UNKNOWN_COUPON`.
Un coupon de cette table dont la condition n'est pas remplie → `409
COUPON_NOT_APPLICABLE`, au moment du `PUT`, et le panier garde le coupon qu'il
avait (ou aucun).

> **Note sur `NEWYEAR`** : la validité est recalculée depuis l'horloge à chaque
> `PUT`, et la borne est le 31 décembre de l'année *que l'horloge indique*. La
> condition est donc toujours vraie en pratique. C'est écrit tel quel dans le
> contrat parce que c'est ce que fait le code : une promotion de fin d'année
> dont personne n'a jamais programmé l'expiration réelle. Un test qui affirme
> « il reste des jours avant la fin de la promo » en lisant l'horloge système
> casse le 31 décembre : c'est exactement le piège du module 3.

### Identifiants et horodatage

- `order_id` est produit par l'`IdGenerator` de l'application.
- `placed_at` est produit par le `Clock` de l'application, et sérialisé en
  ISO 8601 **avec offset**.

Les deux sont injectables en test via `shop.deps.get_id_generator` et
`shop.deps.get_clock` (voir [TESTCLIENT.md](TESTCLIENT.md)).
