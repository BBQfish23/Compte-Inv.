"""Catalogue loading and validation for the inventory application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    product_name: str
    category: str
    sort_order: int


class CatalogValidationError(ValueError):
    """Raised when one or more product catalogue rows are invalid."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(errors)
        super().__init__("Catalogue invalide : " + "; ".join(self.errors))


_TRUE_VALUES = {"1", "true", "vrai", "yes", "oui", "y", "o"}
_FALSE_VALUES = {"0", "false", "faux", "no", "non", "n"}


def parse_bool(value: Any, *, default: bool = True) -> bool:
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"booléen invalide: {value!r}")


def parse_products(rows: Iterable[Mapping[str, Any]]) -> list[Product]:
    """Validate worksheet records and return active products in display order."""

    errors: list[str] = []
    products: list[Product] = []
    seen_ids: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        product_id = str(row.get("product_id", "")).strip()
        product_name = str(row.get("product_name", "")).strip()
        category = str(row.get("category", "")).strip()

        if not product_id:
            errors.append(f"ligne {row_number}: identifiant manquant")
        elif product_id in seen_ids:
            errors.append(f"ligne {row_number}: identifiant dupliqué {product_id!r}")
        else:
            seen_ids.add(product_id)

        if not product_name:
            errors.append(f"ligne {row_number}: nom manquant")

        try:
            sort_order = int(str(row.get("sort_order", "")).strip())
        except (TypeError, ValueError):
            errors.append(f"ligne {row_number}: ordre invalide")
            sort_order = row_number

        try:
            active = parse_bool(row.get("active", True))
        except ValueError:
            errors.append(f"ligne {row_number}: valeur active invalide")
            active = False

        if product_id and product_name and active:
            products.append(Product(product_id, product_name, category, sort_order))

    if errors:
        raise CatalogValidationError(errors)

    return sorted(products, key=lambda product: (product.sort_order, product.product_name.casefold()))


