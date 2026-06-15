"""
Page de comptage tactile - Spa le Finlandais
Liste organisee par categories, noms simplifies a l'affichage,
code Zenoti conserve pour l'export. Compteur +1 / -1, reset, export courriel.
"""

import io
import urllib.parse
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Comptage - Spa le Finlandais",
                   page_icon="🧮", layout="wide")

DATA_DIR = "data"
ZENOTI_CSV = f"{DATA_DIR}/zenoti_current_stock.csv"
DEST_EMAIL = "maximeleclair@spalefinlandais.com"

# Catalogue de comptage : (categorie, [(nom affiche, code Zenoti), ...])
# Le nom affiche est simplifie; le code Zenoti est conserve pour l'export.
CATALOG = [
    ('🧴 Produits spa & bien-être', [
        ('Chandelles', '5150'),
        ('Diffuseur Roseau', '5154'),
        ('Savon liquide', '5151'),
        ('Gel douche', '5153'),
        ('Huile à massage', '5155'),
        ('Bain moussant', '5152'),
        ("Bruine d'ambiance", '5157'),
        ('Huile essentielle', '5156'),
        ('Savon en barre', '5158'),
        ('Bruine de douche', '111100000008'),
    ]),
    ('🎁 Combos', [
        ('Combo Gel douche (bain)', '111100000006'),
        ('Combo Chandelle (détente)', '111100000007'),
        ('Kit Pédicure', '111100000020'),
    ]),
    ('👙 Maillots femme', [
        ('Maillot Femme 28', '5128'),
        ('Maillot Femme 30', '5129'),
        ('Maillot Femme 32', '5131'),
        ('Maillot Femme 34', '5132'),
        ('Maillot Femme 36', '5124'),
        ('Maillot Femme 38', '5125'),
        ('Maillot Femme 40', '5133'),
        ('Maillot Femme 42', '5134'),
    ]),
    ('🩳 Maillots homme', [
        ('Maillot Homme Small', '5010'),
        ('Maillot Homme Médium', '5011'),
        ('Maillot Homme Large', '5012'),
        ('Maillot Homme Extra Large', '5013'),
    ]),
    ('🖤 Slides noirs', [
        ('Slide noir 36-37', '5031'),
        ('Slide noir 38-39', '5032'),
        ('Slide noir 40-41', '5033'),
        ('Slide noir 42-43', '5034'),
        ('Slide noir 44-45', '5035'),
    ]),
    ('🤍 Slides blancs', [
        ('Slide blanche 36-37', '5026'),
        ('Slide blanche 38-39', '5027'),
        ('Slide blanche 40-41', '5028'),
        ('Slide blanche 42-43', '5029'),
        ('Slide blanche 44-45', '5030'),
    ]),
    ('🧢 Tuques', [
        ('Tuque Kaki', '5206'),
        ('Tuque Marine', '5211'),
        ('Tuque Beige', '5207'),
        ('Tuque Noire', '5210'),
        ('Tuque brune', '5208'),
        ('Tuque noire pompon', '5202'),
        ('Tuque blanche pompon', '5203'),
    ]),
    ('☕ Thé & accessoires', [
        ('Peignoir de revente', '5201'),
        ('Thé Éclat Citron', '841453001462'),
        ('Thé Chai Camellia', '841453000182'),
        ('Thé Érable', '841453009123'),
        ('Thé Rooibos', '841453000175'),
        ('Thé Nuit Étoilé', '111100000015'),
        ('Tasse', '111100000018'),
        ('Filtres', '841453001301'),
    ]),
]

# Liste a plat des codes utilises, dans l'ordre du catalogue
CATALOG_CODES = [code for _, items in CATALOG for _, code in items]
DISPLAY_NAME = {code: disp for _, items in CATALOG for disp, code in items}


@st.cache_data
def zenoti_names(path: str) -> dict:
    z = pd.read_csv(path)
    z["Product Code"] = z["Product Code"].astype(str)
    return dict(zip(z["Product Code"], z["Product Name"]))


znames = zenoti_names(ZENOTI_CSV)

# ---- etat des compteurs --------------------------------------------------
if "counts" not in st.session_state:
    st.session_state.counts = {c: 0 for c in CATALOG_CODES}
else:
    for c in CATALOG_CODES:
        st.session_state.counts.setdefault(c, 0)


