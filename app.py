"""
Tableau de bord d'inventaire - Spa le Finlandais
Audit hebdomadaire Zenoti + suivi entrepot Sortly.

Lancement local :  streamlit run app.py
"""

import io
import json
import unicodedata
import re
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Inventaire - Spa le Finlandais",
                   page_icon="🧖", layout="wide")

DATA_DIR = "data"
ZENOTI_CSV = f"{DATA_DIR}/zenoti_current_stock.csv"
SORTLY_CSV = f"{DATA_DIR}/sortly_export.csv"
LINKS_FILE = f"{DATA_DIR}/links.json"   # liens Sortly <-> Zenoti, sauvegardes
AUDIT_TEMPLATE = f"{DATA_DIR}/zenoti_audit_template.csv"  # gabarit d'import audit Zenoti

# Valeurs par defaut pour les produits boutique absents du gabarit Zenoti
DEFAULT_CATEGORY = "Boutique"
DEFAULT_SUBCATEGORY = "4040-00"

VENTE_CLIENT = "VENTE CLIENT"   # sous-dossier Sortly des produits revendables


# --------------------------------------------------------------------------
# Chargement des donnees
# --------------------------------------------------------------------------
def _norm(x: str) -> str:
    if not isinstance(x, str):
        return ""
    x = x.lower().strip()
    x = "".join(c for c in unicodedata.normalize("NFD", x)
                if unicodedata.category(c) != "Mn")
    x = re.sub(r"[^a-z0-9 ]", " ", x)
    return re.sub(r"\s+", " ", x).strip()


def _score(a: str, b: str) -> float:
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@st.cache_data
def load_zenoti(path: str) -> pd.DataFrame:
    z = pd.read_csv(path)
    z = z.rename(columns={
        "Product Code": "code",
        "Product Name": "name",
        "On-Hand Quantity": "onhand",
        "Avg Price (Perpetual)": "avgprice",
        "Stock Cost (Perpetual Average)": "stockcost",
    })
    z["code"] = z["code"].astype(str)
    z["onhand"] = pd.to_numeric(z["onhand"], errors="coerce").fillna(0).astype(int)
    z["avgprice"] = pd.to_numeric(z["avgprice"], errors="coerce").fillna(0.0)
    return z[["code", "name", "onhand", "avgprice"]]


@st.cache_data
def load_sortly(path: str):
    s = pd.read_csv(path)
    s["Entry Name"] = s["Entry Name"].astype(str).str.strip()
    s["Quantity"] = pd.to_numeric(s["Quantity"], errors="coerce").fillna(0.0)
    s["Min Level"] = pd.to_numeric(s["Min Level"], errors="coerce")  # NaN = pas de seuil

    vente = s[s["Subfolder-level3"] == VENTE_CLIENT].copy()
    ops = s[s["Subfolder-level3"] != VENTE_CLIENT].copy()

    vente_list = [{"name": r["Entry Name"],
                   "qty": float(r["Quantity"]),
                   "min": (None if pd.isna(r["Min Level"]) else float(r["Min Level"]))}
                  for _, r in vente.iterrows()]

    ops_list = [{"name": r["Entry Name"],
                 "cat": (r["Subfolder-level3"] if pd.notna(r["Subfolder-level3"]) else "Autre"),
                 "qty": float(r["Quantity"]),
                 "min": (None if pd.isna(r["Min Level"]) else float(r["Min Level"]))}
                for _, r in ops.iterrows()]
    return vente_list, ops_list


@st.cache_data
def load_audit_template(path: str) -> dict:
    """Charge le gabarit d'audit Zenoti. Retourne un dict
    code -> {category, subcategory, valueconsidered} pour reutiliser
    les vraies categories Zenoti dans l'export d'audit."""
    try:
        t = pd.read_csv(path)
    except FileNotFoundError:
        return {}
    meta = {}
    for _, r in t.iterrows():
        meta[str(r["Code"])] = {
            "category": r.get("Category", DEFAULT_CATEGORY),
            "subcategory": r.get("SubCategory", DEFAULT_SUBCATEGORY),
            "value": r.get("ValueConsidered", 0),
        }
    return meta


