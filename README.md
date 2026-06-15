# Comptage d'inventaire — Spa le Finlandais

Application autonome de décompte, optimisée pour mobile. Aucune dépendance
à un autre outil : la liste des produits est intégrée dans `app.py`.

## Ce que ça fait

- Liste de produits organisée par catégories (pliables).
- Pour chaque produit : boutons ➖ / ➕ tactiles + champ de saisie directe.
- Total d'unités visible en haut (barre collante).
- Recherche pour filtrer rapidement.
- Bouton **Reset** pour tout remettre à zéro.
- Bouton **Envoyer par courriel** : ouvre l'app courriel pré-remplie vers
  `maximeleclair@spalefinlandais.com`, comptage groupé par catégorie.
- Bouton **CSV** pour télécharger le décompte.

## Installation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déploiement sur Streamlit Community Cloud

1. Pousser ce dossier dans un dépôt GitHub.
2. Aller sur https://share.streamlit.io , se connecter avec GitHub.
3. « New app » → choisir le dépôt, la branche, et `app.py`.
4. Déployer. Ajouter l'app à l'écran d'accueil du téléphone pour un accès rapide.

## Modifier la liste de produits

Tout est dans la variable `CATALOG` au début de `app.py` : une liste de
catégories, chacune avec ses produits. Ajouter, retirer ou renommer un produit
se fait directement là, puis `git push`.

## Note

Le décompte vit dans la session du navigateur. Un rafraîchissement de page
le remet à zéro — pensez à envoyer le courriel ou télécharger le CSV avant
de fermer.
