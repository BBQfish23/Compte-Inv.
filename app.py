"""Mobile inventory counter backed by Google Sheets."""
from __future__ import annotations

import urllib.parse
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from app_helpers import build_csv_bytes, build_summary_text, normalize_employee_name
from catalog import CatalogValidationError
from google_sheets import GoogleSheetsConfigError, GoogleSheetsError, GoogleSheetsStore, from_streamlit_secrets
from inventory import LOCATIONS, can_complete, is_verified, next_unverified_index, progress, quantity_value, totals_by_location

st.set_page_config(page_title="Comptage · Spa le Finlandais", page_icon="🧮", layout="centered")


@st.cache_resource
def get_store() -> GoogleSheetsStore:
    return from_streamlit_secrets(st.secrets)


def setup_page() -> None:
    st.markdown("""
    <style>
    .block-container{max-width:760px;padding-top:1rem;padding-bottom:5rem}
    div[data-testid="stButton"] button{min-height:46px;font-weight:700;border-radius:11px}
    div[data-testid="stNumberInput"] input{font-size:22px;font-weight:700;text-align:center}
    .card{border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:1rem;margin:.5rem 0 1rem}
    .place{font-size:1.15rem;font-weight:800}.product{font-size:1.5rem;font-weight:800;line-height:1.2}
    </style>""", unsafe_allow_html=True)
    st.title("🧮 Comptage d’inventaire")
    st.caption("Spa le Finlandais · sauvegarde automatique dans Google Sheets")
    if message := st.session_state.pop("flash", ""):
        st.success(message)


def clear_session() -> None:
    st.session_state.pop("active_session_id", None)
    st.session_state.pop("count_index", None)
    for key in list(st.session_state):
        if key.startswith(("guided_quantity_", "correction_quantity_")):
            del st.session_state[key]


def abandon_panel(store: GoogleSheetsStore, session: dict[str, Any], prefix: str) -> None:
    with st.expander("Zone de danger — abandonner cette session"):
        st.caption("L’historique sera conservé avec le statut ABANDONED.")
        text = st.text_input("Écris EFFACER", key=f"{prefix}_erase")
        confirm = st.checkbox("Je confirme l’abandon", key=f"{prefix}_confirm")
        if st.button("Abandonner", disabled=text != "EFFACER" or not confirm,
                     key=f"{prefix}_abandon", use_container_width=True):
            try:
                store.abandon_session(session["session_id"])
            except GoogleSheetsError as exc:
                st.error(str(exc)); return
            clear_session(); st.session_state.flash = "Session abandonnée; historique conservé."; st.rerun()


def start_screen(store: GoogleSheetsStore, products: list[Any]) -> None:
    active = store.find_active_session()
    if active:
        verified, total = int(active.get("verified_count", 0)), int(active.get("total_count", 0))
        st.warning("Un inventaire non terminé existe déjà.")
        st.write(f"**Employé :** {active.get('employee_name', '')}")
        st.write(f"**Début :** {active.get('started_at', '')}")
        st.progress(verified / total if total else 0, text=f"{verified}/{total} vérifiés")
        if st.button("Reprendre cet inventaire", type="primary", use_container_width=True):
            counts = store.load_session_counts(active["session_id"])
            st.session_state.active_session_id = active["session_id"]
            st.session_state.count_index = next_unverified_index(counts) or 0
            st.rerun()
        abandon_panel(store, active, "start")
        return

    st.subheader("Commencer un nouvel inventaire")
    st.caption(f"{len(products)} produits × 3 emplacements = {len(products) * 3} validations")
    with st.form("new_session"):
        name = st.text_input("Nom de l’employé", placeholder="Prénom et nom")
        submitted = st.form_submit_button("Commencer au Lounge", type="primary", use_container_width=True)
    if submitted:
        name = normalize_employee_name(name)
        if not name:
            st.error("Entre ton nom avant de commencer."); return
        try:
            session = store.create_session(name, products)
        except GoogleSheetsError as exc:
            st.error(str(exc)); return
        st.session_state.active_session_id = session["session_id"]
        st.session_state.count_index = 0
        st.session_state.flash = "Session créée dans Google Sheets."
        st.rerun()


def adjust(key: str, delta: int) -> None:
    st.session_state[key] = max(0, quantity_value(st.session_state.get(key, 0)) + delta)


