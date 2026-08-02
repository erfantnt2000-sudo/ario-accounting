# Ario Accounting + Elevator Service — Architecture Guide for AI Editors

**Purpose of this document:** Enable any AI or developer to understand, modify, and extend this software safely without breaking existing features.

**Product name:** حسابداری آریو (Ario Accounting) + مدیریت سرویس آسانسور  
**Language of UI:** Persian (Farsi), RTL  
**Stack:** Python 3.12 + Flask + Jinja2 + SQLite + jdatetime + Gunicorn  
**Deploy target:** Render.com (or any host supporting Gunicorn + `$PORT`)

---

## 1. Project layout

```
ario_accounting/
├── app.py                 # ALL HTTP routes, auth, business handlers (~1000+ lines)
├── database.py            # SQLite path, core tables, init_db, indexes, helpers
├── elevator_models.py     # Elevator-domain tables + sample seed data
├── requirements.txt       # flask, jdatetime, openpyxl, pandas, gunicorn
├── Procfile               # web: gunicorn app:app --bind 0.0.0.0:$PORT ...
├── runtime.txt            # python-3.12.x
├── run.bat / run.sh       # local Windows/Linux launcher
├── DEPLOY_ONLINE.md       # deploy instructions (Persian)
├── ARCHITECTURE.md        # this file
├── data/                  # local SQLite folder (ignored on cloud; uses /tmp)
└── templates/
    ├── base.html          # layout, sidebar, CSS (responsive), mobile menu JS
    ├── login.html         # standalone login page (does NOT extend base)
    ├── dashboard.html
    ├── accounts*.html, vouchers*.html, products*.html, invoices*.html, parties*.html
    ├── customers*.html, appointments_*.html, payments.html
    └── elev_*.html        # all elevator module pages
```

**Important:** There is almost no frontend framework. UI = server-rendered Jinja2 + embedded CSS in `base.html`. No React/Vue. No REST API layer for the main UI.

---

## 2. How the app boots

1. Gunicorn loads `app:app` (Flask instance named `app` in `app.py`).
2. At import time, a try/except block runs:
   - `init_db()` → core accounting + appointments + payments tables + seed admin user
   - `init_elevator_tables()` → complexes, buildings, elevators, contracts, visits, faults, repairs, technicians
   - `seed_elevator_sample()` → sample data only if tables empty
   - `create_indexes()` → performance indexes
3. `if __name__ == "__main__"` does the same for local `python app.py`.

**DB path logic (`database.py`):**
- If env `RENDER` or `PORT` is set → `/tmp/ario.db` (writable on Render free tier; **ephemeral** — data lost on restart)
- Else → `data/ario.db` next to the project

**Default login:** username `admin` / password `admin` (stored plaintext in `users` table — improve before production).

---

## 3. Auth pattern

```python
@login_required
def some_view():
    ...
```

Decorator checks `session["user_id"]`. Login sets `user_id`, `username`, `full_name`.  
Session secret: `os.environ.get("SECRET_KEY", "ario-accounting-secret-key-2026-change-me")`.

When adding a new page that needs login: decorate the view with `@login_required`.

---

## 4. Database schema (logical)

### Core accounting (database.py)
| Table | Role |
|-------|------|
| `users` | Login accounts |
| `accounts` | Chart of accounts (code, name, parent_code, account_type: asset/liability/equity/revenue/expense) |
| `parties` | Customers/suppliers (`party_type`: customer/supplier/both) |
| `products` | Inventory items + stock_qty |
| `vouchers` + `voucher_lines` | Journal entries (debit/credit must balance) |
| `invoices` + `invoice_lines` | Sales invoices; sale flow also posts voucher + reduces stock |
| `appointments` | Customer appointments (date, is_done, amount) |
| `payments` | Customer payments (linked to party_id) |

### Elevator domain (elevator_models.py)
| Table | Role |
|-------|------|
| `complexes` | Residential/commercial complexes |
| `buildings` | Buildings under a complex; optional `party_id` customer |
| `elevators` | Elevator file/dossier per building |
| `contracts` | Service contracts (start/end, amount, visit_per_month, status) |
| `service_visits` | Planned/done periodic visits; report_text, customer_sign |
| `faults` | Breakdown tickets; status open → dispatched → closed |
| `repairs` + `repair_parts` | Repair history + parts cost |
| `technicians` | Field technicians |

