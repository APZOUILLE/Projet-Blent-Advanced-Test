# Quand un double de test se justifie (une page)

## Le critère

> **Un double se justifie s'il donne accès à un état ou à un comportement que
> le vrai composant ne peut pas produire à la demande, ou s'il permet de
> vérifier une interaction attendue. Sinon, on utilise le vrai.**

C'est tout. Le reste de cette page n'est que l'application de cette phrase.

Remarque : la question n'est pas « ce double est-il bien écrit ? » mais
« ce double a-t-il une raison d'exister ? ». Un `MagicMock` impeccable qui
remplace un composant parfaitement utilisable est un test en moins, pas un test
mieux fait.

## Ce que « à la demande » veut dire

"A la demande" n'est pas 100% objectif, alors rafinons le critère. Un vrai
composant produit un scénario **à la demande** quand il le produit :

1. **sans faire attendre**, le test reste dans l'ordre de grandeur des autres.
   Personne ne doit hésiter à lancer la suite à cause de lui.
2. **sans impacter la maintenabilité du test**, le code qui fabrique la
   situation n'obfusque pas la compréhension du test. S'il faut 10 fois plus de 
   lignes de préparation que de vérification, le test ne parle plus de ce qu'il
   teste.

Il faut **les deux**. Un scénario rapide mais monté par une boucle absconse
échoue au critère autant qu'un scénario limpide qui prend trentes secondes.

La limite exacte de ce qui est acceptable est subjective et contextuelle, les
besoins de performance d'une itération en local ne sont pas les mêmes que ceux
d'un lancement en CI. C'est à vous de juger ce qui est acceptable.

L'exemple canonique est le palier bonus du module 2 : tester le refus de
`WELCOME10` pour un client à 300 commandes. Le vrai dépôt en est parfaitement
capable en 300 checkouts. Ça coûte du temps, **et** ça remplit le test d'une
boucle qui n'a rien à voir avec la règle testée. Un lecteur qui tombe dessus se
demande d'abord ce que fait cette boucle, et seulement ensuite ce qu'on vérifie.
`StubOrderRepository(order_count=300)` dit la même chose en une ligne.

## Le test à faire passer à chaque dépendance

Pose-toi la question dans cet ordre :

1. **De quel état ou de quel comportement mon scénario a-t-il besoin ?**
2. **Le vrai composant peut-il le produire à la demande**
   - Oui → utilise le vrai. Fin.
   - Non → le double est justifié. Écris le plus petit possible.
3. **Est-ce que ce que je veux vérifier est une interaction, et non un état ?**
   - Oui → un espion est justifié.
   - Non → vérifie l'état, par une route de lecture.

## Appliqué aux trois dépendances de cet atelier

| Dépendance | Verdict | Pourquoi |
|---|---|---|
| `Clock` | **Double indispensable, mais pas partout** | On ne peut pas attendre samedi 18h30 pour tester `WEEKEND` ou `HAPPYHOUR` : le double est la seule voie d'accès au scénario. En revanche, dans un test de `QUANTITY_LIMIT_EXCEEDED` ou de gratuité de livraison, aucune règle temporelle n'intervient : le doubler n'apporte rien et ajoute du bruit. **Même dépendance, verdict opposé selon le scénario.** |
| `IdGenerator` | **Aucun double** | Le vrai fait l'affaire. L'identifiant n'est jamais une valeur *attendue* : il sort du corps de la réponse au checkout et on le réinjecte dans `GET /orders/{id}`. Et le contrat le déclare opaque, donc l'affirmer serait de toute façon un test à jeter. |
| `OrderRepository` | **Le vrai, plus un espion sur un seul test** | L'état « client ayant déjà commandé » se construit très bien avec la vraie base en `:memory:` et un `POST /checkout`. En revanche, *la persistance a bien eu lieu* est une **interaction attendue** : c'est le seul endroit de l'atelier où un espion se justifie. |

## Query / command : quoi vérifier

| Type d'opération | Ce qu'on vérifie | Comment |
|---|---|---|
| **Query** (lecture) | l'**état** | on appelle la route et on affirme la réponse |
| **Command** (écriture) | l'**effet**, et parfois l'**interaction** | on appelle la route, puis on relit par une route de lecture et, quand le chemin d'écriture lui-même est l'enjeu, on l'observe avec un espion |

Et jamais l'inverse : vérifier l'interaction d'une lecture, c'est écrire un
test qui casse au premier refactoring ; vérifier seulement l'état d'une
écriture, c'est parfois passer à côté du sujet.

**Pourquoi l'état ne suffit pas pour le checkout** : un `GET /orders/{id}` qui
répond `200` prouve que la commande est *lisible*. Il ne prouve pas qu'elle est
passée par le chemin de persistance attendu. La nuance paraît byzantine, mais elle
devient critique le jour où la lecture passe par un cache, ou par un réplica.

## Un espion par délégation, jamais par simulation

```python
@dataclass
class SpyOrderRepository:
    inner: OrderRepository                     # le VRAI dépôt
    saved: list[OrderRecord] = field(default_factory=list)

    def save(self, order):
        self.saved.append(order)               # on observe
        self.inner.save(order)                 # et on laisse faire

    def get(self, order_id):
        return self.inner.get(order_id)        # délégation pure
    ...
```

L'espion enveloppe le vrai composant : le comportement réel est préservé, donc
le test reste sensible aux vrais bugs. Un `MagicMock()` à la place aurait
supprimé le comportement en même temps qu'il l'observait.

Et comme un espion est **un objet à état**, il doit être **neuf à chaque test**.
Un espion partagé au niveau du module est exactement le bug numéro 5 du
module 3.

## Encadré propre au REST

Passer par HTTP ne dispense pas de doubles, mais en réduit beaucoup le nombre.

Le contrat HTTP **est déjà une frontière**. Un test qui l'emprunte a déjà
choisi son niveau d'abstraction. Mocker ce qui est derrière, c'est poser une
frontière derrière une frontière : on se retrouve à décrire deux fois la même
chose, et à vérifier la seconde description au lieu du code.

Ce qui reste légitimement à doubler, derrière une API, c'est **ce qui n'est pas
sous ton contrôle à l'instant du test** : le temps, le hasard, un système
tiers, une panne. Pas ta propre logique métier.

## Les deux exceptions qui valident le critère

Deux cas où le vrai composant est réellement incapable de produire le scénario :

- **`StubOrderRepository(order_count=300)`** : tester le refus de `WELCOME10`
  pour un client à 300 commandes. Le vrai dépôt en serait capable en 300
  checkouts. La logique du test est parasitée
- **`FailingOrderRepository`** : tester le `503 PERSISTENCE_UNAVAILABLE`. Une
  base SQLite en mémoire ne tombe pas quand on le lui demande. Pusisque le vrai
  composant est incapable d'échouer à la demande on crée un fake point. Sans
  double, ce chemin de code n'est jamais testé.

Dans les deux cas, le test affirme le code de statut et le `code` documentés.
Jamais la prose du message, jamais un `500` non spécifié.

## Le compteur

`make count-doubles` compte les `MagicMock`, `Mock`, `patch` et les providers
surchargés dans tes tests.

Ce n'est pas une note, et il n'existe pas de bon score. C'est un miroir : la
plupart des suites truffées de mocks le sont devenues sans que personne ne
décide rien. Voir le nombre écrit noir sur blanc suffit souvent à déclencher la
bonne question : *celui-là, pourquoi ?*