def guided_view(store: GoogleSheetsStore, session: dict[str, Any], counts: list[dict[str, Any]]) -> None:
    if not counts:
        st.error("Aucune ligne de comptage dans cette session."); return
    index = max(0, min(int(st.session_state.get("count_index", 0)), len(counts) - 1))
    st.session_state.count_index = index
    row = counts[index]
    st.markdown(f"<div class='card'><div class='place'>📍 {row['location']}</div>"
                f"<div class='product'>{row['product_name_snapshot']}</div>"
                f"<div>{row.get('category_snapshot','')}</div></div>", unsafe_allow_html=True)
    st.caption(f"Élément {index + 1} sur {len(counts)}")
    key = f"guided_quantity_{row['count_id']}"
    st.session_state.setdefault(key, quantity_value(row.get("quantity")))
    st.number_input("Quantité", min_value=0, step=1, key=key)
    for column, label, delta in zip(st.columns(3), ("−1", "+1", "+5"), (-1, 1, 5)):
        column.button(label, key=f"{label}_{row['count_id']}", on_click=adjust,
                      args=(key, delta), use_container_width=True)
    previous, save = st.columns([1, 2])
    if previous.button("← Précédent", disabled=index == 0, use_container_width=True,
                       key=f"prev_{row['count_id']}"):
        st.session_state.count_index = index - 1; st.rerun()
    label = "Mettre à jour et suivant" if is_verified(row) else "Valider et suivant"
    if save.button(label, type="primary", use_container_width=True, key=f"save_{row['count_id']}"):
        try:
            store.save_count(session["session_id"], row["count_id"], st.session_state[key])
        except GoogleSheetsError as exc:
            st.error(str(exc)); st.warning("La page reste ici. Appuie de nouveau pour réessayer."); return
        refreshed = store.load_session_counts(session["session_id"])
        nxt = next_unverified_index(refreshed, index + 1)
        st.session_state.count_index = index if nxt is None else nxt
        st.session_state.flash = f"{row['product_name_snapshot']} — {row['location']} sauvegardé."
        st.rerun()
    if is_verified(row):
        st.success(f"Déjà vérifié : {quantity_value(row.get('quantity'))}")
    if all(is_verified(item) for item in counts):
        st.info("Tous les éléments sont vérifiés. Ouvre Résumé pour terminer.")


def corrections_view(store: GoogleSheetsStore, session: dict[str, Any], counts: list[dict[str, Any]]) -> None:
    st.caption("Chaque correction est sauvegardée immédiatement.")
    for location in LOCATIONS:
        rows = [row for row in counts if row["location"] == location]
        with st.expander(f"{location} · {sum(is_verified(r) for r in rows)}/{len(rows)} vérifiés"):
            for row in rows:
                with st.container(border=True):
                    st.write(f"**{row['product_name_snapshot']}**")
                    st.caption(row.get("category_snapshot", ""))
                    key = f"correction_quantity_{row['count_id']}"
                    st.session_state.setdefault(key, quantity_value(row.get("quantity")))
                    quantity, action = st.columns([2, 1])
                    quantity.number_input("Quantité", min_value=0, step=1, key=key, label_visibility="collapsed")
                    if action.button("Sauvegarder", key=f"fix_{row['count_id']}", use_container_width=True):
                        try:
                            store.save_count(session["session_id"], row["count_id"], st.session_state[key])
                        except GoogleSheetsError as exc:
                            st.error(str(exc)); return
                        st.session_state.flash = "Correction sauvegardée."; st.rerun()
                    if is_verified(row):
                        st.caption(f"✅ Vérifié · {row.get('updated_at','')}")
                        if st.button("Remettre à non vérifié", key=f"unverify_{row['count_id']}", use_container_width=True):
                            try:
                                store.save_count(session["session_id"], row["count_id"], None, verified=False)
                            except GoogleSheetsError as exc:
                                st.error(str(exc)); return
                            st.session_state.pop(key, None); st.session_state.flash = "Élément remis à non vérifié."; st.rerun()
                    else:
                        st.caption("⬜ Non vérifié")


def summary_table(counts: list[dict[str, Any]]) -> pd.DataFrame:
    products: dict[str, dict[str, Any]] = {}
    for row in counts:
        item = products.setdefault(row["product_id"], {
            "Produit": row["product_name_snapshot"], "Catégorie": row.get("category_snapshot", ""),
            **{location: 0 for location in LOCATIONS}, "Total": 0,
        })
        amount = quantity_value(row.get("quantity")); item[row["location"]] = amount; item["Total"] += amount
    return pd.DataFrame(products.values())


