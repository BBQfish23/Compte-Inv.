# Comptage d’inventaire — Spa le Finlandais

Application Streamlit mobile pour compter chaque produit séparément dans trois emplacements :

1. Lounge
2. Réception & Bureau
3. QBE

Google Sheets conserve le catalogue, les sessions, chaque quantité et l’historique. Une quantité de **0** peut être validée : elle est alors distinguée d’un produit qui n’a pas encore été vérifié.

## Fonctions principales

- Nom libre de l’employé au début du comptage.
- Reprise automatique de la dernière session non terminée.
- Comptage guidé, un produit et un emplacement à la fois.
- Boutons `−1`, `+1`, `+5` et saisie directe.
- Sauvegarde Google Sheets avant de passer au produit suivant.
- Vue de correction complète par emplacement.
- Totaux par emplacement et totaux consolidés par produit.
- Export CSV et résumé texte/courriel.
- Verrouillage d’un inventaire terminé et réouverture explicite.
- Abandon protégé par la saisie de `EFFACER`; l’historique est conservé avec le statut `ABANDONED`.

## Structure du Google Sheets

Au premier lancement, l’application crée les onglets manquants et ajoute les en-têtes.

### `Produits`

| Colonne | Description |
|---|---|
| `product_id` | Identifiant stable et unique |
| `product_name` | Nom affiché |
| `category` | Catégorie |
| `sort_order` | Ordre d’affichage |
| `active` | `true` ou `false` |

Si l’onglet est vide, le catalogue actuellement intégré à l’ancienne application est ajouté automatiquement. Après ce premier démarrage, cet onglet devient la source de vérité : ajouter, renommer, désactiver ou réordonner un produit ne demande aucune modification de code.

### `Sessions`

Une ligne par inventaire avec l’employé, les dates, le statut et les totaux.

### `Comptages`

Une ligne par combinaison session × produit × emplacement. Le champ `verified` permet de distinguer un zéro vérifié d’une ligne non comptée.

### `Configuration`

Format clé-valeur. Les clés initiales sont :

- `destination_email`
- `location_1 = Lounge`
- `location_2 = Réception & Bureau`
- `location_3 = QBE`
- `require_all_verified = true`

## Configuration Google Cloud

1. Créez ou choisissez un projet Google Cloud.
2. Activez **Google Sheets API** et **Google Drive API**.
3. Créez un compte de service et téléchargez sa clé JSON.
4. Créez un Google Sheets vide.
5. Partagez ce Google Sheets avec l’adresse `client_email` du compte de service en lui donnant le rôle **Éditeur**.
6. Copiez `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml` en local, ou ajoutez les mêmes valeurs dans les secrets de Streamlit Community Cloud.
7. Placez l’identifiant du fichier dans `google.spreadsheet_id`. Il s’agit de la partie située entre `/d/` et `/edit` dans l’adresse du Google Sheets.
8. Copiez les valeurs de la clé JSON dans la section `[gcp_service_account]`.

Ne publiez jamais `.streamlit/secrets.toml`. Il est ignoré par Git.

## Installation locale

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Déploiement Streamlit Community Cloud

1. Déployez `app.py` depuis ce dépôt.
2. Ouvrez **App settings → Secrets**.
3. Collez le contenu réel de votre `secrets.toml`.
4. Redémarrez l’application.
5. Au premier lancement, vérifiez que les quatre onglets ont été créés.

## Utilisation quotidienne

1. L’employé saisit son nom et commence au Lounge.
2. Il compte tous les produits du Lounge, puis Réception & Bureau, puis QBE.
3. Il valide chaque quantité, même lorsque la quantité est zéro.
4. L’application n’avance qu’après confirmation de la sauvegarde Google Sheets.
5. La vue **Corrections** permet de modifier une quantité ou de remettre une ligne à l’état non vérifié.
6. La vue **Résumé** affiche les totaux et permet de terminer l’inventaire.
7. Une session terminée est verrouillée, mais peut être rouverte explicitement.

## Tests

```bash
python -m pytest -q
python -m py_compile app.py app_helpers.py catalog.py inventory.py google_sheets.py
```

Les tests utilisent un faux Google Sheets en mémoire; aucune connexion Google n’est nécessaire.
