# Conception — Comptage d’inventaire par emplacement avec Google Sheets

Date : 2026-07-20

## 1. Objectif

Transformer l’application Streamlit actuelle en un outil de comptage d’inventaire fiable, rapide sur téléphone et capable de reprendre une session interrompue.

Le même catalogue de produits doit être compté séparément dans trois emplacements, toujours dans cet ordre :

1. Lounge
2. Réception & Bureau
3. QBE

Tous les produits actifs apparaissent dans les trois emplacements. Une seule personne utilise l’application à la fois.

## 2. Décisions validées

- L’application reste construite avec Streamlit.
- Google Sheets devient la source de vérité pour le catalogue, les sessions et les comptages.
- Le nom de l’employé est saisi librement et est obligatoire avant de commencer.
- Chaque produit possède un comptage distinct pour chacun des trois emplacements.
- Une quantité de zéro peut être explicitement marquée comme vérifiée.
- Le catalogue peut être ajouté, désactivé ou réordonné sans modifier le code.
- Chaque validation est sauvegardée immédiatement dans Google Sheets.
- Une session non terminée peut être reprise.
- Une session terminée est verrouillée par défaut.
- L’abandon ou la remise à zéro exige une confirmation explicite et ne supprime pas silencieusement l’historique.

## 3. Architecture de l’application

L’application sera séparée en modules ayant chacun une responsabilité claire.

### `app.py`

Responsable de l’interface Streamlit, de la navigation entre les écrans et de l’affichage des messages.

Écrans principaux :

- identification de l’employé;
- nouvelle session ou reprise d’une session;
- comptage guidé;
- vue de correction complète;
- résumé et fermeture de la session.

### `catalog.py`

Responsable de charger et valider le catalogue provenant de l’onglet `Produits`.

Il doit notamment :

- ignorer les produits désactivés;
- trier les produits selon leur ordre;
- vérifier que chaque identifiant est unique;
- refuser les lignes invalides avec un message compréhensible.

### `inventory.py`

Responsable des règles métier indépendantes de Streamlit et de Google Sheets.

Il doit notamment :

- générer toutes les combinaisons produit × emplacement;
- distinguer une ligne non vérifiée d’une ligne vérifiée à zéro;
- calculer la progression;
- calculer les totaux par produit et par emplacement;
- déterminer si une session peut être terminée;
- empêcher la modification d’une session terminée ou abandonnée.

### `google_sheets.py`

Responsable de toutes les communications avec Google Sheets.

Il doit notamment :

- lire la configuration et le catalogue;
- créer une session;
- créer les lignes de comptage associées;
- enregistrer une quantité et son état de vérification;
- retrouver la dernière session non terminée;
- terminer, abandonner ou rouvrir explicitement une session;
- transformer les erreurs Google en messages utiles pour l’interface.

### `tests/`

Contient les tests automatisés des règles métier et des validations de données. Les accès Google Sheets seront simulés dans les tests unitaires.

## 4. Structure du Google Sheets

Le fichier Google Sheets contient quatre onglets avec des noms fixes.

### Onglet `Produits`

Une ligne par produit du catalogue.

| Colonne | Type | Rôle |
|---|---|---|
| `product_id` | texte | Identifiant stable et unique, par exemple `MAILLOT-F-028` |
| `product_name` | texte | Nom affiché dans l’application |
| `category` | texte | Catégorie commerciale du produit |
| `sort_order` | entier | Ordre d’affichage dans chaque emplacement |
| `active` | booléen | Détermine si le produit apparaît dans une nouvelle session |

Le nom du produit n’est jamais utilisé comme clé technique. Renommer un produit ne doit donc pas casser l’historique.

### Onglet `Sessions`

Une ligne par inventaire.

| Colonne | Type | Rôle |
|---|---|---|
| `session_id` | texte | UUID unique |
| `employee_name` | texte | Nom saisi librement au début |
| `started_at` | date-heure | Début de la session |
| `ended_at` | date-heure ou vide | Fin, abandon ou fermeture de la session |
| `status` | texte | `IN_PROGRESS`, `COMPLETED`, `REOPENED` ou `ABANDONED` |
| `verified_count` | entier | Nombre de lignes vérifiées |
| `total_count` | entier | Nombre total de lignes attendues |
| `total_units` | entier | Somme des quantités enregistrées |

Les champs de résumé peuvent être recalculés, mais sont conservés pour rendre l’onglet facile à consulter.

### Onglet `Comptages`

Une ligne par combinaison session × emplacement × produit.

