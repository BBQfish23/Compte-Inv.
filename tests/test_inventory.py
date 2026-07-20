import pytest

from catalog import Product
from inventory import (
    LOCATIONS,
    SessionLockedError,
    assert_session_editable,
    build_count_rows,
    can_complete,
    progress,
    totals_by_location,
    totals_by_product,
)


def products():
    return [
        Product("A", "Produit A", "Cat 1", 1),
        Product("B", "Produit B", "Cat 2", 2),
    ]


def test_build_count_rows_creates_three_locations_per_product_in_fixed_order():
    rows = build_count_rows("session-1", products())

    assert len(rows) == 6
    assert [row["location"] for row in rows] == [
        "Lounge", "Lounge",
        "Réception & Bureau", "Réception & Bureau",
        "QBE", "QBE",
    ]
    assert LOCATIONS == ("Lounge", "Réception & Bureau", "QBE")
    assert all(row["quantity"] == "" and row["verified"] is False for row in rows)


def test_progress_counts_verified_zero_but_not_blank_unverified():
    rows = build_count_rows("session-1", products()[:1])
    rows[0]["quantity"] = 0
    rows[0]["verified"] = True
    rows[1]["quantity"] = ""
    rows[1]["verified"] = False

    assert progress(rows) == (1, 3)


def test_totals_group_by_location_and_product():
    rows = build_count_rows("session-1", products())
    quantities = [1, 2, 3, 4, 5, 6]
    for row, quantity in zip(rows, quantities):
        row["quantity"] = quantity
        row["verified"] = True

    assert totals_by_location(rows) == {
        "Lounge": 3,
        "Réception & Bureau": 7,
        "QBE": 11,
    }
    assert totals_by_product(rows) == {
        "A": {"product_name": "Produit A", "total": 9},
        "B": {"product_name": "Produit B", "total": 12},
    }


def test_can_complete_requires_all_verified_when_configured():
    rows = build_count_rows("session-1", products()[:1])
    rows[0]["quantity"] = 0
    rows[0]["verified"] = True

    assert can_complete(rows, require_all_verified=False) is True
    assert can_complete(rows, require_all_verified=True) is False

    for row in rows:
        row["quantity"] = 0
        row["verified"] = True
    assert can_complete(rows, require_all_verified=True) is True


def test_completed_or_abandoned_sessions_are_locked():
    assert_session_editable("IN_PROGRESS")
    assert_session_editable("REOPENED")

    with pytest.raises(SessionLockedError):
        assert_session_editable("COMPLETED")
    with pytest.raises(SessionLockedError):
        assert_session_editable("ABANDONED")
