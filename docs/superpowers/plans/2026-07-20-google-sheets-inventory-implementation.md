# Google Sheets Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the session-only inventory counter with a reliable, mobile-first Streamlit workflow that counts every active product at Lounge, Réception & Bureau, and QBE and persists every validation to Google Sheets.

**Architecture:** Pure business rules live in `inventory.py`, catalogue parsing and validation live in `catalog.py`, and every Google Sheets read/write is isolated in `google_sheets.py`. `app.py` only coordinates Streamlit screens and calls those modules. The Google spreadsheet is the source of truth; browser session state only holds the current UI value until Google confirms the write.

**Tech Stack:** Python 3.11+, Streamlit, pandas, gspread, google-auth, pytest.

## Global Constraints

- Location order is exactly `Lounge`, `Réception & Bureau`, `QBE`.
- Every active product is counted separately at all three locations.
- A verified quantity of zero counts as completed; an empty quantity with `verified = false` does not.
- Only one employee uses the application at a time.
- Employee name is free text and required when creating a session.
- Google Sheets is the source of truth for products, sessions, counts, and configuration.
- The application must not advance after a failed save.
- Completed sessions are immutable until explicitly reopened.
- Abandon/reset requires typing `EFFACER` and records status `ABANDONED` instead of deleting history.
- Secrets never enter GitHub.

---

### Task 1: Domain models, catalogue validation, and counting rules

**Files:**
- Create: `catalog.py`
- Create: `inventory.py`
- Create: `tests/test_catalog.py`
- Create: `tests/test_inventory.py`

**Interfaces:**
- Produces: `Product`, `CatalogValidationError`, `parse_products(rows)`, `LOCATIONS`, `build_count_rows(session_id, products)`, `progress(rows)`, `totals_by_location(rows)`, `totals_by_product(rows)`, `can_complete(rows, require_all_verified)`, `assert_session_editable(status)`.

- [ ] **Step 1: Write failing catalogue tests**

Test active-row filtering, boolean parsing, stable IDs, duplicate rejection, blank names, and `sort_order` sorting.

- [ ] **Step 2: Run catalogue tests and verify RED**

Run: `pytest tests/test_catalog.py -v`
Expected: import failure because `catalog.py` does not exist.

- [ ] **Step 3: Implement minimal catalogue parser**

Use a frozen `Product` dataclass with `product_id`, `product_name`, `category`, and `sort_order`. Raise `CatalogValidationError` with all detected row errors.

- [ ] **Step 4: Run catalogue tests and verify GREEN**

Run: `pytest tests/test_catalog.py -v`
Expected: all catalogue tests pass.

- [ ] **Step 5: Write failing inventory tests**

Cover three rows per product, fixed location order, zero-as-verified progress, blank-as-unverified progress, product totals, location totals, completion requirements, and completed-session locking.

- [ ] **Step 6: Run inventory tests and verify RED**

Run: `pytest tests/test_inventory.py -v`
Expected: import failure because `inventory.py` does not exist.

- [ ] **Step 7: Implement minimal inventory rules**

Represent count rows as dictionaries compatible with Google Sheets columns. Keep functions pure and independent from Streamlit and gspread.

- [ ] **Step 8: Run inventory tests and verify GREEN**

Run: `pytest tests/test_catalog.py tests/test_inventory.py -v`
Expected: all tests pass.

### Task 2: Google Sheets persistence layer

**Files:**
- Create: `google_sheets.py`
- Create: `tests/test_google_sheets.py`

**Interfaces:**
- Consumes: `Product`, `build_count_rows`, `progress`, totals functions.
- Produces: `GoogleSheetsStore`, `GoogleSheetsError`, `GoogleSheetsConfigError`, `from_streamlit_secrets(secrets)`.
- Store methods: `ensure_schema()`, `load_products()`, `load_configuration()`, `find_active_session()`, `create_session(employee_name, products, locations)`, `load_session_counts(session_id)`, `save_count(session_id, count_id, quantity, verified=True)`, `complete_session(session_id)`, `reopen_session(session_id)`, `abandon_session(session_id)`.

- [ ] **Step 1: Write failing persistence tests using fake worksheets**

Test schema seeding, session creation, three count rows per product, active-session lookup, save-count updates, summary updates, completion locking, reopening, and abandonment.

- [ ] **Step 2: Run persistence tests and verify RED**