def bump(code, delta):
    st.session_state.counts[code] = max(0, st.session_state.counts.get(code, 0) + delta)


def set_count(code):
    val = st.session_state.get(f"in_{code}", 0)
    st.session_state.counts[code] = max(0, int(val or 0))


def reset_all():
    for c in CATALOG_CODES:
        st.session_state.counts[c] = 0


# ---- en-tete -------------------------------------------------------------
st.title("Comptage d'inventaire")
st.caption(f"Spa le Finlandais · {date.today().isoformat()}")

total_units = sum(st.session_state.counts.get(c, 0) for c in CATALOG_CODES)
counted_items = sum(1 for c in CATALOG_CODES if st.session_state.counts.get(c, 0) > 0)

c1, c2, c3 = st.columns(3)
c1.metric("Unités comptées", total_units)
c2.metric("Produits avec compte", f"{counted_items} / {len(CATALOG_CODES)}")
with c3:
    st.write("")
    if st.button("🔄 Reset (tout à zéro)", use_container_width=True):
        reset_all()
        st.rerun()

search = st.text_input("Rechercher un produit", "")
s = search.strip().lower()

st.divider()

# ---- liste de comptage par categorie ------------------------------------
for cat_name, items in CATALOG:
    visible = [(disp, code) for disp, code in items
               if not s or s in disp.lower() or s in code.lower()]
    if not visible:
        continue
    st.markdown(f"### {cat_name}")
    for disp, code in visible:
        cur = st.session_state.counts.get(code, 0)
        name_col, minus_col, val_col, plus_col, set_col = st.columns([6, 1.4, 1.2, 1.4, 2])
        with name_col:
            st.markdown(f"**{disp}**  \n<span style='color:gray;font-size:12px'>{code}</span>",
                        unsafe_allow_html=True)
        with minus_col:
            st.button("➖", key=f"m_{code}", use_container_width=True,
                      on_click=bump, args=(code, -1))
        with val_col:
            st.markdown(f"<div style='text-align:center;font-size:22px;"
                        f"font-weight:600;padding-top:4px'>{cur}</div>",
                        unsafe_allow_html=True)
        with plus_col:
            st.button("➕", key=f"p_{code}", use_container_width=True,
                      on_click=bump, args=(code, 1))
        with set_col:
            st.number_input("saisie", min_value=0, step=1, value=cur,
                            key=f"in_{code}", label_visibility="collapsed",
                            on_change=set_count, args=(code,))
    st.write("")

st.divider()

# ---- exports -------------------------------------------------------------
# Liste complete (tous les produits du catalogue), avec categorie + nom Zenoti reel
records = []
for cat_name, items in CATALOG:
    for disp, code in items:
        records.append({
            "Categorie": cat_name,
            "Code": code,
            "Produit": disp,
            "Nom Zenoti": znames.get(code, ""),
            "Compte": st.session_state.counts.get(code, 0),
        })
export_df = pd.DataFrame(records)

# corps texte pour le courriel, groupe par categorie
lines = ["Comptage d'inventaire - Spa le Finlandais",
         f"Date : {date.today().isoformat()}",
         f"Total unités : {total_units}",
         ""]
for cat_name, items in CATALOG:
    lines.append(cat_name)
    for disp, code in items:
        lines.append(f"  {disp} : {st.session_state.counts.get(code, 0)}")
    lines.append("")
body_text = "\n".join(lines)

subject = f"Comptage inventaire - {date.today().isoformat()}"
mailto = (f"mailto:{DEST_EMAIL}"
          f"?subject={urllib.parse.quote(subject)}"
          f"&body={urllib.parse.quote(body_text)}")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


x1, x2 = st.columns(2)
with x1:
    st.link_button("✉ Envoyer par courriel (ouvre l'app courriel)",
                   mailto, use_container_width=True)
    st.caption(f"Pré-rempli vers {DEST_EMAIL}. Si la liste est tronquée par "
               "votre client courriel, utilisez le CSV à droite.")
with x2:
    st.download_button("⬇ Télécharger le CSV",
                       data=to_csv_bytes(export_df),
                       file_name=f"comptage_{date.today().isoformat()}.csv",
                       mime="text/csv", use_container_width=True)

with st.expander("Aperçu de la liste complète", expanded=False):
    st.dataframe(export_df, use_container_width=True, hide_index=True)