**Dates in UI/DB for business fields:** Jalali strings `YYYY/MM/DD` via `jdatetime` (`today_jalali()`, `current_month_jalali()`).  
**Timestamps `created_at`:** ISO datetime strings.

**Convention:** Prefer `CREATE TABLE IF NOT EXISTS` and seed only when `COUNT(*) == 0`.

---

## 5. Route map (by domain)

### Auth / home
- `GET/POST /login`, `GET /logout`, `GET /` dashboard

### Accounting
- `/accounts`, `/accounts/add`, `/accounts/edit/<id>`
- `/vouchers`, `/vouchers/add`, `/vouchers/view/<id>`
- `/products`, `/products/add`, `/products/edit/<id>`
- `/parties`, `/parties/add`, `/parties/edit/<id>`
- `/invoices`, `/invoices/sale`
- `/reports/trial-balance`, `/reports/journal`, `/reports/profit-loss`  
  **Note:** These three were **removed from the sidebar menu** in v5 but **routes/templates still exist**. Do not re-add to menu unless requested.

### CRM / appointments
- `/customers`, `/customers/add`, `/customers/edit/<id>` (customers = parties filtered)
- `/appointments/today`, `POST /appointments/add`, `POST /appointments/toggle/<id>`
- `/appointments/noshow?month=YYYY/MM`
- `/payments`, `POST /payments/add`

### Elevator
- `/elevators/dashboard`
- `/elevators/complexes`, `/elevators/complexes/add`
- `/elevators/buildings`, `/elevators/buildings/add`
- `/elevators/list`, `/elevators/add`
- `/elevators/contracts`, `/elevators/contracts/add`
- `/elevators/visits`, `POST /elevators/visits/add`, `POST /elevators/visits/done/<id>`
- `/elevators/faults`, `POST /elevators/faults/add`, `dispatch/<id>`, `close/<id>`
- `/elevators/repairs`
- `/elevators/technicians`, `POST /elevators/technicians/add`
- `/elevators/profit` (profit by contract/building — **keep**; different from accounting P&L)

---

## 6. UI / frontend rules

- **All authenticated pages** extend `templates/base.html`.
- **Sidebar links** live only in `base.html` (`url_for('endpoint_name')`).
- **CSS** is almost entirely inside `<style>` in `base.html` (CSS variables, mobile breakpoints at 900px and 480px).
- **Mobile menu:** hamburger toggles `.sidebar.open` + overlay; JS at bottom of `base.html`.
- **Tables:** JS auto-wraps tables in `.table-wrap` for horizontal scroll on mobile.
- **Forms on mobile:** use class `mobile-stack-form` for vertical full-width controls.
- **RTL:** `<html lang="fa" dir="rtl">`. Sidebar is on the **right**.
- **Flash messages:** `flash("...", "success"|"danger")` + `get_flashed_messages` in base.

When adding a page:
1. Add route in `app.py`
2. Create `templates/your_page.html` extending `base.html`
3. Add `<a href="{{ url_for('your_endpoint') }}">` in `base.html` nav
4. Pass `today=today_jalali()` if topbar date should show

---

## 7. Coding conventions (must follow when editing)

1. **Persian UI strings** for labels/buttons/flash; code identifiers in English.
2. **Open DB → query → commit if write → close** per request (no global connection).
3. Use `get_connection()` only; never hardcode another DB path in routes.
4. New elevator tables → `elevator_models.py` + call from `init_elevator_tables()`.
5. New core tables → `database.py` `init_db()`.
6. New indexes → `create_indexes()` list in `database.py`.
7. Money fields: `REAL`; display with `" {:,.0f}".format(x)` in templates.
8. Do not introduce a second framework unless explicitly requested.
9. Keep `Procfile` start command as Gunicorn binding `$PORT`.
10. After structural changes, smoke-test with Flask test client: login as admin, GET main pages expect 200.

---

