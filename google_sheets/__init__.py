"""Fast Google Sheets adapter.

This package intentionally shadows the legacy ``google_sheets.py`` module.
It loads that implementation under a private name, then adds row caching and a
single-write count path without changing the public API used by ``app.py``.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "google_sheets.py"
_SPEC = importlib.util.spec_from_file_location("_legacy_google_sheets", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - deployment guard
    raise ImportError(f"Impossible de charger {_LEGACY_PATH}")
_legacy = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_legacy)

GoogleSheetsError = _legacy.GoogleSheetsError
GoogleSheetsConfigError = _legacy.GoogleSheetsConfigError
PRODUCT_HEADERS = _legacy.PRODUCT_HEADERS
SESSION_HEADERS = _legacy.SESSION_HEADERS
COUNT_HEADERS = _legacy.COUNT_HEADERS
CONFIG_HEADERS = _legacy.CONFIG_HEADERS
SHEET_HEADERS = _legacy.SHEET_HEADERS
DEFAULT_CONFIGURATION = _legacy.DEFAULT_CONFIGURATION
DEFAULT_PRODUCT_ROWS = _legacy.DEFAULT_PRODUCT_ROWS
Product = _legacy.Product
CatalogValidationError = _legacy.CatalogValidationError
LOCATIONS = _legacy.LOCATIONS


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).casefold()
    return "429" in message or "quota exceeded" in message


class GoogleSheetsStore(_legacy.GoogleSheetsStore):
    """Legacy-compatible store optimized for Streamlit reruns."""

    def __init__(self, spreadsheet: Any):
        super().__init__(spreadsheet)
        self._records_cache: dict[str, list[dict[str, Any]]] = {}
        self._schema_initialized = False

    def ensure_schema(
        self,
        default_products: Sequence[Mapping[str, Any]] = DEFAULT_PRODUCT_ROWS,
    ) -> None:
        if self._schema_initialized:
            return
        super().ensure_schema(default_products)
        self._schema_initialized = True

    def create_session(
        self,
        employee_name: str,
        products: Sequence[Product],
        locations: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        session = super().create_session(employee_name, products, locations)
        self._records_cache.pop("Sessions", None)
        self._records_cache.pop("Comptages", None)
        return session

    def _records(self, title: str) -> list[dict[str, Any]]:
        cached = self._records_cache.get(title)
        if cached is not None:
            return [dict(record) for record in cached]
        try:
            records = [dict(record) for record in self._worksheet(title).get_all_records()]
            self._records_cache[title] = records
            return [dict(record) for record in records]
        except GoogleSheetsError:
            raise
        except Exception as exc:
            if _is_quota_error(exc):
                raise GoogleSheetsError(
                    "Google Sheets reçoit trop de lectures. Attendez environ une minute, puis réessayez."
                ) from exc
            raise GoogleSheetsError(f"Impossible de lire l’onglet {title!r}.") from exc

    def _find_record_with_row(
        self,
        title: str,
        key: str,
        expected_value: str,
    ) -> tuple[dict[str, Any], int]:
        headers = SHEET_HEADERS[title]
        if key not in headers:
            raise GoogleSheetsConfigError(f"Colonne {key!r} absente de l’onglet {title!r}.")
        for index, record in enumerate(self._records(title)):
            if _legacy._string(record.get(key)) == expected_value:
                return dict(record), index + 2
        raise GoogleSheetsError(f"Enregistrement introuvable dans l’onglet {title!r}.")

    def _replace_cached_record(
        self,
        title: str,
        key: str,
        expected_value: str,
        record: Mapping[str, Any],
    ) -> None:
        cached = self._records_cache.get(title)
        if cached is None:
            return
        for index, existing in enumerate(cached):
            if _legacy._string(existing.get(key)) == expected_value:
                cached[index] = dict(record)
                return

    def _write_record(
        self,
        title: str,
        row_number: int,
        headers: Sequence[str],
        record: Mapping[str, Any],
    ) -> None:
        try:
            self._worksheet(title).update(
                values=[[record.get(header, "") for header in headers]],
                range_name=f"A{row_number}:{_legacy._column_letter(len(headers))}{row_number}",
                value_input_option="USER_ENTERED",
            )
        except Exception as exc:
            raise GoogleSheetsError(
                "Google Sheets n’a pas confirmé la sauvegarde. Réessayez sans quitter la page."
            ) from exc
        self._replace_cached_record(title, headers[0], _legacy._string(record.get(headers[0])), record)

    def save_count(
        self,
        session_id: str,
        count_id: str,
        quantity: int | str | None,
        *,
        verified: bool = True,
    ) -> dict[str, Any]:
        """Persist one count with one write and no provider reads."""
        session_record, _ = self._find_record_with_row("Sessions", "session_id", session_id)
        session = self._normalize_session(session_record)
        try:
            _legacy.assert_session_editable(_legacy._string(session.get("status")))
        except Exception as exc:
            raise GoogleSheetsError("Cette session est verrouillée et ne peut pas être modifiée.") from exc

        if verified:
            try:
                normalized_quantity: int | str = (
                    0 if quantity is None or _legacy._string(quantity) == "" else int(str(quantity).strip())
                )
            except (TypeError, ValueError) as exc:
                raise GoogleSheetsError("La quantité doit être un nombre entier.") from exc
            if normalized_quantity < 0:
                raise GoogleSheetsError("La quantité ne peut pas être négative.")
        else:
            normalized_quantity = ""

        record, row_number = self._find_record_with_row("Comptages", "count_id", count_id)
        if _legacy._string(record.get("session_id")) != session_id:
            raise GoogleSheetsError("Ce comptage n’appartient pas à la session active.")

        was_verified = _legacy.is_verified(record)
        previous_quantity = _legacy.quantity_value(record.get("quantity")) if was_verified else 0
        new_quantity = _legacy.quantity_value(normalized_quantity) if verified else 0
        now = _legacy.utc_now_iso()
        record.update(
            {
                "quantity": normalized_quantity,
                "verified": bool(verified),
                "verified_at": now if verified else "",
                "updated_at": now,
            }
        )

        self._write_record("Comptages", row_number, COUNT_HEADERS, record)

        session_record.update(
            {
                "verified_count": max(
                    0,
                    _legacy.quantity_value(session.get("verified_count"))
                    + int(bool(verified))
                    - int(was_verified),
                ),
                "total_units": max(
                    0,
                    _legacy.quantity_value(session.get("total_units"))
                    - previous_quantity
                    + new_quantity,
                ),
            }
        )
        self._replace_cached_record("Sessions", "session_id", session_id, session_record)
        return self._normalize_count(record)

    def complete_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        try:
            _legacy.assert_session_editable(_legacy._string(session.get("status")))
        except Exception as exc:
            raise GoogleSheetsError("Cette session est déjà verrouillée.") from exc
        counts = self.load_session_counts(session_id)
        if not _legacy.can_complete(counts, self.require_all_verified()):
            raise GoogleSheetsError("Des produits sont encore non vérifiés.")
        verified_count, total_count = _legacy.progress(counts)
        return self._update_session(
            session_id,
            status="COMPLETED",
            completed_at=_legacy.utc_now_iso(),
            verified_count=verified_count,
            total_count=total_count,
            total_units=sum(_legacy.quantity_value(row.get("quantity")) for row in counts),
        )

    def abandon_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        try:
            _legacy.assert_session_editable(_legacy._string(session.get("status")))
        except Exception as exc:
            raise GoogleSheetsError("Cette session ne peut pas être abandonnée.") from exc
        counts = self.load_session_counts(session_id)
        verified_count, total_count = _legacy.progress(counts)
        return self._update_session(
            session_id,
            status="ABANDONED",
            completed_at=_legacy.utc_now_iso(),
            verified_count=verified_count,
            total_count=total_count,
            total_units=sum(_legacy.quantity_value(row.get("quantity")) for row in counts),
        )


def from_streamlit_secrets(secrets: Mapping[str, Any]) -> GoogleSheetsStore:
    base_store = _legacy.from_streamlit_secrets(secrets)
    return GoogleSheetsStore(base_store.spreadsheet)