DEFAULT_PRODUCT_ROWS: tuple[dict[str, Any], ...] = (
    {"product_id": "SPA-CHANDELLES", "product_name": "Chandelles", "category": "Produits spa & bien-être", "sort_order": 10, "active": True},
    {"product_id": "SPA-DIFFUSEUR-ROSEAU", "product_name": "Diffuseur Roseau", "category": "Produits spa & bien-être", "sort_order": 20, "active": True},
    {"product_id": "SPA-SAVON-LIQUIDE", "product_name": "Savon liquide", "category": "Produits spa & bien-être", "sort_order": 30, "active": True},
    {"product_id": "SPA-GEL-DOUCHE", "product_name": "Gel douche", "category": "Produits spa & bien-être", "sort_order": 40, "active": True},
    {"product_id": "SPA-HUILE-MASSAGE", "product_name": "Huile à massage", "category": "Produits spa & bien-être", "sort_order": 50, "active": True},
    {"product_id": "SPA-BAIN-MOUSSANT", "product_name": "Bain moussant", "category": "Produits spa & bien-être", "sort_order": 60, "active": True},
    {"product_id": "SPA-BRUINE-AMBIANCE", "product_name": "Bruine d'ambiance", "category": "Produits spa & bien-être", "sort_order": 70, "active": True},
    {"product_id": "SPA-HUILE-ESSENTIELLE", "product_name": "Huile essentielle", "category": "Produits spa & bien-être", "sort_order": 80, "active": True},
    {"product_id": "SPA-SAVON-BARRE", "product_name": "Savon en barre", "category": "Produits spa & bien-être", "sort_order": 90, "active": True},
    {"product_id": "SPA-BRUINE-DOUCHE", "product_name": "Bruine de douche", "category": "Produits spa & bien-être", "sort_order": 100, "active": True},
    {"product_id": "COMBO-GEL-DOUCHE", "product_name": "Combo Gel douche (bain)", "category": "Combos", "sort_order": 110, "active": True},
    {"product_id": "COMBO-CHANDELLE", "product_name": "Combo Chandelle (détente)", "category": "Combos", "sort_order": 120, "active": True},
    {"product_id": "COMBO-PEDICURE", "product_name": "Kit Pédicure", "category": "Combos", "sort_order": 130, "active": True},
    *tuple({"product_id": f"MAILLOT-F-{size}", "product_name": f"Maillot Femme {size}", "category": "Maillots femme", "sort_order": 140 + index * 10, "active": True} for index, size in enumerate((28, 30, 32, 34, 36, 38, 40, 42))),
    {"product_id": "MAILLOT-H-S", "product_name": "Maillot Homme Small", "category": "Maillots homme", "sort_order": 220, "active": True},
    {"product_id": "MAILLOT-H-M", "product_name": "Maillot Homme Médium", "category": "Maillots homme", "sort_order": 230, "active": True},
    {"product_id": "MAILLOT-H-L", "product_name": "Maillot Homme Large", "category": "Maillots homme", "sort_order": 240, "active": True},
    {"product_id": "MAILLOT-H-XL", "product_name": "Maillot Homme Extra Large", "category": "Maillots homme", "sort_order": 250, "active": True},
    *tuple({"product_id": f"SLIDE-N-{size.replace('-', '_')}", "product_name": f"Slide noir {size}", "category": "Slides noirs", "sort_order": 260 + index * 10, "active": True} for index, size in enumerate(("36-37", "38-39", "40-41", "42-43", "44-45"))),
    *tuple({"product_id": f"SLIDE-B-{size.replace('-', '_')}", "product_name": f"Slide blanche {size}", "category": "Slides blancs", "sort_order": 310 + index * 10, "active": True} for index, size in enumerate(("36-37", "38-39", "40-41", "42-43", "44-45"))),
    {"product_id": "TUQUE-KAKI", "product_name": "Tuque Kaki", "category": "Tuques", "sort_order": 360, "active": True},
    {"product_id": "TUQUE-MARINE", "product_name": "Tuque Marine", "category": "Tuques", "sort_order": 370, "active": True},
    {"product_id": "TUQUE-BEIGE", "product_name": "Tuque Beige", "category": "Tuques", "sort_order": 380, "active": True},
    {"product_id": "TUQUE-NOIRE", "product_name": "Tuque Noire", "category": "Tuques", "sort_order": 390, "active": True},
    {"product_id": "TUQUE-BRUNE", "product_name": "Tuque brune", "category": "Tuques", "sort_order": 400, "active": True},
    {"product_id": "TUQUE-NOIRE-POMPON", "product_name": "Tuque noire pompon", "category": "Tuques", "sort_order": 410, "active": True},
    {"product_id": "TUQUE-BLANCHE-POMPON", "product_name": "Tuque blanche pompon", "category": "Tuques", "sort_order": 420, "active": True},
    {"product_id": "PEIGNOIR-REVENTE", "product_name": "Peignoir de revente", "category": "Thé & accessoires", "sort_order": 430, "active": True},
    {"product_id": "THE-ECLAT-CITRON", "product_name": "Thé Éclat Citron", "category": "Thé & accessoires", "sort_order": 440, "active": True},
    {"product_id": "THE-CHAI-CAMELLIA", "product_name": "Thé Chai Camellia", "category": "Thé & accessoires", "sort_order": 450, "active": True},
    {"product_id": "THE-ERABLE", "product_name": "Thé Érable", "category": "Thé & accessoires", "sort_order": 460, "active": True},
    {"product_id": "THE-ROOIBOS", "product_name": "Thé Rooibos", "category": "Thé & accessoires", "sort_order": 470, "active": True},
    {"product_id": "THE-NUIT-ETOILE", "product_name": "Thé Nuit Étoilé", "category": "Thé & accessoires", "sort_order": 480, "active": True},
    {"product_id": "ACCESSOIRE-TASSE", "product_name": "Tasse", "category": "Thé & accessoires", "sort_order": 490, "active": True},
    {"product_id": "ACCESSOIRE-FILTRES", "product_name": "Filtres", "category": "Thé & accessoires", "sort_order": 500, "active": True},
)