## 8. How to add a typical new feature (checklist for AI)

**Example: “Add elevator inspection checklist per visit”**

1. `elevator_models.py`: `CREATE TABLE IF NOT EXISTS visit_checklist (... visit_id, item, ok INTEGER)`
2. Call table creation inside `init_elevator_tables()`
3. `app.py`: routes e.g. `GET/POST /elevators/visits/<id>/checklist`
4. Template `elev_checklist.html` extends `base.html`
5. Link from `elev_visits.html` row actions
6. Optional index on `visit_id` in `create_indexes()`
7. No change to auth unless new roles needed

**Example: “Change theme color”**  
Edit CSS variables in `base.html` `:root` (`--primary`, `--accent`, …).

**Example: “Persistent cloud DB”**  
Replace SQLite with PostgreSQL (`psycopg2`/`sqlalchemy`), set `DATABASE_URL` on Render, migrate all `get_connection()` usages. Highest-impact production upgrade.

---

## 9. Known limitations (do not “fix” without user ask)

- SQLite on Render `/tmp` is **not durable** across deploys/restarts
- Passwords are plaintext
- No role-based access (only login vs anonymous)
- No real image upload for technician photos (text note field only)
- No SMS renewal alerts
- Accounting reports (trial balance / journal / P&L) removed from menu only
- Single admin user seeded by default

---

## 10. Local run vs production

```bash
# Local
pip install -r requirements.txt
python app.py
# → http://127.0.0.1:5000

# Production (Render)
# Build: pip install -r requirements.txt
# Start: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread ...
```

Env vars: `PORT`, `SECRET_KEY`, optional `RENDER=true`.

---

## 11. Quick file ownership map for edits

| Change type | Edit these files |
|-------------|------------------|
| New HTTP page | `app.py` + `templates/*.html` + maybe `base.html` nav |
| New DB column/table (accounting) | `database.py` |
| New DB column/table (elevator) | `elevator_models.py` |
| Mobile/layout/CSS | `templates/base.html` |
| Login look | `templates/login.html` |
| Deploy process | `Procfile`, `requirements.txt`, `DEPLOY_ONLINE.md` |
| Performance indexes/PRAGMAs | `database.py` (`get_connection`, `create_indexes`) |

---

## 11b. Changelog — v6 update

- **Sales invoice (`invoice_sale.html` + `invoice_sale()`):** redesigned with line-level discount, invoice-level discount, VAT (`tax_percent`), live JS totals, Persian amount-in-words, and a new printable view `invoice_view.html` / `invoice_view(iid)` route (linked from `invoices.html`). `invoice_lines.discount`, `invoices.discount`, `invoices.tax` (already existed in schema) are now actually populated.
- **Elevator "today's appointments" (`elev_today.html` + `elev_today()` at `/elevators/today`):** enter a date (+ optional customer/building search) to see that day's `service_visits` with customer/building/phone/technician details and a one-click "done" toggle (`elev_visit_quick_done`). This mirrors the existing generic `appointments_today` but is elevator/`service_visits`-specific.
- **Missed/incomplete list (`elev_missed.html` + `elev_missed()` at `/elevators/missed`):** any `service_visits` row with `status='planned'` and `planned_date < today` shows up here automatically, with "mark done" and "reschedule to new date" (`elev_visit_reschedule`) actions.
- `elev_visit_add` now accepts an optional `next` form field to redirect back to the calling page (used by `elev_today.html`).
- Nav links for both new elevator pages added to `base.html` under the "آسانسور" group. Mobile hamburger menu (`toggleSidebar`/`closeSidebar`/`menuBtn`/`sidebarOverlay`) untouched.
- Full route smoke test (all GET pages) + POST smoke test (every "add" form across accounting + elevator modules) passed with a stub `jdatetime` during dev; no 4xx/5xx.

## 11c. Changelog — v8 security & data-integrity fixes

