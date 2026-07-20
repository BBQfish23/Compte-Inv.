from app_helpers import build_csv_bytes, build_summary_text, normalize_employee_name


def sample_rows():
    return [
        {
            "location": "Lounge",
            "product_id": "A",
            "product_name_snapshot": "Produit A",
            "category_snapshot": "Cat",
            "quantity": 0,
            "verified": True,
        },
        {
            "location": "QBE",
            "product_id": "A",
            "product_name_snapshot": "Produit A",
            "category_snapshot": "Cat",
            "quantity": 2,
            "verified": True,
        },
    ]


def test_normalize_employee_name_collapses_whitespace():
    assert normalize_employee_name("  Maxime   Leclair  ") == "Maxime Leclair"
    assert normalize_employee_name("   ") == ""


def test_csv_includes_zero_and_verified_state_with_utf8_bom():
    data = build_csv_bytes(sample_rows())
    text = data.decode("utf-8-sig")

    assert text.startswith("Emplacement,Catégorie,Produit,Quantité,Vérifié")
    assert "Lounge,Cat,Produit A,0,Oui" in text
    assert "QBE,Cat,Produit A,2,Oui" in text


def test_summary_text_contains_employee_locations_and_consolidated_total():
    text = build_summary_text(
        {"employee_name": "Maxime", "started_at": "2026-07-20T12:00:00+00:00"},
        sample_rows(),
    )

    assert "Employé : Maxime" in text
    assert "Lounge : 0" in text
    assert "QBE : 2" in text
    assert "Produit A : 2" in text
