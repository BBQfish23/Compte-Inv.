from __future__ import annotations

import re

import pytest

from catalog import Product
from google_sheets import GoogleSheetsError, GoogleSheetsStore


class FakeWorksheet:
    def __init__(self, title):
        self.title = title
        self.values = []

    def get_all_values(self):
        return [row[:] for row in self.values]

    def get_all_records(self):
        if not self.values:
            return []
        headers = self.values[0]
        records = []
        for row in self.values[1:]:
            padded = row + [""] * (len(headers) - len(row))
            records.append(dict(zip(headers, padded)))
        return records

    def append_row(self, row, value_input_option=None):
        self.values.append(list(row))

    def append_rows(self, rows, value_input_option=None):
        self.values.extend([list(row) for row in rows])

    def update(self, range_name, values, value_input_option=None):
        start, end = range_name.split(":") if ":" in range_name else (range_name, range_name)
        start_col, start_row = self._cell(start)
        end_col, end_row = self._cell(end)
        while len(self.values) < end_row:
            self.values.append([])
        for row_offset, source_row in enumerate(values):
            row_index = start_row - 1 + row_offset
            while len(self.values[row_index]) < end_col:
                self.values[row_index].append("")
            for col_offset, value in enumerate(source_row):
                self.values[row_index][start_col - 1 + col_offset] = value

    @staticmethod
    def _cell(reference):
        match = re.fullmatch(r"([A-Z]+)(\d+)", reference)
        assert match, reference
        letters, row = match.groups()
        col = 0
        for letter in letters:
            col = col * 26 + ord(letter) - 64
        return col, int(row)


class FakeSpreadsheet:
    def __init__(self):
        self._worksheets = {}

    def worksheets(self):
        return list(self._worksheets.values())

    def add_worksheet(self, title, rows, cols):
        worksheet = FakeWorksheet(title)
        self._worksheets[title] = worksheet
        return worksheet

    def worksheet(self, title):
        return self._worksheets[title]


def make_store():
    spreadsheet = FakeSpreadsheet()
    store = GoogleSheetsStore(spreadsheet)
    store.ensure_schema(
        default_products=[
            {"product_id": "A", "product_name": "Produit A", "category": "Cat", "sort_order": 1, "active": True}
        ]
    )
    return store, spreadsheet


def test_ensure_schema_seeds_four_worksheets_products_and_configuration():
    store, spreadsheet = make_store()

    assert {ws.title for ws in spreadsheet.worksheets()} == {
        "Produits", "Sessions", "Comptages", "Configuration"
    }
    assert store.load_products() == [Product("A", "Produit A", "Cat", 1)]
    config = store.load_configuration()
    assert config["location_1"] == "Lounge"
    assert config["location_2"] == "Réception & Bureau"
    assert config["location_3"] == "QBE"
    assert config["require_all_verified"] == "true"


def test_create_session_creates_three_count_rows_and_finds_active_session():
    store, _ = make_store()

    session = store.create_session(" Maxime ", store.load_products())
    counts = store.load_session_counts(session["session_id"])

    assert session["employee_name"] == "Maxime"
    assert session["status"] == "IN_PROGRESS"
    assert len(counts) == 3
    assert [row["location"] for row in counts] == ["Lounge", "Réception & Bureau", "QBE"]
    assert store.find_active_session()["session_id"] == session["session_id"]


def test_save_count_accepts_zero_and_updates_session_summary():
    store, _ = make_store()
    session = store.create_session("Maxime", store.load_products())
    count = store.load_session_counts(session["session_id"])[0]

    saved = store.save_count(session["session_id"], count["count_id"], 0)
    refreshed_session = store.get_session(session["session_id"])

    assert saved["quantity"] == 0
    assert saved["verified"] is True
    assert refreshed_session["verified_count"] == 1
    assert refreshed_session["total_count"] == 3
    assert refreshed_session["total_units"] == 0


def test_completion_requires_all_verified_then_locks_until_reopened():
    store, _ = make_store()
    session = store.create_session("Maxime", store.load_products())
    counts = store.load_session_counts(session["session_id"])

    with pytest.raises(GoogleSheetsError, match="non vérifiés"):
        store.complete_session(session["session_id"])

    for count in counts:
        store.save_count(session["session_id"], count["count_id"], 0)
    completed = store.complete_session(session["session_id"])
    assert completed["status"] == "COMPLETED"

    with pytest.raises(GoogleSheetsError, match="verrouillée"):
        store.save_count(session["session_id"], counts[0]["count_id"], 1)

    reopened = store.reopen_session(session["session_id"])
    assert reopened["status"] == "REOPENED"
    store.save_count(session["session_id"], counts[0]["count_id"], 1)


def test_abandon_preserves_session_with_abandoned_status():
    store, _ = make_store()
    session = store.create_session("Maxime", store.load_products())

    abandoned = store.abandon_session(session["session_id"])

    assert abandoned["status"] == "ABANDONED"
    assert store.find_active_session() is None
