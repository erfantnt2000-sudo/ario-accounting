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

## 12. Smoke test snippet (for AI after edits)

```python
from app import app
c = app.test_client()
assert c.post("/login", data={"username":"admin","password":"admin"}, follow_redirects=True).status_code == 200
for path in ["/", "/customers", "/elevators/dashboard", "/elevators/faults", "/vouchers"]:
    assert c.get(path).status_code == 200, path
```

End of architecture guide.