| Colonne | Type | Rôle |
|---|---|---|
| `count_id` | texte | UUID unique |
| `session_id` | texte | Référence vers `Sessions` |
| `location` | texte | `Lounge`, `Réception & Bureau` ou `QBE` |
| `product_id` | texte | Référence vers `Produits` |
| `product_name_snapshot` | texte | Nom du produit au moment du comptage |
| `quantity` | entier ou vide | Quantité comptée; vide signifie non vérifié |
| `verified` | booléen | Confirme que l’emplacement a été vérifié, même si la quantité est zéro |
| `verified_at` | date-heure ou vide | Heure de la validation |
| `updated_at` | date-heure | Dernière modification |

Le champ `product_name_snapshot` permet de conserver un historique lisible même si le produit est renommé plus tard.

### Onglet `Configuration`

Format clé-valeur.

| Colonne | Type | Exemple |
|---|---|---|
| `key` | texte | `destination_email` |
| `value` | texte | adresse courriel interne |

Clés initiales :

- `destination_email`
- `location_1 = Lounge`
- `location_2 = Réception & Bureau`
- `location_3 = QBE`
- `require_all_verified = true`

## 5. Création d’une session

Lorsqu’un nouvel inventaire est créé :

1. L’employé saisit son nom.
2. L’application charge tous les produits actifs, triés selon `sort_order`.
3. Une ligne est créée dans `Sessions` avec le statut `IN_PROGRESS`.
4. Pour chaque produit, trois lignes sont créées dans `Comptages`, une par emplacement.
5. Les quantités sont initialement vides et `verified` vaut `false`.
6. L’application ouvre le premier produit non vérifié du Lounge.

Le nombre total de lignes attendues est :

`nombre de produits actifs × 3 emplacements`.

## 6. Reprise d’une session

Au démarrage, l’application recherche la plus récente session ayant le statut `IN_PROGRESS` ou `REOPENED`.

Si une session existe, l’interface affiche :

- le nom de l’employé;
- la date et l’heure de début;
- la progression;
- un bouton pour reprendre;
- un bouton séparé pour abandonner la session, protégé par confirmation.

Comme une seule personne utilise l’application à la fois, aucun système de verrouillage multiutilisateur n’est requis dans cette version.

## 7. Flux de comptage guidé

Le comptage suit l’ordre fixe des emplacements, puis l’ordre du catalogue dans chaque emplacement.

Pour chaque ligne, l’écran affiche :

- l’emplacement actuel;
- le nom et la catégorie du produit;
- la progression globale;
- un champ numérique;
- les commandes `−1`, `+1` et `+5`;
- un bouton `Valider et suivant`.

Lors de la validation :

1. La quantité est convertie en entier supérieur ou égal à zéro.
2. `verified` devient `true`, y compris lorsque la quantité vaut zéro.
3. La ligne est sauvegardée dans Google Sheets.
4. La session est mise à jour avec sa progression et ses totaux.
5. L’application avance seulement après confirmation de la sauvegarde.

L’application ne doit jamais déduire qu’un produit est vérifié simplement parce que sa quantité est supérieure à zéro.

## 8. Vue de correction

Une vue secondaire permet de voir toutes les lignes de la session, regroupées par emplacement dans l’ordre suivant :

1. Lounge
2. Réception & Bureau
3. QBE

Chaque ligne affiche :

- le produit;
- la quantité;
- l’état vérifié ou non vérifié;
- l’heure de la dernière modification.

Une modification sauvegarde immédiatement la nouvelle valeur. Une ligne peut aussi être remise à l’état non vérifié avant la fermeture de la session.

## 9. Résumé et fermeture

Le résumé affiche :

- la progression globale;
- le total d’unités par emplacement;
- le total consolidé par produit;
- le total général;
- la liste des lignes non vérifiées.

Le total consolidé d’un produit est :

`quantité Lounge + quantité Réception & Bureau + quantité QBE`.

Le bouton `Terminer l’inventaire` est désactivé tant que des lignes ne sont pas vérifiées lorsque `require_all_verified` vaut `true`.

À la fermeture :

- la session passe à `COMPLETED`;
- `ended_at` est enregistré;
- la session devient non modifiable;
- un rapport CSV peut être téléchargé;
- un résumé prêt à transmettre est généré à partir des données sauvegardées.

Une session terminée peut seulement être modifiée après une action explicite `Rouvrir la session`, accompagnée d’une confirmation. La réouverture passe son statut à `REOPENED` et efface `ended_at` jusqu’à sa prochaine fermeture.

## 10. Abandon et remise à zéro

