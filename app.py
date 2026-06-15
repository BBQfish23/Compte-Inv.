"""
Comptage d'inventaire - Spa le Finlandais
Application autonome de decompte. Optimisee mobile, disposition compacte 2 colonnes.
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
# Style mobile - disposition compacte
# --------------------------------------------------------------------------
st.markdown("""
<style>
  .block-container { padding-top: 1rem; padding-bottom: 5rem; max-width: 680px; }

  /* boutons +/- compacts mais tactiles */
  div[data-testid="stButton"] button {
      height: 40px; font-size: 20px; font-weight: 700;
      border-radius: 10px; padding: 0; min-width: 0;
  }
  /* champ nombre = la valeur centrale, bien visible et cliquable */
  div[data-testid="stNumberInput"] input {
      height: 40px; font-size: 20px; font-weight: 700; text-align: center;
      padding: 0;
  }
  /* cacher les petits +/- natifs du number_input pour gagner de la place */
  div[data-testid="stNumberInput"] button { display: none; }

  /* nom de produit compact */
  .prod-name { font-size: 13px; font-weight: 600; line-height: 1.15;
      height: 32px; overflow: hidden; margin-bottom: 2px; }
  .prod-name small { color: gray; font-weight: 400; }

  /* resserrer l'espacement vertical des colonnes */
  div[data-testid="stHorizontalBlock"] { gap: 0.4rem; margin-bottom: 0.3rem; }
  div[data-testid="column"] { padding: 0 0.15rem; }

  h3 { margin-top: 0.3rem !important; margin-bottom: 0.2rem !important;
       font-size: 17px !important; }

  .total-bar {
      position: sticky; top: 0; z-index: 999;
      background: var(--background-color, #fff);
      padding: 8px 0; border-bottom: 1px solid rgba(128,128,128,0.2);
      margin-bottom: 6px; font-size: 15px;
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
    new = max(0, st.session_state.counts.get(name, 0) + delta)
    st.session_state.counts[name] = new
    st.session_state[f"in_{name}"] = new   # garde le champ affiche synchronise


def set_count(name):
    val = st.session_state.get(f"in_{name}", 0)
    st.session_state.counts[name] = max(0, int(val or 0))


def reset_all():
    for p in ALL_PRODUCTS:
        st.session_state.counts[p] = 0
        st.session_state[f"in_{p}"] = 0


# --------------------------------------------------------------------------
# En-tete + total collant
# --------------------------------------------------------------------------
st.title("🧮 Comptage")
st.caption(f"Spa le Finlandais · {date.today().isoformat()}")

total_units = sum(st.session_state.counts.get(p, 0) for p in ALL_PRODUCTS)
counted = sum(1 for p in ALL_PRODUCTS if st.session_state.counts.get(p, 0) > 0)

st.markdown(
    f"<div class='total-bar'><b>{total_units}</b> unités · "
    f"{counted}/{len(ALL_PRODUCTS)} comptés</div>",
    unsafe_allow_html=True)

search = st.text_input("🔎 Rechercher", "", label_visibility="collapsed",
                       placeholder="🔎 Rechercher un produit…")
s = search.strip().lower()


# --------------------------------------------------------------------------
# Bloc produit (un quart de ligne : nom + [- valeur +])
# --------------------------------------------------------------------------
def product_block(name):
    key = f"in_{name}"
    if key not in st.session_state:
        st.session_state[key] = st.session_state.counts.get(name, 0)
    st.markdown(f"<div class='prod-name'>{name}</div>", unsafe_allow_html=True)
    bminus, bval, bplus = st.columns([1, 1.3, 1])
    with bminus:
        st.button("➖", key=f"m_{name}", use_container_width=True,
                  on_click=bump, args=(name, -1))
    with bval:
        st.number_input("n", min_value=0, step=1,
                        key=key, label_visibility="collapsed",
                        on_change=set_count, args=(name,))
    with bplus:
        st.button("➕", key=f"p_{name}", use_container_width=True,
                  on_click=bump, args=(name, 1))


# --------------------------------------------------------------------------
# Liste par categorie (pliable), 2 produits de large
# --------------------------------------------------------------------------
for cat_name, items in CATALOG:
    visible = [p for p in items if not s or s in p.lower()]
    if not visible:
        continue
    with st.expander(f"{cat_name}  ·  {len(visible)}", expanded=bool(s)):
        # rendre les produits par paires (2 colonnes)
        for i in range(0, len(visible), 2):
            left, right = st.columns(2)
            with left:
                product_block(visible[i])
            with right:
                if i + 1 < len(visible):
                    product_block(visible[i + 1])

# --------------------------------------------------------------------------
# Actions : reset + export
# --------------------------------------------------------------------------
st.write("")
if st.button("🔄 Reset (tout à zéro)", use_container_width=True):
    reset_all()
    st.rerun()

records = []
for cat_name, items in CATALOG:
    for name in items:
        records.append({"Categorie": cat_name, "Produit": name,
                        "Compte": st.session_state.counts.get(name, 0)})
export_df = pd.DataFrame(records)

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
