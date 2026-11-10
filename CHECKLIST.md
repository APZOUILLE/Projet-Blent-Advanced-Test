# Checklist d'un bon test

Neuf questions à se poser **avant d'ouvrir une PR**.

---

## Découplage

**Mon test passerait-il si on réécrivait l'application derrière les mêmes
routes ?**
Si tu hésites : `make swap`.

**Saurais-je dire quelle règle métier il protège**
Si la seule réponse est un nom de fonction, ce n'est pas une règle métier.

**Ai-je affirmé quelque chose que le contrat ne garantit pas ?**
La liste habituelle : l'ordre d'une collection, un corps de réponse entier, le
format d'un identifiant, la prose d'un message, la charge utile d'une erreur de
validation, un header que le contrat ne nomme pas, un schéma de base, une route
de debug.

**Est-ce que mon test franchit une frontière que la documentation publique ne
mentionne pas ?**
`app.state`, un import d'implémentation, un appel de handler, une requête SQL :
quatre portes dérobées, quatre tests morts à la prochaine refonte.

---

## Doubles

**Chacun de mes doubles me donne-t-il accès à quelque chose que le vrai
composant ne sait pas produire ?**
Sinon, utilise le vrai. C'est tout le critère.

**Mon test détecterait-il un vrai bug dans le code qu'il couvre ?**
Un test ne peut détecter un bug que dans le code qu'il **exécute réellement**.
Chaque double retire du code de la zone couverte.

**Est-ce que je vérifie une interaction là où un état suffirait ?**
Query → on vérifie l'**état**. Command → l'**effet**, et l'**interaction**
seulement quand le chemin d'écriture est lui-même l'enjeu. Jamais l'inverse.

---

## Indépendance

**Ai-je un objet à état partagé entre deux tests ?**
Application, client, base de données, surcharge de dépendance, espion,
compteur, cache, panier « préparé » pour le voisin. Si tu en trouves un :
`make shuffle`.

**Mon test passerait-il un dimanche à minuit ?**
Un `datetime.now()`, un `date.today()`, une attente qui dépend du jour ou de
l'heure réels. Si tu en trouves un : `make check-dates`.

---

## Couverture

**Y a-t-il une règle du contrat que mes tests n'atteignent jamais ?**
`make coverage` la nomme. Une ligne jamais exécutée, c'est un pan du contrat
sans filet.

**Et est-ce que je me raconte une histoire avec ce 100 % ?**
Une suite sans une seule assertion atteint 100 % elle aussi. Moins de 100 %
prouve qu'il manque un test ; 100 % ne prouve rien tout seul.

---

## Les quatre commandes

```bash
make swap          # tes tests connaissent-ils l'implémentation ?
make shuffle       # ... connaissent-ils leurs voisins ?
make check-dates   # ... connaissent-ils l'heure qu'il est ?
make coverage      # ... touchent-ils toutes les règles du contrat ?
```

---

## Et deux phrases à emporter

> **Tous les tests couplés ne se réparent pas. Certains se jettent.**

> **Un double se justifie s'il donne accès à un état ou à un comportement que
> le vrai composant ne peut pas produire à la demande, ou s'il permet de
> vérifier une interaction attendue. Sinon, on utilise le vrai.**
