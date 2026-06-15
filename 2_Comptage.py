"""
Page de comptage tactile - Spa le Finlandais
Compteur +1 / -1 par produit, reset, et export courriel pre-rempli.
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


@st.cache_data
def load_products(path: str) -> pd.DataFrame:
    z = pd.read_csv(path)
    z = z.rename(columns={"Product Code": "code", "Product Name": "name"})
    z["code"] = z["code"].astype(str)
    return z[["code", "name"]]


products = load_products(ZENOTI_CSV)

# ---- etat des compteurs --------------------------------------------------
if "counts" not in st.session_state:
    st.session_state.counts = {c: 0 for c in products["code"]}


def bump(code, delta):
    st.session_state.counts[code] = max(0, st.session_state.counts.get(code, 0) + delta)


def set_count(code):
    val = st.session_state.get(f"in_{code}", 0)
    st.session_state.counts[code] = max(0, int(val or 0))


def reset_all():
    for c in products["code"]:
        st.session_state.counts[c] = 0


# ---- en-tete -------------------------------------------------------------
st.title("Comptage d'inventaire")
st.caption(f"Spa le Finlandais · {date.today().isoformat()}")

total_units = sum(st.session_state.counts.values())
counted_items = sum(1 for v in st.session_state.counts.values() if v > 0)
c1, c2, c3 = st.columns(3)
c1.metric("Unités comptées", total_units)
c2.metric("Produits avec compte", f"{counted_items} / {len(products)}")
with c3:
    st.write("")
    if st.button("🔄 Reset (tout à zéro)", use_container_width=True):
        reset_all()
        st.rerun()

search = st.text_input("Rechercher un produit", "")

st.divider()

# ---- liste de comptage ---------------------------------------------------
filtered = products
if search.strip():
    s = search.strip().lower()
    filtered = products[products["name"].str.lower().str.contains(s)
                        | products["code"].str.lower().str.contains(s)]

for _, p in filtered.iterrows():
    code, name = p["code"], p["name"]
    cur = st.session_state.counts.get(code, 0)

    name_col, minus_col, val_col, plus_col, set_col = st.columns([6, 1.4, 1.2, 1.4, 2])
    with name_col:
        st.markdown(f"**{name}**  \n<span style='color:gray;font-size:12px'>{code}</span>",
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

st.divider()

# ---- exports -------------------------------------------------------------
# Liste complete des 65 produits, peu importe le compte
export_df = products.copy()
export_df["Compte"] = export_df["code"].map(st.session_state.counts).fillna(0).astype(int)
export_df = export_df.rename(columns={"code": "Code", "name": "Produit"})

# corps texte pour le courriel
lines = [f"Comptage d'inventaire - Spa le Finlandais",
         f"Date : {date.today().isoformat()}",
         f"Total unités : {total_units}",
         "",
         "Code | Produit | Compte",
         "-----|---------|-------"]
for _, r in export_df.iterrows():
    lines.append(f"{r['Code']} | {r['Produit']} | {r['Compte']}")
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
    st.download_button("⬇ Télécharger le CSV (65 produits)",
                       data=to_csv_bytes(export_df),
                       file_name=f"comptage_{date.today().isoformat()}.csv",
                       mime="text/csv", use_container_width=True)

with st.expander("Aperçu de la liste complète", expanded=False):
    st.dataframe(export_df, use_container_width=True, hide_index=True)