# Liens etablis manuellement (code Zenoti -> nom article Sortly « vente client »).
# Sert de base par defaut quand data/links.json n'existe pas encore.
CURATED_LINKS = {
    # produits Soja & Co.
    "5152": "Bain moussant", "5157": "Bruine ambiance",
    "111100000008": "BRUINE DOUCHE", "5153": "Gel douche",
    "5155": "Huile à massage", "5156": "Huile essentielle",
    "5158": "Savon en barre", "5151": "Savon main liquide",
    "5150": "Chandelle", "5154": "Diffuseur à roseaux",
    # divers
    "5204": "SAC DE SPORT (SAC REMPLIS DE SAC)", "5213": "TAPIS RUSSE",
    # maillots femme par taille
    "5128": "TAILLE 28", "5129": "TAILLE 30", "5131": "TAILLE 32",
    "5132": "TAILLE 34", "5124": "TAILLE 36", "5125": "TAILLE 38",
    "5133": "TAILLE 40", "5134": "TAILLE 42",
    # maillots homme S/M/L/XL (XSMALL Sortly laisse non lie)
    "5010": "SMALL", "5011": "MEDIUM", "5012": "LARGE", "5013": "XLARGE",
    # slides blanches (B) par pointure, ordre croissant de taille
    "5026": "B240 - 36-37", "5027": "B250 - 38-39", "5028": "B260 - 40-41",
    "5029": "B270 - 42-43", "5030": "B280 -44-45",
    # slides noires (N) par pointure
    "5031": "N240 - 36-37", "5032": "N250 - 38-39", "5033": "N260 - 40-41",
    "5034": "N270 - 42-43", "5035": "N280 - 44-45",
    # peignoir (taille 2; la taille 1 est a 0)
    "5201": "PEIGNOIR REVENTE (TAILLE 2)",
    # tuques revente par couleur
    "5207": "BEIGE", "5208": "BRUN", "5206": "KHAKI", "5210": "NOIR",
}


def auto_links(zdf: pd.DataFrame, vente_list: list, threshold: float = 0.6) -> dict:
    """Liens par defaut : la table manuelle d'abord, puis appariement par nom
    pour combler les trous restants."""
    link = {c: n for c, n in CURATED_LINKS.items()}
    used = {i for i, sp in enumerate(vente_list) if sp["name"] in link.values()}
    zcodes = set(zdf["code"].astype(str))
    for _, zp in zdf.iterrows():
        if zp["code"] in link:
            continue
        best, best_s = None, 0.0
        for i, sp in enumerate(vente_list):
            if i in used:
                continue
            sc = _score(zp["name"], sp["name"])
            if sc > best_s:
                best_s, best = sc, i
        if best is not None and best_s >= threshold:
            used.add(best)
            link[zp["code"]] = vente_list[best]["name"]
    # ne garde que des codes valides
    return {c: n for c, n in link.items() if c in zcodes}


