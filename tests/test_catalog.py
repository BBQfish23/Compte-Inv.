import pytest

from catalog import CatalogValidationError, Product, parse_products


def test_parse_products_filters_inactive_and_sorts():
    rows = [
        {"product_id": "B", "product_name": "Produit B", "category": "Cat", "sort_order": "2", "active": "TRUE"},
        {"product_id": "A", "product_name": "Produit A", "category": "Cat", "sort_order": "1", "active": "oui"},
        {"product_id": "C", "product_name": "Produit C", "category": "Cat", "sort_order": "3", "active": "false"},
    ]

    products = parse_products(rows)

    assert products == [
        Product("A", "Produit A", "Cat", 1),
        Product("B", "Produit B", "Cat", 2),
    ]


def test_parse_products_rejects_duplicate_ids_and_invalid_rows():
    rows = [
        {"product_id": "A", "product_name": "", "category": "Cat", "sort_order": "x", "active": "true"},
        {"product_id": "A", "product_name": "Produit A", "category": "Cat", "sort_order": "2", "active": "true"},
    ]

    with pytest.raises(CatalogValidationError) as exc:
        parse_products(rows)

    message = str(exc.value)
    assert "nom manquant" in message
    assert "ordre invalide" in message
    assert "identifiant dupliqué" in message


def test_parse_products_rejects_missing_id():
    with pytest.raises(CatalogValidationError, match="identifiant manquant"):
        parse_products([
            {"product_id": "", "product_name": "Produit", "category": "Cat", "sort_order": "1", "active": "true"}
        ])