- **Passwords hashed** (`werkzeug.security.generate_password_hash`/`check_password_hash`). `database.py` auto-migrates any legacy plaintext password found in `users.password` on startup (detects by absence of `pbkdf2:`/`scrypt:` prefix), so upgrading an existing deployment does not lock anyone out.
- **SECRET_KEY**: no more hardcoded fallback string in source. If the `SECRET_KEY` env var is absent, `app.py` generates a random `secrets.token_hex(32)` at process start (prints a warning) instead of a predictable committed value.
- **CSRF protection**: `get_csrf_token()`/`inject_csrf_token()` + a `before_request` check in `app.py` validate a `csrf_token` hidden field on every POST against the session token. All templates with `<form method="post">` already carry `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` — any *new* POST form must include this or it will be rejected.
- **IDOR fix** in `tech_visit_report()` (`/tech/visit/<id>`): a technician can only open/submit a visit whose `technician_id` is NULL or equal to their own `session['technician_id']`; otherwise redirected with a flash error. Admin role is unaffected.
- **Jalali date normalization**: `database.normalize_jalali_date(value, default=None)` zero-pads and validates `YYYY/MM/DD` (also accepts `-` separator and non-padded month/day), rejecting impossible calendar dates via `jdatetime.date(...)`. Applied to every user-submitted date field across `app.py` (voucher, invoice, contract start/end, service visit planned/visit date, reschedule, appointment, payment, fault report). Without this, e.g. `1404/5/9` and `1404/05/09` were treated as different strings and broke exact-match lookups (`/elevators/today`) and lexicographic sorting.
- **Duplicate-customer fix** in `/customers/register`: added an "existing customer" toggle (`existing_party_id`) so adding a second building/contract for the same employer reuses the existing `parties` row instead of creating a duplicate.
- **contract_no / invoice_no collision fix**: both `customer_register()` and `elev_contract_add()` / `invoice_sale()` now retry with a random hex suffix (`secrets.token_hex(2)`) on `sqlite3.IntegrityError` instead of crashing when the same customer/timestamp produces the same auto-generated number twice in one day/second.
- **Stock check before sale**: `invoice_sale()` now verifies every line's `qty <= products.stock_qty` *before* writing anything; insufficient stock aborts with a flash listing which product(s) are short, instead of silently allowing negative inventory.
- **`customers()` list query fix**: "next service" now correctly filters `status='planned'` and sorts ascending (nearest upcoming), instead of `ORDER BY planned_date DESC` (which surfaced whichever visit had the *latest* date regardless of done/overdue status). Also added `building_count` and `nearest_expiry` (soonest-expiring active contract, highlighted red if already past) — a lightweight contract-renewal alert.
- **Digital signature + real photo capture**: `tech_visit_report.html` replaced the plain-text "photo note" with an actual `<canvas>` signature pad and a file input that reads the photo as base64 via `FileReader`, stored in two new `service_visits` columns (`signature_data`, `photo_data`, migrated in `init_elevator_tables()` via `ALTER TABLE ... ADD COLUMN` wrapped in try/except). A new admin-facing viewer (`elev_visit_view.html` / `/elevators/visits/view/<id>`, linked from `elev_visits.html`) renders the checklist, signature image, and photo for any completed visit.
- **Dead code removed**: `customer_add()` no longer duplicates `customer_register()`'s logic — it's now a one-line redirect to `/customers/register` (kept only so old links/bookmarks don't 404).
- Re-verified with the same test-client smoke-test approach as before, this time asserting the specific bugs are fixed (duplicate-party count, contract_no collision under same-day resubmission, unpadded-date lookup, IDOR cross-technician access, insufficient-stock sale) in addition to the full GET/POST route sweep.

## 12. Smoke test snippet (for AI after edits)

```python
import re
from app import app
c = app.test_client()

def get_csrf(client, path="/login"):
    r = client.get(path)
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode("utf-8"))
    return m.group(1) if m else None

token = get_csrf(c)
assert c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token},
               follow_redirects=True).status_code == 200
for path in ["/", "/customers", "/elevators/dashboard", "/elevators/faults", "/vouchers"]:
    assert c.get(path).status_code == 200, path
```

Note: every POST in the test client now needs a valid `csrf_token` fetched from a prior GET of the same session (see `get_csrf` above) — a bare `c.post(...)` without it will be rejected with a redirect + flash message.

End of architecture guide.