def load_saved_links() -> dict:
    try:
        with open(LINKS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_links(link: dict) -> None:
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(link, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Initialisation de l'etat
# --------------------------------------------------------------------------
zdf = load_zenoti(ZENOTI_CSV)
vente_list, ops_list = load_sortly(SORTLY_CSV)
audit_meta = load_audit_template(AUDIT_TEMPLATE)
vente_names = [v["name"] for v in vente_list]
vente_by_name = {v["name"]: v for v in vente_list}

if "links" not in st.session_state:
    saved = load_saved_links()
    st.session_state.links = saved if saved else auto_links(zdf, vente_list)


def transfer_qty(code, onhand, audit_val, link) -> int:
    """A transferer = PAR (stock systeme) - audit, plafonne par le stock entrepot."""
    if audit_val is None:
        return 0
    so = vente_by_name.get(link.get(code))
    if not so:
        return 0
    need = max(0, onhand - audit_val)
    return int(min(need, int(so["qty"])))


# --------------------------------------------------------------------------
# En-tete
# --------------------------------------------------------------------------
st.title("Inventaire - Spa le Finlandais")
st.caption(f"Audit hebdomadaire · {date.today().isoformat()}")


# --------------------------------------------------------------------------
# Tableau 1 : produits revendables (audit spa + transfert)
# --------------------------------------------------------------------------
st.subheader("Produits revendables — audit spa & transfert")
st.caption("Saisissez le compte papier dans la colonne « Audit papier ». "
           "Laissez vide les produits non comptés.")

rows = []
for _, p in zdf.iterrows():
    link_name = st.session_state.links.get(p["code"], "")
    so = vente_by_name.get(link_name)
    rows.append({
        "Code": p["code"],
        "Produit (Zenoti)": p["name"],
        "Système": int(p["onhand"]),
        "Audit papier": None,
        "Coût/u": round(float(p["avgprice"]), 2),
        "Entrepôt (Sortly)": link_name,
        "Dispo entrepôt": (int(so["qty"]) if so else None),
    })
base = pd.DataFrame(rows)

edited = st.data_editor(
    base,
    key="audit_editor",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Code": st.column_config.TextColumn(disabled=True, width="small"),
        "Produit (Zenoti)": st.column_config.TextColumn(disabled=True),
        "Système": st.column_config.NumberColumn(disabled=True, width="small",
                                                 help="Stock système Zenoti"),
        "Audit papier": st.column_config.NumberColumn(
            min_value=0, step=1, width="small",
            help="Compte physique papier"),
        "Coût/u": st.column_config.NumberColumn(disabled=True, format="$%.2f",
                                                width="small"),
        "Entrepôt (Sortly)": st.column_config.SelectboxColumn(
            options=[""] + vente_names,
            help="Article Sortly « vente client » lié à ce produit"),
        "Dispo entrepôt": st.column_config.NumberColumn(disabled=True,
                                                        width="small"),
    },
)

# Recalcul a partir du tableau edite
edited = edited.copy()
edited["Écart"] = edited.apply(
    lambda r: (None if pd.isna(r["Audit papier"])
               else int(r["Audit papier"]) - int(r["Système"])), axis=1)
edited["Valeur (audit)"] = edited.apply(
    lambda r: round((int(r["Système"]) if pd.isna(r["Audit papier"])
                     else int(r["Audit papier"])) * float(r["Coût/u"]), 2), axis=1)

# Met a jour les liens choisis dans l'editeur
for _, r in edited.iterrows():
    chosen = r["Entrepôt (Sortly)"]
    if chosen:
        st.session_state.links[r["Code"]] = chosen
    else:
        st.session_state.links.pop(r["Code"], None)

edited["À transférer"] = edited.apply(
    lambda r: transfer_qty(r["Code"], int(r["Système"]),
                           (None if pd.isna(r["Audit papier"]) else int(r["Audit papier"])),
                           st.session_state.links), axis=1)

# Tuiles resume
perp_value = float(edited["Valeur (audit)"].sum())
variance_total = int(edited["Écart"].dropna().abs().sum())
transfer_total = int(edited["À transférer"].sum())
ops_low = sum(1 for o in ops_list if o["min"] is not None and o["qty"] <= o["min"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Valeur perpétuelle moy. (coût)", f"{perp_value:,.2f} $")
c2.metric("Écart d'audit (unités)", variance_total)
c3.metric("Unités à transférer", transfer_total)
c4.metric("Matériel d'op. à commander", ops_low)

with st.expander("Voir les écarts, valeurs et transferts calculés", expanded=False):
    st.dataframe(
        edited[["Code", "Produit (Zenoti)", "Système", "Audit papier",
                "Écart", "Valeur (audit)", "Entrepôt (Sortly)",
                "Dispo entrepôt", "À transférer"]],
        use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------
# Exports CSV
# --------------------------------------------------------------------------
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")  # BOM pour Excel/accents


today = date.today().isoformat()
e1, e2 = st.columns(2)

# Export audit au format gabarit Zenoti (8 colonnes), produits audites seulement.
# Le compte papier va dans StoreQuantity (reserve). FloorQuantity reste vide.
audited = edited[edited["Audit papier"].notna()]
audit_records = []
for _, r in audited.iterrows():
    code = str(r["Code"])
    meta = audit_meta.get(code, {})
    audit_records.append({
        "Code": code,
        "ProductName": r["Produit (Zenoti)"],
        "Category": meta.get("category", DEFAULT_CATEGORY),
        "SubCategory": meta.get("subcategory", DEFAULT_SUBCATEGORY),
        "StoreQuantity": int(r["Audit papier"]),
        "FloorQuantity": "",
        "Notes": "",
        "ValueConsidered": meta.get("value", 0),
    })
audit_export = pd.DataFrame(audit_records, columns=[
    "Code", "ProductName", "Category", "SubCategory",
    "StoreQuantity", "FloorQuantity", "Notes", "ValueConsidered"])

e1.download_button(
    "⬇ Import audit Zenoti (gabarit)",
    data=to_csv_bytes(audit_export),
    file_name=f"zenoti_audit_{today}.csv",
    mime="text/csv",
    disabled=audit_export.empty,
    use_container_width=True,
    help="Format gabarit Zenoti. Le compte papier est placé dans StoreQuantity. "
         "Seuls les produits audités sont inclus.")

transfer_export = edited[edited["À transférer"] > 0][
    ["Code", "Produit (Zenoti)", "Entrepôt (Sortly)", "À transférer"]].rename(
    columns={"Code": "Code Zenoti", "Produit (Zenoti)": "Produit",
             "Entrepôt (Sortly)": "Article Sortly",
             "À transférer": "Quantite a transferer"})
e2.download_button(
    "⬇ Bon de transfert (CSV)",
    data=to_csv_bytes(transfer_export),
    file_name=f"bon_transfert_{today}.csv",
    mime="text/csv",
    disabled=transfer_export.empty,
    use_container_width=True)

if st.button("💾 Sauvegarder les liens Sortly ↔ Zenoti"):
    save_links(st.session_state.links)
    st.success("Liens sauvegardés dans data/links.json")


# --------------------------------------------------------------------------
# Tableau 2 : materiel d'operation (suivi restock, jamais transfere)
# --------------------------------------------------------------------------
st.divider()
st.subheader("Matériel d'opération — suivi restock entrepôt")
st.caption("Bracelets, papeterie, emballage, certificats. Jamais transféré au spa. "
           "Alerte « à commander » quand le stock atteint le seuil min de Sortly.")

only_low = st.checkbox("Afficher seulement ce qui est sous le seuil")


def ops_status(o):
    if o["min"] is None:
        return "non suivi"
    return "à commander" if o["qty"] <= o["min"] else "ok"


ops_df = pd.DataFrame([{
    "Article (Sortly)": o["name"],
    "Catégorie": o["cat"],
    "Stock": round(o["qty"], 1),
    "Seuil min": (None if o["min"] is None else int(o["min"])),
    "Statut": ops_status(o),
} for o in ops_list])

if only_low:
    ops_df = ops_df[ops_df["Statut"] == "à commander"]

st.dataframe(ops_df, use_container_width=True, hide_index=True,
             column_config={
                 "Stock": st.column_config.NumberColumn(width="small"),
                 "Seuil min": st.column_config.NumberColumn(width="small"),
             })

restock_export = pd.DataFrame([{
    "Article Sortly": o["name"],
    "Categorie": o["cat"],
    "Stock actuel": round(o["qty"], 1),
    "Seuil min": int(o["min"]),
    "A commander (suggere)": max(1, int(-(-(o["min"] * 2 - o["qty"]) // 1))),
} for o in ops_list if o["min"] is not None and o["qty"] <= o["min"]])

st.download_button(
    "⬇ Liste d'achat fournisseur (CSV)",
    data=to_csv_bytes(restock_export),
    file_name=f"liste_achat_fournisseur_{today}.csv",
    mime="text/csv",
    disabled=restock_export.empty,
    use_container_width=True)
