"""Google Sheets persistence for the inventory application.

The module deliberately imports Google client libraries only when authenticating,
so the business and persistence tests can run with an injected fake spreadsheet.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

from catalog import (
    DEFAULT_PRODUCT_ROWS,
    CatalogValidationError,
    Product,
    parse_bool,
    parse_products,
)
from inventory import (
    LOCATIONS,
    assert_session_editable,
    build_count_rows,
    can_complete,
    is_verified,
    progress,
    quantity_value,
    utc_now_iso,
)

PRODUCT_HEADERS = ["product_id", "product_name", "category", "sort_order", "active"]
SESSION_HEADERS = [
    "session_id",
    "employee_name",
    "started_at",
    "completed_at",
    "status",
    "verified_count",
    "total_count",
    "total_units",
]
COUNT_HEADERS = [
    "count_id",
    "session_id",
    "location",
    "product_id",
    "product_name_snapshot",
    "category_snapshot",
    "sort_order_snapshot",
    "quantity",
    "verified",
    "verified_at",
    "updated_at",
]
CONFIG_HEADERS = ["key", "value"]

SHEET_HEADERS = {
    "Produits": PRODUCT_HEADERS,
    "Sessions": SESSION_HEADERS,
    "Comptages": COUNT_HEADERS,
    "Configuration": CONFIG_HEADERS,
}

DEFAULT_CONFIGURATION = {
    "destination_email": "",
    "location_1": LOCATIONS[0],
    "location_2": LOCATIONS[1],
    "location_3": LOCATIONS[2],
    "require_all_verified": "true",
}


class GoogleSheetsError(RuntimeError):
    """Safe, user-facing wrapper for Google Sheets failures."""


class GoogleSheetsConfigError(GoogleSheetsError):
    """Raised when secrets or worksheet schemas are invalid."""


def _column_letter(number: int) -> str:
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


class GoogleSheetsStore:
    def __init__(self, spreadsheet: Any):
        self.spreadsheet = spreadsheet

    def _worksheet(self, title: str) -> Any:
        try:
            return self.spreadsheet.worksheet(title)
        except Exception as exc:
            raise GoogleSheetsError(f"Impossible d’ouvrir l’onglet {title!r}.") from exc

    def ensure_schema(
        self,
        default_products: Sequence[Mapping[str, Any]] = DEFAULT_PRODUCT_ROWS,
    ) -> None:
        """Create missing worksheets, validate headers, and seed first-run data."""

        try:
            existing = {worksheet.title: worksheet for worksheet in self.spreadsheet.worksheets()}
            for title, headers in SHEET_HEADERS.items():
                worksheet = existing.get(title)
                if worksheet is None:
                    worksheet = self.spreadsheet.add_worksheet(
                        title=title,
                        rows=max(200, len(default_products) * len(LOCATIONS) + 20),
                        cols=max(12, len(headers)),
                    )
                    existing[title] = worksheet

                values = worksheet.get_all_values()
                if not values:
                    worksheet.update(
                        values=[headers],
                        range_name=f"A1:{_column_letter(len(headers))}1",
                        value_input_option="RAW",
                    )
                elif values[0][: len(headers)] != headers:
                    raise GoogleSheetsConfigError(
                        f"Les colonnes de l’onglet {title!r} ne correspondent pas au modèle attendu. "
                        f"Attendu : {', '.join(headers)}."
                    )

            products_ws = existing["Produits"]
            if not products_ws.get_all_records():
                products_ws.append_rows(
                    [[row.get(header, "") for header in PRODUCT_HEADERS] for row in default_products],
                    value_input_option="USER_ENTERED",
                )

            config_ws = existing["Configuration"]
            current_config = {
                _string(row.get("key")): _string(row.get("value"))
                for row in config_ws.get_all_records()
                if _string(row.get("key"))
            }
            missing = [
                [key, value]
                for key, value in DEFAULT_CONFIGURATION.items()
                if key not in current_config
            ]
            if missing:
                config_ws.append_rows(missing, value_input_option="USER_ENTERED")
        except GoogleSheetsError:
            raise
        except Exception as exc:
            raise GoogleSheetsError(
                "Impossible d’initialiser le Google Sheets. Vérifiez le partage et les permissions."
            ) from exc

    def load_products(self) -> list[Product]:
        try:
            return parse_products(self._worksheet("Produits").get_all_records())
        except (GoogleSheetsError, CatalogValidationError):
            raise
        except Exception as exc:
            raise GoogleSheetsError("Impossible de charger le catalogue de produits.") from exc

    def load_configuration(self) -> dict[str, str]:
        try:
            rows = self._worksheet("Configuration").get_all_records()
            return {
                _string(row.get("key")): _string(row.get("value"))
                for row in rows
                if _string(row.get("key"))
            }
        except GoogleSheetsError:
            raise
        except Exception as exc:
            raise GoogleSheetsError("Impossible de charger la configuration.") from exc

    def configured_locations(self) -> tuple[str, ...]:
        configuration = self.load_configuration()
        locations = tuple(
            configuration.get(f"location_{index}", "").strip()
            for index in range(1, 4)
        )
        if any(not location for location in locations):
            raise GoogleSheetsConfigError(
                "Les clés location_1, location_2 et location_3 doivent être remplies."
            )
        return locations

    def require_all_verified(self) -> bool:
        value = self.load_configuration().get("require_all_verified", "true")
        try:
            return parse_bool(value, default=True)
        except ValueError as exc:
            raise GoogleSheetsConfigError(
                "La configuration require_all_verified doit être true ou false."
            ) from exc

    def create_session(
        self,
        employee_name: str,
        products: Sequence[Product],
        locations: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        employee = " ".join(employee_name.split())
        if not employee:
            raise GoogleSheetsError("Le nom de l’employé est obligatoire.")
        if not products:
            raise GoogleSheetsError("Aucun produit actif n’est disponible pour le comptage.")

        locations = tuple(locations or self.configured_locations())
        session_id = str(uuid4())
        started_at = utc_now_iso()
        count_rows = build_count_rows(session_id, products, locations)
        session = {
            "session_id": session_id,
            "employee_name": employee,
            "started_at": started_at,
            "completed_at": "",
            "status": "IN_PROGRESS",
            "verified_count": 0,
            "total_count": len(count_rows),
            "total_units": 0,
        }

        try:
            self._worksheet("Sessions").append_row(
                [session[header] for header in SESSION_HEADERS],
                value_input_option="USER_ENTERED",
            )
            self._worksheet("Comptages").append_rows(
                [[row[header] for header in COUNT_HEADERS] for row in count_rows],
                value_input_option="USER_ENTERED",
            )
            return session
        except Exception as exc:
            raise GoogleSheetsError(
                "La création de la session n’a pas été confirmée par Google Sheets."
            ) from exc

    def _records(self, title: str) -> list[dict[str, Any]]:
        try:
            return [dict(record) for record in self._worksheet(title).get_all_records()]
        except GoogleSheetsError:
            raise
        except Exception as exc:
            raise GoogleSheetsError(f"Impossible de lire l’onglet {title!r}.") from exc

    def get_session(self, session_id: str) -> dict[str, Any]:
        for record in self._records("Sessions"):
            if _string(record.get("session_id")) == session_id:
                return self._normalize_session(record)
        raise GoogleSheetsError("Session d’inventaire introuvable.")

    def find_active_session(self) -> dict[str, Any] | None:
        sessions = [
            self._normalize_session(record)
            for record in self._records("Sessions")
            if _string(record.get("status")) in {"IN_PROGRESS", "REOPENED"}
        ]
        if not sessions:
            return None
        return max(sessions, key=lambda session: _string(session.get("started_at")))

    def load_session_counts(self, session_id: str) -> list[dict[str, Any]]:
        location_order = {location: index for index, location in enumerate(self.configured_locations())}
        rows = [
            self._normalize_count(record)
            for record in self._records("Comptages")
            if _string(record.get("session_id")) == session_id
        ]
        return sorted(
            rows,
            key=lambda row: (
                location_order.get(_string(row.get("location")), 99),
                int(row.get("sort_order_snapshot") or 0),
                _string(row.get("product_name_snapshot")).casefold(),
            ),
        )

    def save_count(
        self,
        session_id: str,
        count_id: str,
        quantity: int | str | None,
        *,
        verified: bool = True,
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        try:
            assert_session_editable(_string(session.get("status")))
        except Exception as exc:
            raise GoogleSheetsError("Cette session est verrouillée et ne peut pas être modifiée.") from exc

        normalized_quantity: int | str
        if verified:
            if quantity is None or _string(quantity) == "":
                normalized_quantity = 0
            else:
                try:
                    normalized_quantity = int(str(quantity).strip())
                except (TypeError, ValueError) as exc:
                    raise GoogleSheetsError("La quantité doit être un nombre entier.") from exc
                if normalized_quantity < 0:
                    raise GoogleSheetsError("La quantité ne peut pas être négative.")
        else:
            normalized_quantity = ""

        now = utc_now_iso()
        record, row_number = self._find_record_with_row("Comptages", "count_id", count_id)
        if _string(record.get("session_id")) != session_id:
            raise GoogleSheetsError("Ce comptage n’appartient pas à la session active.")

        record.update(
            {
                "quantity": normalized_quantity,
                "verified": bool(verified),
                "verified_at": now if verified else "",
                "updated_at": now,
            }
        )
        self._write_record("Comptages", row_number, COUNT_HEADERS, record)
        self._refresh_session_summary(session_id)
        return self._normalize_count(record)

    def complete_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        try:
            assert_session_editable(_string(session.get("status")))
        except Exception as exc:
            raise GoogleSheetsError("Cette session est déjà verrouillée.") from exc

        counts = self.load_session_counts(session_id)
        if not can_complete(counts, self.require_all_verified()):
            raise GoogleSheetsError("Des produits sont encore non vérifiés.")

        self._refresh_session_summary(session_id)
        return self._update_session(
            session_id,
            status="COMPLETED",
            completed_at=utc_now_iso(),
        )

    def reopen_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if _string(session.get("status")) != "COMPLETED":
            raise GoogleSheetsError("Seule une session terminée peut être rouverte.")
        return self._update_session(session_id, status="REOPENED", completed_at="")

    def abandon_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        try:
            assert_session_editable(_string(session.get("status")))
        except Exception as exc:
            raise GoogleSheetsError("Cette session ne peut pas être abandonnée.") from exc
        self._refresh_session_summary(session_id)
        return self._update_session(
            session_id,
            status="ABANDONED",
            completed_at=utc_now_iso(),
        )

    def _refresh_session_summary(self, session_id: str) -> dict[str, Any]:
        counts = self.load_session_counts(session_id)
        verified_count, total_count = progress(counts)
        total_units = sum(quantity_value(row.get("quantity")) for row in counts)
        return self._update_session(
            session_id,
            verified_count=verified_count,
            total_count=total_count,
            total_units=total_units,
        )

    def _update_session(self, session_id: str, **changes: Any) -> dict[str, Any]:
        record, row_number = self._find_record_with_row("Sessions", "session_id", session_id)
        record.update(changes)
        self._write_record("Sessions", row_number, SESSION_HEADERS, record)
        return self._normalize_session(record)

    def _find_record_with_row(
        self,
        title: str,
        key: str,
        expected_value: str,
    ) -> tuple[dict[str, Any], int]:
        worksheet = self._worksheet(title)
        try:
            values = worksheet.get_all_values()
        except Exception as exc:
            raise GoogleSheetsError(f"Impossible de lire l’onglet {title!r}.") from exc
        if not values or key not in values[0]:
            raise GoogleSheetsConfigError(f"Colonne {key!r} absente de l’onglet {title!r}.")
        key_index = values[0].index(key)
        headers = values[0]
        for row_number, values_row in enumerate(values[1:], start=2):
            padded = values_row + [""] * (len(headers) - len(values_row))
            if _string(padded[key_index]) == expected_value:
                return dict(zip(headers, padded)), row_number
        raise GoogleSheetsError(f"Enregistrement introuvable dans l’onglet {title!r}.")

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
                range_name=f"A{row_number}:{_column_letter(len(headers))}{row_number}",
                value_input_option="USER_ENTERED",
            )
        except Exception as exc:
            raise GoogleSheetsError(
                "Google Sheets n’a pas confirmé la sauvegarde. Réessayez sans quitter la page."
            ) from exc

    @staticmethod
    def _normalize_session(record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(record)
        for field in ("verified_count", "total_count", "total_units"):
            normalized[field] = quantity_value(normalized.get(field))
        return normalized

    @staticmethod
    def _normalize_count(record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(record)
        quantity = normalized.get("quantity", "")
        normalized["quantity"] = "" if quantity == "" else quantity_value(quantity)
        normalized["verified"] = is_verified(normalized)
        normalized["sort_order_snapshot"] = quantity_value(
            normalized.get("sort_order_snapshot", 0)
        )
        return normalized


def from_streamlit_secrets(secrets: Mapping[str, Any]) -> GoogleSheetsStore:
    """Authenticate from Streamlit secrets and open the configured spreadsheet."""

    try:
        google_config = secrets.get("google", {})
        spreadsheet_id = _string(google_config.get("spreadsheet_id"))
        service_account_info = dict(secrets["gcp_service_account"])
    except Exception as exc:
        raise GoogleSheetsConfigError(
            "Secrets manquants : configurez [google].spreadsheet_id et [gcp_service_account]."
        ) from exc

    if not spreadsheet_id:
        raise GoogleSheetsConfigError("Le secret google.spreadsheet_id est vide.")

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=scopes,
        )
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(spreadsheet_id)
        return GoogleSheetsStore(spreadsheet)
    except ImportError as exc:
        raise GoogleSheetsConfigError(
            "Les dépendances Google ne sont pas installées. Exécutez pip install -r requirements.txt."
        ) from exc
    except Exception as exc:
        raise GoogleSheetsConfigError(
            "Connexion Google Sheets impossible. Vérifiez l’identifiant, le compte de service et le partage."
        ) from exc