def summary_view(store: GoogleSheetsStore, session: dict[str, Any], counts: list[dict[str, Any]],
                 configuration: dict[str, str], allow_completion: bool = True) -> None:
    verified, total = progress(counts); location_totals = totals_by_location(counts)
    metrics = st.columns(4); metrics[0].metric("Vérifiés", f"{verified}/{total}")
    for i, location in enumerate(LOCATIONS, 1): metrics[i].metric(location, location_totals.get(location, 0))
    st.metric("Total général", sum(location_totals.values()))
    missing = [row for row in counts if not is_verified(row)]
    if missing:
        st.warning(f"{len(missing)} éléments non vérifiés.")
        with st.expander("Voir les éléments manquants"):
            for row in missing: st.write(f"• {row['location']} — {row['product_name_snapshot']}")
    else:
        st.success("Tout est vérifié, y compris les quantités zéro.")
    table = summary_table(counts)
    if not table.empty: st.dataframe(table, hide_index=True, use_container_width=True)
    st.download_button("⬇️ Télécharger le CSV", build_csv_bytes(counts),
                       file_name=f"comptage_{date.today().isoformat()}_{session['session_id'][:8]}.csv",
                       mime="text/csv", use_container_width=True)
    text = build_summary_text(session, counts); email = configuration.get("destination_email", "").strip()
    if email:
        subject = urllib.parse.quote(f"Comptage inventaire - {date.today().isoformat()}")
        st.link_button("✉️ Préparer le courriel", f"mailto:{email}?subject={subject}&body={urllib.parse.quote(text)}",
                       use_container_width=True)
    with st.expander("Résumé texte"): st.code(text, language=None)
    if allow_completion:
        allowed = can_complete(counts, store.require_all_verified())
        if st.button("Terminer et verrouiller l’inventaire", type="primary", disabled=not allowed,
                     use_container_width=True):
            try:
                store.complete_session(session["session_id"])
            except GoogleSheetsError as exc:
                st.error(str(exc)); return
            st.session_state.flash = "Inventaire terminé et verrouillé."; st.rerun()


def completed_view(store: GoogleSheetsStore, session: dict[str, Any], counts: list[dict[str, Any]],
                   configuration: dict[str, str]) -> None:
    st.success("Inventaire terminé et verrouillé.")
    summary_view(store, session, counts, configuration, allow_completion=False)
    with st.expander("Rouvrir cette session"):
        confirm = st.checkbox("Je confirme la réouverture")
        if st.button("Rouvrir", disabled=not confirm, use_container_width=True):
            try:
                store.reopen_session(session["session_id"])
            except GoogleSheetsError as exc:
                st.error(str(exc)); return
            st.session_state.flash = "Session rouverte."; st.rerun()
    if st.button("Retour à l’accueil", use_container_width=True): clear_session(); st.rerun()


def active_screen(store: GoogleSheetsStore, session: dict[str, Any], configuration: dict[str, str]) -> None:
    counts = store.load_session_counts(session["session_id"])
    st.write(f"**Employé :** {session.get('employee_name','')}")
    verified, total = progress(counts); st.progress(verified / total if total else 0, text=f"{verified}/{total} vérifiés")
    if session["status"] == "COMPLETED": completed_view(store, session, counts, configuration); return
    if session["status"] == "ABANDONED":
        st.warning("Session abandonnée et verrouillée.")
        if st.button("Retour à l’accueil", use_container_width=True): clear_session(); st.rerun()
        return
    guided, corrections, summary = st.tabs(["Comptage guidé", "Corrections", "Résumé"])
    with guided: guided_view(store, session, counts)
    with corrections: corrections_view(store, session, counts)
    with summary: summary_view(store, session, counts, configuration)
    abandon_panel(store, session, "active")


def main() -> None:
    setup_page()
    try:
        store = get_store()
        if not st.session_state.get("schema_ready"):
            store.ensure_schema(); st.session_state.schema_ready = True
        products, configuration = store.load_products(), store.load_configuration()
    except (GoogleSheetsConfigError, GoogleSheetsError, CatalogValidationError) as exc:
        st.error(str(exc))
        with st.expander("Configuration requise"):
            st.write("Configure `.streamlit/secrets.toml`, puis partage le Google Sheets avec le compte de service.")
        return
    session_id = st.session_state.get("active_session_id")
    if not session_id: start_screen(store, products); return
    try:
        active_screen(store, store.get_session(session_id), configuration)
    except GoogleSheetsError as exc:
        st.error(str(exc))
        if st.button("Retour à l’accueil", use_container_width=True): clear_session(); st.rerun()


if __name__ == "__main__":
    main()
