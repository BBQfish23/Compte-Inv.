# Inventaire — Spa le Finlandais

Tableau de bord d'inventaire hebdomadaire. Réunit l'audit du stock spa (Zenoti) et
le suivi de l'entrepôt (Sortly) en une seule interface.

## Ce que ça fait

**Produits revendables (audit spa + transfert)**
- Saisie du compte papier hebdomadaire dans la colonne « Audit papier »
- Calcul automatique de l'écart vs le stock système Zenoti
- Valeur perpétuelle moyenne de l'inventaire au coût
- Suggestion de transfert entrepôt → spa (plafonnée par le stock disponible en entrepôt)
- Export d'un CSV d'import d'audit pour Zenoti
- Export d'un bon de transfert

**Matériel d'opération (suivi restock)**
- Bracelets, papeterie, emballage, certificats — surveillés mais jamais transférés au spa
- Alerte « à commander » quand le stock atteint le seuil min de Sortly
- Export d'une liste d'achat fournisseur

## Page de comptage tactile

L'app a une seconde page, **Comptage** (dans la barre latérale), conçue pour
compter rapidement sur tablette ou téléphone :

- Chaque produit a un bouton ➖ / ➕ et un champ de saisie directe.
- Compteurs de total et de produits comptés en haut.
- Bouton **Reset** pour tout remettre à zéro.
- Bouton **Envoyer par courriel** : ouvre l'app courriel pré-remplie vers
  `maximeleclair@spalefinlandais.com` avec la liste complète des 65 produits.
- Bouton **CSV** en filet de sécurité (si le client courriel tronque le corps).

> Note : l'envoi courriel utilise un lien `mailto:` qui ouvre votre application
> courriel — il n'envoie pas automatiquement. C'est voulu : aucune configuration
> de serveur d'envoi n'est requise.

## Installation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'app s'ouvre dans le navigateur à `http://localhost:8501`.

## Déploiement sur Streamlit Community Cloud

1. Pousser ce dossier dans un dépôt GitHub.
2. Aller sur https://share.streamlit.io , se connecter avec GitHub.
3. « New app » → choisir le dépôt, la branche, et `app.py` comme fichier principal.
4. Déployer. L'app se met à jour à chaque `git push`.

## Mettre à jour les données

Les deux fichiers dans `data/` sont les exports bruts :

| Fichier | Source | Comment l'obtenir |
|---------|--------|-------------------|
| `data/zenoti_current_stock.csv` | Zenoti | Rapport « Current Stock » exporté en CSV |
| `data/sortly_export.csv` | Sortly | Export complet de l'inventaire en CSV |
| `data/zenoti_audit_template.csv` | Zenoti | Gabarit d'audit exporté (fournit les Category / SubCategory / ValueConsidered) |

Pour rafraîchir : remplacer ces deux fichiers par les exports récents (mêmes noms),
puis `git push`. L'app relit les colonnes automatiquement.

### Colonnes attendues

**Zenoti** : `Product Code`, `Product Name`, `On-Hand Quantity`, `Avg Price (Perpetual)`

**Sortly** : `Entry Name`, `Quantity`, `Min Level`, `Subfolder-level3`
(le sous-dossier `VENTE CLIENT` distingue les produits revendables du matériel d'opération)

## Liens Sortly ↔ Zenoti

Les deux systèmes n'ont pas de code produit commun, donc l'app apparie les produits
par nom au premier lancement (~10 sur 65 automatiquement). Les autres se règlent à la
main via le menu déroulant « Entrepôt (Sortly) » dans le tableau.

Le bouton **« Sauvegarder les liens »** écrit `data/links.json`. Une fois ce fichier
commité dans GitHub, les liens persistent d'une semaine à l'autre.

> Le vrai correctif à long terme : utiliser le **même code produit** dans Zenoti et
> Sortly, ce qui rendrait l'appariement automatique et permanent.

## Export d'audit Zenoti

Le bouton « Import audit Zenoti » génère un CSV au format gabarit exact de Zenoti
(`Code, ProductName, Category, SubCategory, StoreQuantity, FloorQuantity, Notes,
ValueConsidered`). Le compte papier saisi est placé dans `StoreQuantity` (réserve);
`FloorQuantity` reste vide. Seuls les produits réellement audités (compte saisi)
sont inclus. Les Category / SubCategory / ValueConsidered sont repris du gabarit
Zenoti quand le produit y figure, sinon `Boutique` / `4040-00` par défaut.

## Le seuil de réappro

Le seuil vient directement de la colonne `Min Level` de Sortly. Un article sans
`Min Level` est marqué « non suivi ». Pour qu'un article déclenche une alerte, lui
donner un seuil dans Sortly à la source.
