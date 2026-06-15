"""
Comptage d'inventaire - Spa le Finlandais
Application autonome de decompte. Optimisee mobile.
Aucune dependance externe : la liste de produits est integree ci-dessous.

Lancement local :  streamlit run app.py
"""

import io
import urllib.parse
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Comptage · Spa le Finlandais",
                   page_icon="🧮", layout="centered")

DEST_EMAIL = "maximeleclair@spalefinlandais.com"

# Catalogue de comptage : (categorie, [noms de produits, ...])
CATALOG = [
    ("🧴 Produits spa & bien-être", [
        "Chandelles", "Diffuseur Roseau", "Savon liquide", "Gel douche",
        "Huile à massage", "Bain moussant", "Bruine d'ambiance",
        "Huile essentielle", "Savon en barre", "Bruine de douche",
    ]),
    ("🎁 Combos", [
        "Combo Gel douche (bain)", "Combo Chandelle (détente)", "Kit Pédicure",
    ]),
    ("👙 Maillots femme", [
        "Maillot Femme 28", "Maillot Femme 30", "Maillot Femme 32",
        "Maillot Femme 34", "Maillot Femme 36", "Maillot Femme 38",
        "Maillot Femme 40", "Maillot Femme 42",
    ]),
    ("🩳 Maillots homme", [
        "Maillot Homme Small", "Maillot Homme Médium",
        "Maillot Homme Large", "Maillot Homme Extra Large",
    ]),
    ("🖤 Slides noirs", [
        "Slide noir 36-37", "Slide noir 38-39", "Slide noir 40-41",
        "Slide noir 42-43", "Slide noir 44-45",
    ]),
    ("🤍 Slides blancs", [
        "Slide blanche 36-37", "Slide blanche 38-39", "Slide blanche 40-41",
        "Slide blanche 42-43", "Slide blanche 44-45",
    ]),
    ("🧢 Tuques", [
        "Tuque Kaki", "Tuque Marine", "Tuque Beige", "Tuque Noire",
        "Tuque brune", "Tuque noire pompon", "Tuque blanche pompon",
    ]),
    ("☕ Thé & accessoires", [
        "Peignoir de revente", "Thé Éclat Citron", "Thé Chai Camellia",
        "Thé Érable", "Thé Rooibos", "Thé Nuit Étoilé", "Tasse", "Filtres",
    ]),
]

ALL_PRODUCTS = [p for _, items in CATALOG for p in items]

# --------------------------------------------------------------------------
# Style mobile
# --------------------------------------------------------------------------
st.markdown("""
<style>
  /* compacter la page sur mobile */
  .block-container { padding-top: 1.2rem; padding-bottom: 5rem;
                     max-width: 640px; }
  /* gros boutons tactiles */
  div[data-testid="stButton"] button {
      height: 52px; font-size: 24px; font-weight: 700;
      border-radius: 14px; padding: 0;
  }
  /* champ nombre plus grand */
  div[data-testid="stNumberInput"] input { height: 44px; font-size: 18px;
      text-align: center; }
  /* titres de categorie */
  h3 { margin-top: 0.4rem !important; margin-bottom: 0.2rem !important; }
  /* barre total collante en haut */
  .total-bar {
      position: sticky; top: 0; z-index: 999;
      background: var(--background-color, #fff);
      padding: 10px 0; border-bottom: 1px solid rgba(128,128,128,0.2);
      margin-bottom: 8px;
  }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Etat
# --------------------------------------------------------------------------
if "counts" not in st.session_state:
    st.session_state.counts = {p: 0 for p in ALL_PRODUCTS}
else:
    for p in ALL_PRODUCTS:
        st.session_state.counts.setdefault(p, 0)


def bump(name, delta):
    st.session_state.counts[name] = max(0, st.session_state.counts.get(name, 0) + delta)


def set_count(name):
    val = st.session_state.get(f"in_{name}", 0)
    st.session_state.counts[name] = max(0, int(val or 0))


def reset_all():
    for p in ALL_PRODUCTS:
        st.session_state.counts[p] = 0


# --------------------------------------------------------------------------
# En-tete + total collant
# --------------------------------------------------------------------------
st.title("🧮 Comptage")
st.caption(f"Spa le Finlandais · {date.today().isoformat()}")

total_units = sum(st.session_state.counts.get(p, 0) for p in ALL_PRODUCTS)
counted = sum(1 for p in ALL_PRODUCTS if st.session_state.counts.get(p, 0) > 0)

st.markdown(
    f"<div class='total-bar'><b>{total_units}</b> unités · "
    f"{counted}/{len(ALL_PRODUCTS)} produits comptés</div>",
    unsafe_allow_html=True)

search = st.text_input("🔎 Rechercher", "", label_visibility="collapsed",
                       placeholder="🔎 Rechercher un produit…")
s = search.strip().lower()

# --------------------------------------------------------------------------
# Liste par categorie (pliable)
# --------------------------------------------------------------------------
for cat_name, items in CATALOG:
    visible = [p for p in items if not s or s in p.lower()]
    if not visible:
        continue
    # ouvert par defaut si recherche active, sinon plie
    with st.expander(f"{cat_name}  ·  {len(visible)}", expanded=bool(s)):
        for name in visible:
            cur = st.session_state.counts.get(name, 0)
            st.markdown(f"**{name}**")
            minus, val, plus, setc = st.columns([1.2, 1, 1.2, 1.6])
            with minus:
                st.button("➖", key=f"m_{name}", use_container_width=True,
                          on_click=bump, args=(name, -1))
            with val:
                st.markdown(
                    f"<div style='text-align:center;font-size:24px;"
                    f"font-weight:700;padding-top:8px'>{cur}</div>",
                    unsafe_allow_html=True)
            with plus:
                st.button("➕", key=f"p_{name}", use_container_width=True,
                          on_click=bump, args=(name, 1))
            with setc:
                st.number_input("n", min_value=0, step=1, value=cur,
                                key=f"in_{name}", label_visibility="collapsed",
                                on_change=set_count, args=(name,))
            st.divider()

# --------------------------------------------------------------------------
# Actions : reset + export
# --------------------------------------------------------------------------
st.write("")
if st.button("🔄 Reset (tout à zéro)", use_container_width=True):
    reset_all()
    st.rerun()

# Donnees d'export (tous les produits)
records = []
for cat_name, items in CATALOG:
    for name in items:
        records.append({"Categorie": cat_name, "Produit": name,
                        "Compte": st.session_state.counts.get(name, 0)})
export_df = pd.DataFrame(records)

# Corps courriel groupe par categorie
lines = ["Comptage d'inventaire - Spa le Finlandais",
         f"Date : {date.today().isoformat()}",
         f"Total unités : {total_units}", ""]
for cat_name, items in CATALOG:
    lines.append(cat_name)
    for name in items:
        lines.append(f"  {name} : {st.session_state.counts.get(name, 0)}")
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


st.link_button("✉️ Envoyer par courriel", mailto, use_container_width=True)
st.caption(f"Ouvre votre application courriel, pré-rempli vers {DEST_EMAIL}.")

st.download_button("⬇️ Télécharger le CSV",
                   data=to_csv_bytes(export_df),
                   file_name=f"comptage_{date.today().isoformat()}.csv",
                   mime="text/csv", use_container_width=True)