Aucune session n’est abandonnée ou remise à zéro par un simple clic.

L’utilisateur doit :

1. ouvrir la section de danger;
2. cliquer sur `Abandonner cette session`;
3. saisir exactement `EFFACER`;
4. confirmer une deuxième fois.

L’abandon passe la session à `ABANDONED`, inscrit `ended_at` et conserve les lignes existantes pour l’historique. Pour recommencer à zéro, l’utilisateur crée ensuite une nouvelle session. Aucune ligne historique n’est supprimée automatiquement.

## 11. Gestion des erreurs

### Google Sheets inaccessible

- La valeur courante reste dans `st.session_state` pendant que la session du navigateur demeure ouverte.
- L’application affiche que la sauvegarde n’a pas été confirmée.
- Elle ne passe pas au produit suivant.
- Un bouton `Réessayer la sauvegarde` est affiché.
- L’application ne prétend jamais que la donnée est enregistrée avant une réponse positive de Google Sheets.

Cette conservation temporaire ne garantit pas la survie à une fermeture ou à un rafraîchissement du navigateur.

### Catalogue invalide

L’application bloque la création d’une nouvelle session et affiche les erreurs précises : identifiant manquant, doublon, ordre invalide ou nom vide.

### Session terminée ou abandonnée

Toute tentative de modification est refusée tant que la session n’a pas été rouverte explicitement. Une session abandonnée n’est pas proposée automatiquement à la reprise.

### Secrets manquants

L’application affiche une erreur de configuration sans exposer le contenu des identifiants.

## 12. Sécurité et configuration Google

Les identifiants du compte de service Google sont placés dans les secrets Streamlit et ne sont jamais enregistrés dans GitHub.

Le Google Sheets est partagé uniquement avec l’adresse du compte de service. L’accès direct au fichier est limité aux employés autorisés par Google Workspace.

L’adresse courriel de destination est retirée du code et placée dans l’onglet `Configuration`.

## 13. Dépendances prévues

- `streamlit`
- `pandas`
- `gspread`
- `google-auth`
- `pytest`

Les versions seront fixées à des versions testées afin d’éviter qu’une mise à jour automatique casse l’application ou son CSS.

## 14. Tests obligatoires

### Règles métier

- Une quantité zéro avec `verified = true` compte dans la progression.
- Une quantité vide avec `verified = false` ne compte pas dans la progression.
- Chaque produit actif génère exactement trois lignes, une par emplacement.
- Les emplacements sont toujours ordonnés Lounge, Réception & Bureau, QBE.
- Le total produit additionne correctement les trois emplacements.
- Le total par emplacement additionne correctement tous les produits.
- Une session ne peut pas être terminée avec des lignes non vérifiées lorsque la configuration l’interdit.
- Une session terminée ou abandonnée refuse les modifications.

### Catalogue

- Les identifiants de produit doivent être uniques.
- Un produit inactif n’apparaît pas dans une nouvelle session.
- Les produits sont triés selon `sort_order`.
- Renommer un produit ne change pas son identifiant.

### Persistance

- Une session interrompue peut être retrouvée et reprise.
- Une session abandonnée n’est pas proposée automatiquement à la reprise.
- Une sauvegarde échouée ne fait pas avancer le comptage.
- Une sauvegarde réussie met à jour la progression de la session.
- La réouverture explicite d’une session terminée permet de nouveau les modifications.

## 15. Hors portée de cette version

- Comptage simultané par plusieurs employés.
- Mode entièrement hors ligne.
- Lecture de codes-barres.
- Gestion de plusieurs établissements.
- Gestion avancée des rôles et permissions dans l’application.
- Notifications automatiques complexes.

Ces fonctions pourront être ajoutées plus tard sans modifier le modèle principal produit × emplacement × session.

## 16. Critères d’acceptation

La version est considérée réussie lorsque :

1. Un employé peut commencer un inventaire en saisissant son nom.
2. Tous les produits actifs sont présentés aux trois emplacements dans le bon ordre.
3. Une quantité zéro peut être validée et compte dans la progression.
4. Chaque validation est sauvegardée dans Google Sheets avant de continuer.
5. Une session interrompue peut être reprise sans perdre les données déjà confirmées.
6. Le catalogue peut être modifié dans Google Sheets sans toucher au code.
7. Le résumé consolide correctement les trois emplacements.
8. Un inventaire terminé ou abandonné est verrouillé.
9. L’abandon exige la saisie de `EFFACER` et conserve l’historique.
10. Les tests automatisés couvrent les règles critiques décrites ci-dessus.