Run: `pytest tests/test_google_sheets.py -v`
Expected: import failure because `google_sheets.py` does not exist.

- [ ] **Step 3: Implement the store without importing gspread at module import time**

Accept an injected spreadsheet object for tests. Import `gspread` and Google credentials only inside `from_streamlit_secrets`, so unit tests run without network packages.

- [ ] **Step 4: Implement worksheet schema and defaults**

Create or validate `Produits`, `Sessions`, `Comptages`, and `Configuration`. Seed the current catalogue only when `Produits` is empty, and seed location/configuration keys only when absent.

- [ ] **Step 5: Implement row lookup and atomic-looking update flow**

Update the count row first, recalculate session summaries from saved count rows, then update `Sessions`. Convert provider exceptions into `GoogleSheetsError` without exposing credentials.

- [ ] **Step 6: Run persistence tests and verify GREEN**

Run: `pytest tests/test_google_sheets.py -v`
Expected: all tests pass.

### Task 3: Mobile Streamlit workflow

**Files:**
- Replace: `app.py`
- Create: `tests/test_app_helpers.py`

**Interfaces:**
- Consumes all public interfaces from Tasks 1 and 2.
- Produces a Streamlit UI with start/resume, guided count, corrections, summary, completion, reopen, and abandon flows.

- [ ] **Step 1: Write failing tests for non-UI helpers**

Test next-unverified selection, CSV construction, and safe employee-name normalization in helper functions that can be imported without running Streamlit.

- [ ] **Step 2: Run helper tests and verify RED**

Run: `pytest tests/test_app_helpers.py -v`
Expected: import failure because helpers do not exist.

- [ ] **Step 3: Implement helper functions in `app.py` or a small import-safe helper section**

Keep Streamlit execution under `main()` and `if __name__ == "__main__": main()` so tests can import helpers.

- [ ] **Step 4: Implement connection and setup screen**

Read `st.secrets`, connect to the spreadsheet, ensure schema, validate products, and show actionable errors for missing secrets or invalid catalogue rows.

- [ ] **Step 5: Implement start/resume screen**

Require a nonblank employee name for a new session. If an active session exists, display employee, start time, and progress with actions to resume or enter the protected abandonment flow.

- [ ] **Step 6: Implement guided counting**

Show one product/location at a time in fixed order, quantity input, `−1`, `+1`, `+5`, previous, `Valider et suivant`, and progress. Save before moving. On save failure keep the value, show `Réessayer la sauvegarde`, and do not advance.

- [ ] **Step 7: Implement correction and summary views**

Provide grouped rows by location, explicit save per changed row, verified state, totals by product/location, remaining items, CSV download, and a disabled completion button until rules permit completion.

- [ ] **Step 8: Implement completed-session and danger flows**

Lock editing after completion, require explicit reopen confirmation, and require exact `EFFACER` plus a second confirmation to abandon.

- [ ] **Step 9: Run helper tests and syntax checks**

Run: `pytest tests/test_app_helpers.py -v && python -m py_compile app.py catalog.py inventory.py google_sheets.py`
Expected: tests pass and compilation exits 0.

### Task 4: Deployment configuration and documentation

**Files:**
- Replace: `requirements.txt`
- Replace: `README.md`
- Create: `.streamlit/secrets.example.toml`

**Interfaces:**
- Documents required Google spreadsheet sharing and exact secret keys.

- [ ] **Step 1: Pin tested dependencies**

Include Streamlit, pandas, gspread, google-auth, and pytest at exact versions.

- [ ] **Step 2: Document Google setup**

Explain service-account creation, sharing the spreadsheet with the service-account email, configuring `spreadsheet_id`, copying example secrets, first-run worksheet creation, catalogue columns, and recovery behavior.

- [ ] **Step 3: Document daily use**

Explain start, resume, zero verification, corrections, completion, reopen, abandonment, and CSV export.

- [ ] **Step 4: Run complete verification**

Run: `pytest -q`
Expected: zero failures.

Run: `python -m py_compile app.py catalog.py inventory.py google_sheets.py`
Expected: exit 0.

Run: `grep -R "private_key\|client_email" -n --exclude='secrets.example.toml' .`
Expected: no committed real credentials.

- [ ] **Step 5: Review requirements against the design specification**

Confirm every acceptance criterion in `docs/superpowers/specs/2026-07-20-inventaire-google-sheets-design.md` maps to implemented behavior or an automated test.
