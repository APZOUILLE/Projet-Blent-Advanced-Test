"""Les seuls doubles de test dont ce module a besoin. Squelettes a completer.

Deux artefacts pour le coeur de l'exercice, deux de plus pour le palier bonus.
Aucun `MagicMock`, aucun `patch` : ces classes sont courtes, explicites, et on
lit dans leur code exactement ce qu'elles simulent.

Rappel du critere, a appliquer avant d'ecrire une seule ligne :

    Un double se justifie s'il donne acces a un etat ou a un comportement que
    le vrai composant ne peut pas produire a la demande, ou s'il permet de
    verifier une interaction attendue. Sinon, on utilise le vrai.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shop.ports import OrderRecord, OrderRepository


@dataclass(frozen=True)
class FixedClock:
    """Horloge figee : renvoie toujours le meme instant.

    Justification : on ne peut pas attendre un samedi 18h30 pour tester
    WEEKEND ou HAPPYHOUR. Le double est la seule voie d'acces au scenario.

    L'instant doit etre **timezone-aware** : les regles de coupon sont
    evaluees en heure de Paris, et un datetime naif changerait la decision
    metier sans prevenir.

    Args:
        instant: l'instant renvoye par chaque appel a `now()`.
    """

    instant: datetime

    def now(self) -> datetime:
        raise NotImplementedError("TODO module 2, etape 3")


@dataclass
class SpyOrderRepository:
    """Espion par delegation : observe `save`, delegue tout le reste.

    Justification : "la commande a bien ete persistee" est une **interaction
    attendue**, pas un etat lisible. C'est le seul endroit de l'atelier ou un
    espion se justifie.

    Par delegation, et pas par simulation : le vrai depot fait le travail, donc
    le comportement reste reel et le test reste sensible aux vrais bugs. On
    observe, on ne remplace pas.

    Args:
        inner: le vrai depot, construit par `shop.create_order_repository()`.

    Attributes:
        saved: les commandes passees a `save`, dans l'ordre.
    """

    inner: OrderRepository
    saved: list[OrderRecord] = field(default_factory=list)

    def save(self, order: OrderRecord) -> None:
        raise NotImplementedError("TODO module 2, etape 3")

    def get(self, order_id: str) -> OrderRecord | None:
        raise NotImplementedError("TODO module 2, etape 3")

    def list_for_customer(self, customer_id: str) -> list[OrderRecord]:
        raise NotImplementedError("TODO module 2, etape 3")

    def count_for_customer(self, customer_id: str) -> int:
        raise NotImplementedError("TODO module 2, etape 3")


# ---------------------------------------------------------------------------
# Palier bonus : deux cas ou le vrai composant est reellement incapable de
# produire le scenario. Ce sont les exceptions qui valident le critere.
# ---------------------------------------------------------------------------


@dataclass
class StubOrderRepository:
    """Depot qui annonce un nombre de commandes arbitraire.

    Justification : tester le refus de WELCOME10 pour un client a 300 commandes
    sans passer 300 checkouts. Le vrai depot en serait capable, mais le temps
    d'attente et la lisibilitée seraient impactées.

    Args:
        order_count: la valeur renvoyee par `count_for_customer`.
    """

    order_count: int
    saved: list[OrderRecord] = field(default_factory=list)

    def save(self, order: OrderRecord) -> None:
        raise NotImplementedError("TODO module 2, palier bonus")

    def get(self, order_id: str) -> OrderRecord | None:
        raise NotImplementedError("TODO module 2, palier bonus")

    def list_for_customer(self, customer_id: str) -> list[OrderRecord]:
        raise NotImplementedError("TODO module 2, palier bonus")

    def count_for_customer(self, customer_id: str) -> int:
        raise NotImplementedError("TODO module 2, palier bonus")


@dataclass
class FailingOrderRepository:
    """Depot dont l'ecriture echoue toujours.

    Justification : le `503 PERSISTENCE_UNAVAILABLE` du contrat est
    impossible a provoquer avec une vraie base SQLite en memoire -- elle ne
    tombe pas a la demande.

    `save` doit lever `shop.errors.PersistenceUnavailable`. Le test qui s'en
    sert affirme le code de statut et le `code` documentes, jamais la prose du
    message.
    """

    def save(self, order: OrderRecord) -> None:
        raise NotImplementedError("TODO module 2, palier bonus")

    def get(self, order_id: str) -> OrderRecord | None:
        return None

    def list_for_customer(self, customer_id: str) -> list[OrderRecord]:
        return []

    def count_for_customer(self, customer_id: str) -> int:
        return 0
