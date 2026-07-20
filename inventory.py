"""Pure inventory rules shared by Streamlit and Google Sheets persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from catalog import Product

LOCATIONS = ("Lounge", "Réception & Bureau", "QBE")
EDITABLE_STATUSES = {"IN_PROGRESS", "REOPENED"}


class SessionLockedError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_count_rows(
    session_id: str,
    products: Sequence[Product],
    locations: Sequence[str] = LOCATIONS,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = utc_now_iso()
    for location in locations:
        for product in products:
            rows.append(
                {
                    "count_id": str(uuid4()),
                    "session_id": session_id,
                    "location": location,
                    "product_id": product.product_id,
                    "product_name_snapshot": product.product_name,
                    "category_snapshot": product.category,
                    "sort_order_snapshot": product.sort_order,
                    "quantity": "",
                    "verified": False,
                    "verified_at": "",
                    "updated_at": now,
                }
            )
    return rows


def is_verified(row: Mapping[str, Any]) -> bool:
    value = row.get("verified", False)
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "vrai", "yes", "oui", "1"}


def quantity_value(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return max(0, int(float(str(value).strip())))
    except (TypeError, ValueError):
        return 0


def progress(rows: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    materialized = list(rows)
    return sum(1 for row in materialized if is_verified(row)), len(materialized)


def totals_by_location(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    totals = {location: 0 for location in LOCATIONS}
    for row in rows:
        location = str(row.get("location", ""))
        totals.setdefault(location, 0)
        totals[location] += quantity_value(row.get("quantity"))
    return totals


def totals_by_product(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for row in rows:
        product_id = str(row.get("product_id", ""))
        entry = totals.setdefault(
            product_id,
            {
                "product_name": str(row.get("product_name_snapshot", "")),
                "total": 0,
            },
        )
        entry["total"] += quantity_value(row.get("quantity"))
    return totals


def can_complete(rows: Iterable[Mapping[str, Any]], require_all_verified: bool = True) -> bool:
    if not require_all_verified:
        return True
    verified, total = progress(rows)
    return total > 0 and verified == total


def assert_session_editable(status: str) -> None:
    if status not in EDITABLE_STATUSES:
        raise SessionLockedError(f"La session {status!r} est verrouillée.")


def next_unverified_index(rows: Sequence[Mapping[str, Any]], start: int = 0) -> int | None:
    if not rows:
        return None
    for index in range(max(0, start), len(rows)):
        if not is_verified(rows[index]):
            return index
    for index in range(0, min(max(0, start), len(rows))):
        if not is_verified(rows[index]):
            return index
    return None
