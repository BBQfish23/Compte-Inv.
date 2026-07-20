"""Import-safe helpers used by the Streamlit user interface."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from inventory import LOCATIONS, is_verified, quantity_value, totals_by_location, totals_by_product


def normalize_employee_name(value: str) -> str:
    return " ".join(str(value or "").split())


def build_csv_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["Emplacement", "Catégorie", "Produit", "Quantité", "Vérifié"])
    for row in rows:
        writer.writerow(
            [
                row.get("location", ""),
                row.get("category_snapshot", ""),
                row.get("product_name_snapshot", ""),
                "" if row.get("quantity", "") == "" else quantity_value(row.get("quantity")),
                "Oui" if is_verified(row) else "Non",
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def build_summary_text(
    session: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> str:
    location_totals = totals_by_location(rows)
    product_totals = totals_by_product(rows)
    total_units = sum(location_totals.values())

    lines = [
        "Comptage d’inventaire - Spa le Finlandais",
        f"Employé : {session.get('employee_name', '')}",
        f"Début : {session.get('started_at', '')}",
        f"Total général : {total_units}",
        "",
        "Totaux par emplacement",
    ]
    for location in LOCATIONS:
        lines.append(f"{location} : {location_totals.get(location, 0)}")

    lines.extend(["", "Totaux consolidés par produit"])
    for item in sorted(
        product_totals.values(),
        key=lambda value: str(value.get("product_name", "")).casefold(),
    ):
        lines.append(f"{item.get('product_name', '')} : {item.get('total', 0)}")
    return "\n".join(lines)
