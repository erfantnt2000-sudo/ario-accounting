# -*- coding: utf-8 -*-
"""
نرم‌افزار حسابداری آریو (Ario Accounting)
نسخه ساده و کاربردی با قابلیت‌های اصلی حسابداری مالی، اشخاص، کالا و گزارش‌ها
تفاوت با پارسیان: فقط نام و توسعه‌ی محدودتر – ظاهر و ساختار مشابه نرم‌افزارهای حسابداری فارسی
"""
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, abort
import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
import jdatetime
from werkzeug.security import generate_password_hash, check_password_hash
from database import (init_db, get_connection, get_next_voucher_no, today_jalali,
                       current_month_jalali, DB_PATH, create_indexes, normalize_jalali_date)
from elevator_models import init_elevator_tables, seed_elevator_sample

app = Flask(__name__)
_env_secret = os.environ.get("SECRET_KEY")
if _env_secret:
    app.secret_key = _env_secret
else:
    # بدون SECRET_KEY ثابت در کد: هر بار اجرا یک کلید تصادفی امن ساخته می‌شود
    # (نشست‌های قبلی با ری‌استارت باطل می‌شوند، ولی هیچ کلید قابل‌حدسی در کد نمی‌ماند)
    app.secret_key = secrets.token_hex(32)
    print("⚠️  متغیر محیطی SECRET_KEY تنظیم نشده؛ یک کلید موقت تصادفی استفاده می‌شود. "
          "برای دیپلوی واقعی حتماً SECRET_KEY را در محیط سرور تنظیم کنید.")
app.config['TEMPLATES_AUTO_RELOAD'] = not (os.environ.get('PORT') or os.environ.get('RENDER'))

# --- Performance: cache static, security headers ---
@app.after_request
def add_perf_headers(response):
    # static-like templates don't change often; short cache for assets
    if request.path.startswith("/static"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

# ---------------- CSRF Protection ----------------
def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["_csrf_token"] = token
    return token

@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token}

@app.before_request
def csrf_protect():
    if request.method == "POST":
        form_token = request.form.get("csrf_token")
        session_token = session.get("_csrf_token")
        if not form_token or not session_token or not secrets.compare_digest(form_token, session_token):
            flash("نشست شما منقضی شده یا درخواست نامعتبر است؛ لطفاً دوباره تلاش کنید.", "danger")
            return redirect(request.referrer or url_for("login"))



# Create tables on startup (important for gunicorn / Render)
try:
    init_db()
    init_elevator_tables()
    seed_elevator_sample()
    create_indexes()
except Exception as _e:
    print("init_db warning:", _e)

# ---------------- Authentication ----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") == "technician":
            flash("دسترسی فقط برای مدیر است.", "danger")
            return redirect(url_for("tech_home"))
        return f(*args, **kwargs)
    return decorated

# چک‌لیست استاندارد سرویس آسانسور
SERVICE_CHECKLIST = [
    ("door", "عملکرد درب و تیغه درب"),
    ("cabin_light", "روشنایی و فن کابین"),
    ("buttons", "دکمه‌ها و نمایشگر طبقات"),
    ("leveling", "تراز بودن کابین در طبقات"),
    ("noise", "صدای غیرعادی موتور/گیربکس"),
    ("safety", "ترمز ایمنی و گاورنر (بازرسی ظاهری)"),
    ("rails", "وضعیت ریل و کفشک"),
    ("pit", "نظافت چاهک و بررسی نشتی"),
    ("phone", "تلفن اضطراری / اینترکام"),
    ("overall", "وضعیت کلی ایمن برای بهره‌برداری"),
]



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"] if "role" in user.keys() else "admin"
            # link technician profile if role is technician
            session.pop("technician_id", None)
            if session["role"] == "technician":
                conn2 = get_connection()
                tech = conn2.execute("SELECT id FROM technicians WHERE user_id=?", (user["id"],)).fetchone()
                if not tech:
                    tech = conn2.execute("SELECT id FROM technicians WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()
                    if tech:
                        conn2.execute("UPDATE technicians SET user_id=? WHERE id=?", (user["id"], tech["id"]))
                        conn2.commit()
                if tech:
                    session["technician_id"] = tech["id"]
                conn2.close()
                flash("ورود سرویس‌کار موفقیت‌آمیز بود.", "success")
                return redirect(url_for("tech_home"))
            flash("ورود موفقیت‌آمیز بود.", "success")
            return redirect(url_for("dashboard"))
        flash("نام کاربری یا رمز عبور اشتباه است.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- Dashboard ----------------
@app.route("/")
@login_required
def dashboard():
    conn = get_connection()
    stats = {
        "accounts": conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
        "parties": conn.execute("SELECT COUNT(*) FROM parties").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "vouchers": conn.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0],
        "invoices": conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
    }
    # موجودی صندوق و بانک (ساده)
    cash = conn.execute("""
        SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM voucher_lines
        WHERE account_code LIKE '11101%'
    """).fetchone()[0]
    bank = conn.execute("""
        SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM voucher_lines
        WHERE account_code LIKE '11102%'
    """).fetchone()[0]
    conn.close()
    return render_template("dashboard.html", stats=stats, cash=cash, bank=bank, today=today_jalali())

# ---------------- حساب‌ها (کدینگ) ----------------
@app.route("/accounts")
@login_required
def accounts():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM accounts ORDER BY code"
    ).fetchall()
    conn.close()
    return render_template("accounts.html", accounts=rows)

@app.route("/accounts/add", methods=["GET", "POST"])
@login_required
def account_add():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        parent = request.form.get("parent_code") or None
        atype = request.form.get("account_type", "asset")
        desc = request.form.get("description", "")
        if not code or not name:
            flash("کد و نام حساب الزامی است.", "danger")
            return redirect(url_for("account_add"))
        try:
            conn = get_connection()
            conn.execute(
                "INSERT INTO accounts (code, name, parent_code, account_type, description) VALUES (?,?,?,?,?)",
                (code, name, parent, atype, desc)
            )
            conn.commit()
            conn.close()
            flash("حساب با موفقیت اضافه شد.", "success")
            return redirect(url_for("accounts"))
        except sqlite3.IntegrityError:
            flash("کد حساب تکراری است.", "danger")
    conn = get_connection()
    parents = conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()
    conn.close()
    return render_template("account_form.html", parents=parents, account=None)

@app.route("/accounts/edit/<int:aid>", methods=["GET", "POST"])
@login_required
def account_edit(aid):
    conn = get_connection()
    account = conn.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    if not account:
        flash("حساب یافت نشد.", "danger")
        return redirect(url_for("accounts"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        parent = request.form.get("parent_code") or None
        atype = request.form.get("account_type")
        desc = request.form.get("description", "")
        conn.execute(
            "UPDATE accounts SET name=?, parent_code=?, account_type=?, description=? WHERE id=?",
            (name, parent, atype, desc, aid)
        )
        conn.commit()
        conn.close()
        flash("حساب ویرایش شد.", "success")
        return redirect(url_for("accounts"))
    parents = conn.execute("SELECT code, name FROM accounts WHERE id!=? ORDER BY code", (aid,)).fetchall()
    conn.close()
    return render_template("account_form.html", parents=parents, account=account)

# ---------------- اشخاص ----------------
@app.route("/parties")
@login_required
def parties():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM parties ORDER BY name").fetchall()
    conn.close()
    return render_template("parties.html", parties=rows)

@app.route("/parties/add", methods=["GET", "POST"])
@login_required
def party_add():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        ptype = request.form.get("party_type", "customer")
        phone = request.form.get("phone", "")
        address = request.form.get("address", "")
        if not name:
            flash("نام الزامی است.", "danger")
            return redirect(url_for("party_add"))
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO parties (code, name, party_type, phone, address, created_at) VALUES (?,?,?,?,?,?)",
                (code or None, name, ptype, phone, address, datetime.now().isoformat())
            )
            conn.commit()
            flash("شخص با موفقیت ثبت شد.", "success")
        except Exception as e:
            flash(f"خطا: {e}", "danger")
        conn.close()
        return redirect(url_for("parties"))
    return render_template("party_form.html", party=None)

@app.route("/parties/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def party_edit(pid):
    conn = get_connection()
    party = conn.execute("SELECT * FROM parties WHERE id=?", (pid,)).fetchone()
    if not party:
        return redirect(url_for("parties"))
    if request.method == "POST":
        conn.execute(
            "UPDATE parties SET code=?, name=?, party_type=?, phone=?, address=? WHERE id=?",
            (request.form.get("code"), request.form.get("name"), request.form.get("party_type"),
             request.form.get("phone"), request.form.get("address"), pid)
        )
        conn.commit()
        conn.close()
        flash("ویرایش شد.", "success")
        return redirect(url_for("parties"))
    conn.close()
    return render_template("party_form.html", party=party)

# ---------------- کالا ----------------
@app.route("/products")
@login_required
def products():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM products ORDER BY code").fetchall()
    conn.close()
    return render_template("products.html", products=rows)

@app.route("/products/add", methods=["GET", "POST"])
@login_required
def product_add():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        unit = request.form.get("unit", "عدد")
        buy = float(request.form.get("buy_price") or 0)
        sell = float(request.form.get("sell_price") or 0)
        stock = float(request.form.get("stock_qty") or 0)
        if not code or not name:
            flash("کد و نام کالا الزامی است.", "danger")
            return redirect(url_for("product_add"))
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO products (code, name, unit, buy_price, sell_price, stock_qty) VALUES (?,?,?,?,?,?)",
                (code, name, unit, buy, sell, stock)
            )
            conn.commit()
            flash("کالا ثبت شد.", "success")
        except sqlite3.IntegrityError:
            flash("کد کالا تکراری است.", "danger")
        conn.close()
        return redirect(url_for("products"))
    return render_template("product_form.html", product=None)

@app.route("/products/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def product_edit(pid):
    conn = get_connection()
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not product:
        return redirect(url_for("products"))
    if request.method == "POST":
        conn.execute(
            """UPDATE products SET code=?, name=?, unit=?, buy_price=?, sell_price=?, stock_qty=? WHERE id=?""",
            (request.form.get("code"), request.form.get("name"), request.form.get("unit"),
             float(request.form.get("buy_price") or 0), float(request.form.get("sell_price") or 0),
             float(request.form.get("stock_qty") or 0), pid)
        )
        conn.commit()
        conn.close()
        flash("کالا ویرایش شد.", "success")
        return redirect(url_for("products"))
    conn.close()
    return render_template("product_form.html", product=product)

# ---------------- اسناد حسابداری ----------------
@app.route("/vouchers")
@login_required
def vouchers():
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.*, 
               (SELECT COALESCE(SUM(debit),0) FROM voucher_lines WHERE voucher_id=v.id) as total_debit
        FROM vouchers v ORDER BY voucher_no DESC
    """).fetchall()
    conn.close()
    return render_template("vouchers.html", vouchers=rows)

@app.route("/vouchers/add", methods=["GET", "POST"])
@login_required
def voucher_add():
    if request.method == "POST":
        vdate = normalize_jalali_date(request.form.get("voucher_date"), today_jalali())
        desc = request.form.get("description", "")
        accounts = request.form.getlist("account_code[]")
        debits = request.form.getlist("debit[]")
        credits = request.form.getlist("credit[]")
        line_descs = request.form.getlist("line_desc[]")

        total_d = sum(float(d or 0) for d in debits)
        total_c = sum(float(c or 0) for c in credits)
        if abs(total_d - total_c) > 0.01:
            flash(f"سند تراز نیست! جمع بدهکار: {total_d:,.0f} | جمع بستانکار: {total_c:,.0f}", "danger")
            return redirect(url_for("voucher_add"))

        if total_d == 0:
            flash("سند خالی است.", "danger")
            return redirect(url_for("voucher_add"))

        conn = get_connection()
        vno = get_next_voucher_no()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO vouchers (voucher_no, voucher_date, description, voucher_type, created_at) VALUES (?,?,?,?,?)",
            (vno, vdate, desc, "manual", datetime.now().isoformat())
        )
        vid = cur.lastrowid
        for i, acc in enumerate(accounts):
            if not acc:
                continue
            d = float(debits[i] or 0)
            c = float(credits[i] or 0)
            if d == 0 and c == 0:
                continue
            cur.execute(
                "INSERT INTO voucher_lines (voucher_id, account_code, description, debit, credit) VALUES (?,?,?,?,?)",
                (vid, acc, line_descs[i] if i < len(line_descs) else "", d, c)
            )
        conn.commit()
        conn.close()
        flash(f"سند شماره {vno} با موفقیت ثبت شد.", "success")
        return redirect(url_for("vouchers"))

    conn = get_connection()
    accounts = conn.execute("SELECT code, name FROM accounts WHERE length(code)>=4 ORDER BY code").fetchall()
    conn.close()
    return render_template("voucher_form.html", accounts=accounts, today=today_jalali())

@app.route("/vouchers/view/<int:vid>")
@login_required
def voucher_view(vid):
    conn = get_connection()
    v = conn.execute("SELECT * FROM vouchers WHERE id=?", (vid,)).fetchone()
    lines = conn.execute("""
        SELECT vl.*, a.name as account_name FROM voucher_lines vl
        LEFT JOIN accounts a ON a.code = vl.account_code
        WHERE vl.voucher_id=?
    """, (vid,)).fetchall()
    conn.close()
    if not v:
        flash("سند یافت نشد.", "danger")
        return redirect(url_for("vouchers"))
    return render_template("voucher_view.html", voucher=v, lines=lines)

# ---------------- فاکتور فروش ساده ----------------
@app.route("/invoices")
@login_required
def invoices():
    conn = get_connection()
    rows = conn.execute("""
        SELECT i.*, p.name as party_name FROM invoices i
        LEFT JOIN parties p ON p.id = i.party_id
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return render_template("invoices.html", invoices=rows)

@app.route("/invoices/sale", methods=["GET", "POST"])
@login_required
def invoice_sale():
    if request.method == "POST":
        party_id = request.form.get("party_id")
        idate = normalize_jalali_date(request.form.get("invoice_date"), today_jalali())
        desc = request.form.get("description", "")
        product_ids = request.form.getlist("product_id[]")
        qtys = request.form.getlist("qty[]")
        prices = request.form.getlist("unit_price[]")
        line_discounts = request.form.getlist("line_discount[]")
        tax_percent = float(request.form.get("tax_percent") or 0)
        invoice_discount = float(request.form.get("invoice_discount") or 0)

        if not party_id or not product_ids:
            flash("مشتری و حداقل یک کالا الزامی است.", "danger")
            return redirect(url_for("invoice_sale"))

        subtotal = 0
        lines_data = []
        for i, pid in enumerate(product_ids):
            if not pid:
                continue
            q = float(qtys[i] or 0)
            p = float(prices[i] or 0)
            ld = float(line_discounts[i] or 0) if i < len(line_discounts) else 0
            amt = max(q * p - ld, 0)
            subtotal += amt
            lines_data.append((int(pid), q, p, ld, amt))

        if subtotal == 0:
            flash("مبلغ فاکتور صفر است.", "danger")
            return redirect(url_for("invoice_sale"))

        # بررسی کفایت موجودی قبل از هرگونه ثبت (جلوگیری از موجودی منفی)
        conn = get_connection()
        insufficient = []
        for pid, q, p, ld, amt in lines_data:
            prod = conn.execute("SELECT name, stock_qty FROM products WHERE id=?", (pid,)).fetchone()
            if prod and q > prod["stock_qty"]:
                insufficient.append(f"{prod['name']} (موجودی: {prod['stock_qty']:g}، درخواست: {q:g})")
        if insufficient:
            conn.close()
            flash("موجودی کافی نیست: " + "، ".join(insufficient), "danger")
            return redirect(url_for("invoice_sale"))

        after_discount = max(subtotal - invoice_discount, 0)
        tax_amount = round(after_discount * tax_percent / 100)
        final_total = after_discount + tax_amount

        cur = conn.cursor()
        inv_no = f"S-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        # ثبت فاکتور (با تلاش مجدد در صورت برخورد نادر شماره فاکتور)
        for attempt in range(5):
            try:
                cur.execute(
                    """INSERT INTO invoices (invoice_no, invoice_type, invoice_date, party_id, description,
                       total_amount, discount, tax, final_amount, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (inv_no, "sale", idate, party_id, desc, subtotal, invoice_discount, tax_amount, final_total, datetime.now().isoformat())
                )
                break
            except sqlite3.IntegrityError:
                inv_no = f"S-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2)}"
        iid = cur.lastrowid
        for pid, q, p, ld, amt in lines_data:
            cur.execute(
                "INSERT INTO invoice_lines (invoice_id, product_id, qty, unit_price, discount, amount) VALUES (?,?,?,?,?,?)",
                (iid, pid, q, p, ld, amt)
            )
            # کاهش موجودی
            cur.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id=?", (q, pid))

        # ثبت سند حسابداری خودکار
        vno = get_next_voucher_no()
        cur.execute(
            "INSERT INTO vouchers (voucher_no, voucher_date, description, voucher_type, created_at) VALUES (?,?,?,?,?)",
            (vno, idate, f"فاکتور فروش {inv_no}", "sale", datetime.now().isoformat())
        )
        vid = cur.lastrowid
        # بدهکار: بدهکاران
        cur.execute(
            "INSERT INTO voucher_lines (voucher_id, account_code, description, debit, credit) VALUES (?,?,?,?,?)",
            (vid, "11201", f"فروش به مشتری - {inv_no}", final_total, 0)
        )
        # بستانکار: فروش
        cur.execute(
            "INSERT INTO voucher_lines (voucher_id, account_code, description, debit, credit) VALUES (?,?,?,?,?)",
            (vid, "4101", f"فروش کالا - {inv_no}", 0, subtotal - invoice_discount)
        )
        if tax_amount:
            cur.execute(
                "INSERT INTO voucher_lines (voucher_id, account_code, description, debit, credit) VALUES (?,?,?,?,?)",
                (vid, "21301", f"مالیات بر ارزش افزوده - {inv_no}", 0, tax_amount)
            )
        cur.execute("UPDATE invoices SET voucher_id=? WHERE id=?", (vid, iid))
        conn.commit()
        conn.close()
        flash(f"فاکتور فروش {inv_no} و سند مربوطه ثبت شد.", "success")
        return redirect(url_for("invoice_view", iid=iid))

    conn = get_connection()
    parties = conn.execute("SELECT id, name, phone, address FROM parties WHERE party_type IN ('customer','both')").fetchall()
    products = conn.execute("SELECT id, code, name, sell_price, stock_qty, unit FROM products WHERE is_active=1").fetchall()
    conn.close()
    next_no = f"S-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return render_template("invoice_sale.html", parties=parties, products=products, today=today_jalali(), next_no=next_no)

@app.route("/invoices/view/<int:iid>")
@login_required
def invoice_view(iid):
    conn = get_connection()
    inv = conn.execute("""
        SELECT i.*, p.name as party_name, p.phone as party_phone, p.address as party_address, p.national_id
        FROM invoices i LEFT JOIN parties p ON p.id = i.party_id
        WHERE i.id = ?
    """, (iid,)).fetchone()
    if not inv:
        flash("فاکتور یافت نشد.", "danger")
        return redirect(url_for("invoices"))
    lines = conn.execute("""
        SELECT il.*, pr.code as product_code, pr.name as product_name, pr.unit
        FROM invoice_lines il LEFT JOIN products pr ON pr.id = il.product_id
        WHERE il.invoice_id = ?
    """, (iid,)).fetchall()
    conn.close()
    return render_template("invoice_view.html", inv=inv, lines=lines, today=today_jalali())

# ---------------- گزارش‌ها ----------------
@app.route("/reports/trial-balance")
@login_required
def trial_balance():
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.code, a.name, a.account_type,
               COALESCE(SUM(vl.debit),0) as total_debit,
               COALESCE(SUM(vl.credit),0) as total_credit
        FROM accounts a
        LEFT JOIN voucher_lines vl ON vl.account_code = a.code
        GROUP BY a.code, a.name, a.account_type
        HAVING total_debit > 0 OR total_credit > 0 OR length(a.code) <= 3
        ORDER BY a.code
    """).fetchall()
    # محاسبه مانده
    result = []
    total_d = total_c = 0
    for r in rows:
        bal_d = max(0, r["total_debit"] - r["total_credit"])
        bal_c = max(0, r["total_credit"] - r["total_debit"])
        result.append({
            "code": r["code"], "name": r["name"], "type": r["account_type"],
            "debit": r["total_debit"], "credit": r["total_credit"],
            "bal_debit": bal_d, "bal_credit": bal_c
        })
        total_d += bal_d
        total_c += bal_c
    conn.close()
    return render_template("trial_balance.html", rows=result, total_d=total_d, total_c=total_c)

@app.route("/reports/journal")
@login_required
def journal():
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.voucher_no, v.voucher_date, v.description as vdesc,
               vl.account_code, a.name as account_name, vl.description, vl.debit, vl.credit
        FROM voucher_lines vl
        JOIN vouchers v ON v.id = vl.voucher_id
        LEFT JOIN accounts a ON a.code = vl.account_code
        ORDER BY v.voucher_no, vl.id
    """).fetchall()
    conn.close()
    return render_template("journal.html", rows=rows)

@app.route("/reports/profit-loss")
@login_required
def profit_loss():
    conn = get_connection()
    revenue = conn.execute("""
        SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM voucher_lines
        WHERE account_code LIKE '4%'
    """).fetchone()[0]
    expense = conn.execute("""
        SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM voucher_lines
        WHERE account_code LIKE '5%'
    """).fetchone()[0]
    conn.close()
    profit = revenue - expense
    return render_template("profit_loss.html", revenue=revenue, expense=expense, profit=profit)

# ---------------- Main ----------------

# ==================== ماژول مشتریان و نوبت‌ها ====================

@app.route("/customers")
@login_required
def customers():
    """لیست کارفرماها با قرارداد و ساختمان (ویژه شرکت آسانسور)"""
    today = today_jalali()
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.id, p.code, p.name, p.phone, p.address,
               (SELECT COUNT(*) FROM contracts c WHERE c.party_id=p.id AND c.status='active') as active_contracts,
               (SELECT COALESCE(SUM(c.amount),0) FROM contracts c WHERE c.party_id=p.id) as total_contract,
               (SELECT COALESCE(SUM(pay.amount),0) FROM payments pay WHERE pay.party_id=p.id) as total_paid,
               (SELECT COUNT(*) FROM buildings b WHERE b.party_id=p.id) as building_count,
               (SELECT b.name FROM buildings b WHERE b.party_id=p.id ORDER BY b.id DESC LIMIT 1) as building_name,
               (SELECT c.end_date FROM contracts c WHERE c.party_id=p.id AND c.status='active' ORDER BY c.end_date ASC LIMIT 1) as nearest_expiry,
               (SELECT v.planned_date FROM service_visits v
                    JOIN contracts c2 ON c2.id=v.contract_id
                    WHERE c2.party_id=p.id AND v.status='planned'
                    ORDER BY v.planned_date ASC LIMIT 1) as next_service
        FROM parties p
        WHERE p.party_type IN ('customer', 'both') AND p.is_active=1
        ORDER BY p.name
    """).fetchall()
    conn.close()
    return render_template("customers.html", customers=rows, today=today)


@app.route("/customers/add", methods=["GET", "POST"])
@login_required
def customer_add():
    """
    این مسیر با فرم یکپارچه‌ی /customers/register جایگزین شده (که هم‌زمان کارفرما، ساختمان،
    آسانسور و قرارداد را ثبت می‌کند و از تکراری‌شدن مشتری هم جلوگیری می‌کند)؛ برای سازگاری با
    لینک‌های قدیمی، این مسیر صرفاً کاربر را به همان فرم هدایت می‌کند.
    """
    return redirect(url_for("customer_register"))

@app.route("/customers/edit/<int:cid>", methods=["GET", "POST"])
@login_required
def customer_edit(cid):
    conn = get_connection()
    customer = conn.execute("SELECT * FROM parties WHERE id=?", (cid,)).fetchone()
    if not customer:
        flash("مشتری یافت نشد.", "danger")
        return redirect(url_for("customers"))
    if request.method == "POST":
        conn.execute(
            "UPDATE parties SET code=?, name=?, phone=?, address=?, notes=? WHERE id=?",
            (request.form.get("code"), request.form.get("name"), request.form.get("phone"),
             request.form.get("address"), request.form.get("notes"), cid)
        )
        conn.commit()
        conn.close()
        flash("ویرایش شد.", "success")
        return redirect(url_for("customers"))
    conn.close()
    return render_template("customer_form.html", customer=customer, today=today_jalali())


@app.route("/customers/register", methods=["GET", "POST"])
@login_required
def customer_register():
    """ثبت یکجای کارفرما + ساختمان + آسانسور + قرارداد + نوبت سرویس"""
    if request.method == "POST":
        existing_party_id = request.form.get("existing_party_id") or None
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        address = (request.form.get("address") or "").strip()
        building_name = (request.form.get("building_name") or "").strip()
        elev_code = (request.form.get("elev_code") or "").strip()
        elev_brand = (request.form.get("elev_brand") or "").strip()
        elev_stops = int(request.form.get("elev_stops") or 0)
        contract_no = (request.form.get("contract_no") or "").strip()
        start_date = normalize_jalali_date(request.form.get("start_date"), today_jalali())
        end_date = normalize_jalali_date(request.form.get("end_date"))
        amount = float(request.form.get("amount") or 0)
        visit_per_month = int(request.form.get("visit_per_month") or 1)
        first_service = normalize_jalali_date(request.form.get("first_service"), start_date)
        tech_id = request.form.get("technician_id") or None
        notes = (request.form.get("notes") or "").strip()

        if not existing_party_id and not name:
            flash("نام کارفرما الزامی است (یا یک کارفرمای موجود را انتخاب کنید).", "danger")
            return redirect(url_for("customer_register"))
        if not building_name:
            flash("نام ساختمان الزامی است.", "danger")
            return redirect(url_for("customer_register"))
        if not end_date:
            flash("تاریخ پایان قرارداد نامعتبر یا خالی است (فرمت صحیح: 1404/06/15).", "danger")
            return redirect(url_for("customer_register"))

        conn = get_connection()
        cur = conn.cursor()
        try:
            # کارفرما: استفاده از رکورد موجود یا ساخت کارفرمای جدید (جلوگیری از ثبت تکراری)
            if existing_party_id:
                party_id = int(existing_party_id)
                party_row = cur.execute("SELECT id FROM parties WHERE id=?", (party_id,)).fetchone()
                if not party_row:
                    raise ValueError("کارفرمای انتخاب‌شده یافت نشد.")
            else:
                cur.execute(
                    "INSERT INTO parties (name, party_type, phone, address, notes, created_at) VALUES (?,?,?,?,?,?)",
                    (name, "customer", phone, address, notes, datetime.now().isoformat())
                )
                party_id = cur.lastrowid

            cur.execute(
                "INSERT INTO buildings (code, name, address, party_id, created_at) VALUES (?,?,?,?,?)",
                (None, building_name, address, party_id, datetime.now().isoformat())
            )
            building_id = cur.lastrowid
            if not elev_code:
                elev_code = f"EL-{party_id:04d}-{building_id:04d}"
            cur.execute(
                """INSERT INTO elevators (building_id, code, name, brand, stops, status, notes, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (building_id, elev_code, f"آسانسور {building_name}", elev_brand, elev_stops, "active", notes, datetime.now().isoformat())
            )
            elev_id = cur.lastrowid

            # شماره قرارداد: تضمین یکتایی واقعی با پسوند تصادفی + تلاش مجدد در صورت برخورد
            base_contract_no = contract_no or f"CT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            final_contract_no = base_contract_no
            for attempt in range(5):
                try:
                    cur.execute(
                        """INSERT INTO contracts (contract_no, party_id, building_id, elevator_id, start_date, end_date,
                           amount, visit_per_month, payment_type, status, description, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (final_contract_no, party_id, building_id, elev_id, start_date, end_date, amount,
                         visit_per_month, "monthly", "active", notes, datetime.now().isoformat())
                    )
                    break
                except sqlite3.IntegrityError:
                    final_contract_no = f"{base_contract_no}-{secrets.token_hex(2)}"
            else:
                raise ValueError("امکان تولید شماره قرارداد یکتا وجود نداشت؛ دوباره تلاش کنید.")
            contract_id = cur.lastrowid
            contract_no = final_contract_no

            cur.execute(
                """INSERT INTO service_visits (contract_id, elevator_id, technician_id, planned_date, visit_type, status, amount, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (contract_id, elev_id, tech_id, first_service, "periodic", "planned", amount / max(visit_per_month * 12, 1), datetime.now().isoformat())
            )
            conn.commit()
            flash(f"ثبت شد: {name or ''} — {building_name} — قرارداد {contract_no}", "success")
            return redirect(url_for("customers"))
        except Exception as e:
            conn.rollback()
            flash(f"خطا در ثبت: {e}", "danger")
            return redirect(url_for("customer_register"))
        finally:
            conn.close()

    conn = get_connection()
    techs = conn.execute("SELECT id, name FROM technicians WHERE is_active=1 ORDER BY name").fetchall()
    parties = conn.execute("""
        SELECT id, name, phone FROM parties WHERE party_type IN ('customer','both') AND is_active=1 ORDER BY name
    """).fetchall()
    conn.close()
    return render_template("customer_register.html", techs=techs, parties=parties, today=today_jalali())


@app.route("/appointments/today")
@login_required
def appointments_today():
    """نوبت‌های امروز + تیک سرویس انجام‌شده"""
    today = today_jalali()
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, p.name as customer_name, p.phone
        FROM appointments a
        JOIN parties p ON p.id = a.party_id
        WHERE a.appt_date = ?
        ORDER BY a.appt_time, a.id
    """, (today,)).fetchall()
    customers = conn.execute("SELECT id, name FROM parties WHERE party_type IN ('customer','both') AND is_active=1 ORDER BY name").fetchall()
    conn.close()
    return render_template("appointments_today.html", appointments=rows, customers=customers, today=today)

@app.route("/appointments/add", methods=["POST"])
@login_required
def appointment_add():
    party_id = request.form.get("party_id")
    appt_date = normalize_jalali_date(request.form.get("appt_date"), today_jalali())
    appt_time = request.form.get("appt_time", "")
    service_type = request.form.get("service_type", "")
    description = request.form.get("description", "")
    amount = float(request.form.get("amount") or 0)
    if not party_id:
        flash("انتخاب مشتری الزامی است.", "danger")
        return redirect(url_for("appointments_today"))
    conn = get_connection()
    conn.execute(
        "INSERT INTO appointments (party_id, appt_date, appt_time, service_type, description, amount, is_done, created_at) VALUES (?,?,?,?,?,?,0,?)",
        (party_id, appt_date, appt_time, service_type, description, amount, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    flash("نوبت ثبت شد.", "success")
    return redirect(url_for("appointments_today"))

@app.route("/appointments/toggle/<int:aid>", methods=["POST"])
@login_required
def appointment_toggle(aid):
    """تیک زدن سرویس انجام‌شده"""
    conn = get_connection()
    row = conn.execute("SELECT is_done FROM appointments WHERE id=?", (aid,)).fetchone()
    if row:
        new_val = 0 if row["is_done"] else 1
        done_at = datetime.now().isoformat() if new_val else None
        conn.execute("UPDATE appointments SET is_done=?, done_at=? WHERE id=?", (new_val, done_at, aid))
        conn.commit()
    conn.close()
    return redirect(url_for("appointments_today"))

@app.route("/appointments/noshow")
@login_required
def appointments_noshow():
    """مشتریانی که در ماه جاری نوبت داشتند ولی نیامدند (سرویس انجام نشده)"""
    month = request.args.get("month") or current_month_jalali()
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, p.name as customer_name, p.phone
        FROM appointments a
        JOIN parties p ON p.id = a.party_id
        WHERE a.appt_date LIKE ? AND a.is_done = 0
        ORDER BY a.appt_date, a.appt_time
    """, (month + "%",)).fetchall()
    conn.close()
    return render_template("appointments_noshow.html", appointments=rows, month=month, today=today_jalali())

@app.route("/payments")
@login_required
def payments_list():
    """پرداختی‌ها و بدهکاری مشتریان - ماهانه"""
    month = request.args.get("month") or current_month_jalali()
    conn = get_connection()
    # پرداخت‌های ماه
    pays = conn.execute("""
        SELECT pay.*, p.name as customer_name
        FROM payments pay
        JOIN parties p ON p.id = pay.party_id
        WHERE pay.pay_date LIKE ?
        ORDER BY pay.pay_date DESC
    """, (month + "%",)).fetchall()
    # خلاصه بدهی هر مشتری (جمع سرویس‌های انجام‌شده - جمع پرداخت‌ها)
    debts = conn.execute("""
        SELECT p.id, p.name, p.phone,
               COALESCE((SELECT SUM(amount) FROM appointments a WHERE a.party_id=p.id AND a.is_done=1), 0) as total_service,
               COALESCE((SELECT SUM(amount) FROM payments pay WHERE pay.party_id=p.id), 0) as total_paid
        FROM parties p
        WHERE p.party_type IN ('customer','both') AND p.is_active=1
        ORDER BY p.name
    """).fetchall()
    customers = conn.execute("SELECT id, name FROM parties WHERE party_type IN ('customer','both') AND is_active=1 ORDER BY name").fetchall()
    conn.close()
    debt_list = []
    for d in debts:
        balance = (d["total_service"] or 0) - (d["total_paid"] or 0)
        debt_list.append({
            "id": d["id"], "name": d["name"], "phone": d["phone"],
            "total_service": d["total_service"] or 0,
            "total_paid": d["total_paid"] or 0,
            "balance": balance
        })
    return render_template("payments.html", payments=pays, debts=debt_list, customers=customers, month=month, today=today_jalali())

@app.route("/payments/add", methods=["POST"])
@login_required
def payment_add():
    party_id = request.form.get("party_id")
    pay_date = normalize_jalali_date(request.form.get("pay_date"), today_jalali())
    amount = float(request.form.get("amount") or 0)
    method = request.form.get("method", "cash")
    description = request.form.get("description", "")
    if not party_id or amount <= 0:
        flash("مشتری و مبلغ معتبر الزامی است.", "danger")
        return redirect(url_for("payments_list"))
    conn = get_connection()
    conn.execute(
        "INSERT INTO payments (party_id, pay_date, amount, method, description, created_at) VALUES (?,?,?,?,?,?)",
        (party_id, pay_date, amount, method, description, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    flash("پرداخت ثبت شد.", "success")
    return redirect(url_for("payments_list"))



# ==================== مدیریت سرویس آسانسور ====================

@app.route("/elevators/dashboard")
@login_required
def elev_dashboard():
    """داشبورد مدیر: قراردادهای رو به پایان، بدهی، سرویس عقب‌افتاده"""
    conn = get_connection()
    today = today_jalali()
    # contracts ending in 30 days (string compare works for YYYY/MM/DD jalali roughly)
    expiring = conn.execute("""
        SELECT c.*, p.name as customer_name, b.name as building_name, e.code as elev_code
        FROM contracts c
        LEFT JOIN parties p ON p.id=c.party_id
        LEFT JOIN buildings b ON b.id=c.building_id
        LEFT JOIN elevators e ON e.id=c.elevator_id
        WHERE c.status='active' AND c.end_date >= ? 
        ORDER BY c.end_date LIMIT 20
    """, (today,)).fetchall()
    overdue_visits = conn.execute("""
        SELECT v.*, e.code as elev_code, e.name as elev_name, t.name as tech_name
        FROM service_visits v
        LEFT JOIN elevators e ON e.id=v.elevator_id
        LEFT JOIN technicians t ON t.id=v.technician_id
        WHERE v.status='planned' AND v.planned_date < ?
        ORDER BY v.planned_date LIMIT 30
    """, (today,)).fetchall()
    open_faults = conn.execute("""
        SELECT f.*, e.code as elev_code, e.name as elev_name
        FROM faults f
        LEFT JOIN elevators e ON e.id=f.elevator_id
        WHERE f.status IN ('open','dispatched')
        ORDER BY f.report_date DESC LIMIT 20
    """).fetchall()
    stats = {
        "complexes": conn.execute("SELECT COUNT(*) FROM complexes").fetchone()[0],
        "buildings": conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0],
        "elevators": conn.execute("SELECT COUNT(*) FROM elevators").fetchone()[0],
        "contracts": conn.execute("SELECT COUNT(*) FROM contracts WHERE status='active'").fetchone()[0],
        "open_faults": conn.execute("SELECT COUNT(*) FROM faults WHERE status IN ('open','dispatched')").fetchone()[0],
        "overdue": len(overdue_visits),
    }
    conn.close()
    return render_template("elev_dashboard.html", stats=stats, expiring=expiring,
                           overdue_visits=overdue_visits, open_faults=open_faults, today=today)

@app.route("/elevators/complexes")
@login_required
def elev_complexes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM complexes ORDER BY name").fetchall()
    conn.close()
    return render_template("elev_complexes.html", rows=rows, today=today_jalali())

@app.route("/elevators/complexes/add", methods=["GET", "POST"])
@login_required
def elev_complex_add():
    if request.method == "POST":
        conn = get_connection()
        conn.execute(
            "INSERT INTO complexes (code,name,address,city,manager_name,manager_phone,notes,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (request.form.get("code"), request.form.get("name"), request.form.get("address"),
             request.form.get("city"), request.form.get("manager_name"), request.form.get("manager_phone"),
             request.form.get("notes"), datetime.now().isoformat())
        )
        conn.commit(); conn.close()
        flash("مجتمع ثبت شد.", "success")
        return redirect(url_for("elev_complexes"))
    return render_template("elev_complex_form.html", row=None, today=today_jalali())

@app.route("/elevators/buildings")
@login_required
def elev_buildings():
    conn = get_connection()
    rows = conn.execute("""
        SELECT b.*, c.name as complex_name, p.name as customer_name
        FROM buildings b
        LEFT JOIN complexes c ON c.id=b.complex_id
        LEFT JOIN parties p ON p.id=b.party_id
        ORDER BY b.name
    """).fetchall()
    conn.close()
    return render_template("elev_buildings.html", rows=rows, today=today_jalali())

@app.route("/elevators/buildings/add", methods=["GET", "POST"])
@login_required
def elev_building_add():
    conn = get_connection()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO buildings (complex_id,code,name,address,floors,units,party_id,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (request.form.get("complex_id") or None, request.form.get("code"), request.form.get("name"),
             request.form.get("address"), int(request.form.get("floors") or 0), int(request.form.get("units") or 0),
             request.form.get("party_id") or None, request.form.get("notes"), datetime.now().isoformat())
        )
        conn.commit(); conn.close()
        flash("ساختمان ثبت شد.", "success")
        return redirect(url_for("elev_buildings"))
    complexes = conn.execute("SELECT id,name FROM complexes ORDER BY name").fetchall()
    parties = conn.execute("SELECT id,name FROM parties WHERE party_type IN ('customer','both')").fetchall()
    conn.close()
    return render_template("elev_building_form.html", complexes=complexes, parties=parties, today=today_jalali())

@app.route("/elevators/list")
@login_required
def elev_list():
    conn = get_connection()
    rows = conn.execute("""
        SELECT e.*, b.name as building_name, c.name as complex_name
        FROM elevators e
        LEFT JOIN buildings b ON b.id=e.building_id
        LEFT JOIN complexes c ON c.id=b.complex_id
        ORDER BY e.code
    """).fetchall()
    conn.close()
    return render_template("elev_list.html", rows=rows, today=today_jalali())

@app.route("/elevators/add", methods=["GET", "POST"])
@login_required
def elev_add():
    conn = get_connection()
    if request.method == "POST":
        conn.execute(
            """INSERT INTO elevators (building_id,code,name,brand,model,capacity,stops,drive_type,door_type,status,notes,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (request.form.get("building_id"), request.form.get("code"), request.form.get("name"),
             request.form.get("brand"), request.form.get("model"), request.form.get("capacity"),
             int(request.form.get("stops") or 0), request.form.get("drive_type"), request.form.get("door_type"),
             request.form.get("status") or "active", request.form.get("notes"), datetime.now().isoformat())
        )
        conn.commit(); conn.close()
        flash("پرونده آسانسور ثبت شد.", "success")
        return redirect(url_for("elev_list"))
    buildings = conn.execute("SELECT id,name FROM buildings ORDER BY name").fetchall()
    conn.close()
    return render_template("elev_form.html", buildings=buildings, today=today_jalali())

@app.route("/elevators/contracts")
@login_required
def elev_contracts():
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.*, p.name as customer_name, b.name as building_name, e.code as elev_code
        FROM contracts c
        LEFT JOIN parties p ON p.id=c.party_id
        LEFT JOIN buildings b ON b.id=c.building_id
        LEFT JOIN elevators e ON e.id=c.elevator_id
        ORDER BY c.end_date
    """).fetchall()
    conn.close()
    return render_template("elev_contracts.html", rows=rows, today=today_jalali())

@app.route("/elevators/contracts/add", methods=["GET", "POST"])
@login_required
def elev_contract_add():
    conn = get_connection()
    if request.method == "POST":
        start_date = normalize_jalali_date(request.form.get("start_date"))
        end_date = normalize_jalali_date(request.form.get("end_date"))
        if not start_date or not end_date:
            conn.close()
            flash("تاریخ شروع/پایان قرارداد نامعتبر است (فرمت صحیح: 1404/06/15).", "danger")
            return redirect(url_for("elev_contract_add"))
        contract_no = (request.form.get("contract_no") or "").strip() or f"CT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            conn.execute(
                """INSERT INTO contracts (contract_no,party_id,building_id,elevator_id,start_date,end_date,amount,visit_per_month,payment_type,status,description,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (contract_no, request.form.get("party_id") or None,
                 request.form.get("building_id") or None, request.form.get("elevator_id") or None,
                 start_date, end_date,
                 float(request.form.get("amount") or 0), int(request.form.get("visit_per_month") or 1),
                 request.form.get("payment_type") or "monthly", "active",
                 request.form.get("description"), datetime.now().isoformat())
            )
            conn.commit()
            flash("قرارداد ثبت شد.", "success")
        except sqlite3.IntegrityError:
            flash(f"شماره قرارداد «{contract_no}» تکراری است؛ لطفاً شماره دیگری وارد کنید یا آن را خالی بگذارید.", "danger")
        conn.close()
        return redirect(url_for("elev_contracts"))
    parties = conn.execute("SELECT id,name FROM parties WHERE party_type IN ('customer','both')").fetchall()
    buildings = conn.execute("SELECT id,name FROM buildings").fetchall()
    elevators = conn.execute("SELECT id,code,name FROM elevators").fetchall()
    conn.close()
    return render_template("elev_contract_form.html", parties=parties, buildings=buildings, elevators=elevators, today=today_jalali())

@app.route("/elevators/visits")
@login_required
def elev_visits():
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.*, e.code as elev_code, e.name as elev_name, t.name as tech_name
        FROM service_visits v
        LEFT JOIN elevators e ON e.id=v.elevator_id
        LEFT JOIN technicians t ON t.id=v.technician_id
        ORDER BY v.planned_date DESC LIMIT 100
    """).fetchall()
    techs = conn.execute("SELECT id,name FROM technicians WHERE is_active=1").fetchall()
    elevators = conn.execute("SELECT id,code,name FROM elevators").fetchall()
    contracts = conn.execute("SELECT id,contract_no FROM contracts WHERE status='active'").fetchall()
    conn.close()
    return render_template("elev_visits.html", rows=rows, techs=techs, elevators=elevators, contracts=contracts, today=today_jalali())

@app.route("/elevators/visits/view/<int:vid>")
@login_required
def elev_visit_view(vid):
    """مشاهده گزارش کامل یک بازدید انجام‌شده: چک‌لیست، امضای دیجیتال، عکس مستندات"""
    conn = get_connection()
    visit = conn.execute("""
        SELECT v.*, e.code as elev_code, e.name as elev_name, b.name as building_name, b.address as building_address,
               p.name as customer_name, p.phone as customer_phone, t.name as tech_name
        FROM service_visits v
        LEFT JOIN elevators e ON e.id=v.elevator_id
        LEFT JOIN buildings b ON b.id=e.building_id
        LEFT JOIN contracts c ON c.id=v.contract_id
        LEFT JOIN parties p ON p.id=COALESCE(c.party_id, b.party_id)
        LEFT JOIN technicians t ON t.id=v.technician_id
        WHERE v.id=?
    """, (vid,)).fetchone()
    if not visit:
        conn.close()
        flash("بازدید یافت نشد.", "danger")
        return redirect(url_for("elev_visits"))
    checklist = conn.execute("SELECT * FROM visit_checklist WHERE visit_id=?", (vid,)).fetchall()
    conn.close()
    return render_template("elev_visit_view.html", visit=visit, checklist=checklist, today=today_jalali())

@app.route("/elevators/visits/add", methods=["POST"])
@login_required
def elev_visit_add():
    conn = get_connection()
    conn.execute(
        """INSERT INTO service_visits (contract_id,elevator_id,technician_id,planned_date,visit_type,status,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (request.form.get("contract_id") or None, request.form.get("elevator_id"),
         request.form.get("technician_id") or None, normalize_jalali_date(request.form.get("planned_date"), today_jalali()),
         request.form.get("visit_type") or "periodic", "planned", datetime.now().isoformat())
    )
    conn.commit(); conn.close()
    flash("بازدید برنامه‌ریزی شد.", "success")
    next_url = request.form.get("next")
    if next_url:
        return redirect(next_url)
    return redirect(url_for("elev_visits"))

@app.route("/elevators/visits/done/<int:vid>", methods=["POST"])
@login_required
def elev_visit_done(vid):
    conn = get_connection()
    conn.execute(
        "UPDATE service_visits SET status='done', visit_date=?, report_text=?, customer_sign=? WHERE id=?",
        (normalize_jalali_date(request.form.get("visit_date"), today_jalali()), request.form.get("report_text"),
         request.form.get("customer_sign"), vid)
    )
    conn.commit(); conn.close()
    flash("گزارش بازدید ثبت شد.", "success")
    return redirect(url_for("elev_visits"))

@app.route("/elevators/today")
@login_required
def elev_today():
    """نوبت امروز آسانسور: ورود تاریخ/جستجوی مشتری و نمایش سرویس‌های آن روز با امکان تیک زدن"""
    date_q = (request.args.get("date") or today_jalali()).strip()
    q = (request.args.get("q") or "").strip()
    conn = get_connection()
    sql = """
        SELECT v.*, e.code as elev_code, e.name as elev_name, e.capacity, e.stops,
               b.name as building_name, b.address as building_address,
               cx.name as complex_name,
               p.name as customer_name, p.phone as customer_phone,
               t.name as tech_name, c.contract_no
        FROM service_visits v
        LEFT JOIN elevators e ON e.id = v.elevator_id
        LEFT JOIN buildings b ON b.id = e.building_id
        LEFT JOIN complexes cx ON cx.id = b.complex_id
        LEFT JOIN contracts c ON c.id = v.contract_id
        LEFT JOIN parties p ON p.id = COALESCE(c.party_id, b.party_id)
        LEFT JOIN technicians t ON t.id = v.technician_id
        WHERE v.planned_date = ?
    """
    params = [date_q]
    if q:
        sql += " AND (p.name LIKE ? OR b.name LIKE ? OR e.code LIKE ? OR e.name LIKE ? OR cx.name LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like, like]
    sql += " ORDER BY (CASE WHEN v.status='done' THEN 1 ELSE 0 END), b.name, e.code"
    rows = conn.execute(sql, params).fetchall()

    stats = {"total": len(rows)}
    stats["done"] = sum(1 for r in rows if r["status"] == "done")
    stats["pending"] = stats["total"] - stats["done"]

    elevators = conn.execute("""
        SELECT e.id, e.code, e.name, b.name as building_name
        FROM elevators e LEFT JOIN buildings b ON b.id = e.building_id
        WHERE e.status='active' ORDER BY b.name, e.code
    """).fetchall()
    techs = conn.execute("SELECT id,name FROM technicians WHERE is_active=1 ORDER BY name").fetchall()
    contracts = conn.execute("SELECT id, contract_no FROM contracts WHERE status='active' ORDER BY contract_no").fetchall()
    conn.close()
    return render_template("elev_today.html", rows=rows, stats=stats, date_q=date_q, q=q,
                           elevators=elevators, techs=techs, contracts=contracts, today=today_jalali())

@app.route("/elevators/visits/quick_done/<int:vid>", methods=["POST"])
@login_required
def elev_visit_quick_done(vid):
    """تیک زدن سریع انجام سرویس از صفحه نوبت امروز"""
    conn = get_connection()
    row = conn.execute("SELECT status, planned_date FROM service_visits WHERE id=?", (vid,)).fetchone()
    if row:
        if row["status"] == "done":
            conn.execute("UPDATE service_visits SET status='planned', visit_date=NULL WHERE id=?", (vid,))
        else:
            conn.execute(
                "UPDATE service_visits SET status='done', visit_date=? WHERE id=?",
                (today_jalali(), vid)
            )
        conn.commit()
    conn.close()
    next_url = request.form.get("next") or url_for("elev_today")
    return redirect(next_url)

@app.route("/elevators/missed")
@login_required
def elev_missed():
    """لیست سرویس‌هایی که در تاریخ برنامه‌ریزی‌شده انجام نشده‌اند (نوبت‌های عقب‌افتاده)"""
    today = today_jalali()
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.*, e.code as elev_code, e.name as elev_name,
               b.name as building_name, b.address as building_address,
               p.name as customer_name, p.phone as customer_phone,
               t.name as tech_name, c.contract_no
        FROM service_visits v
        LEFT JOIN elevators e ON e.id = v.elevator_id
        LEFT JOIN buildings b ON b.id = e.building_id
        LEFT JOIN contracts c ON c.id = v.contract_id
        LEFT JOIN parties p ON p.id = COALESCE(c.party_id, b.party_id)
        LEFT JOIN technicians t ON t.id = v.technician_id
        WHERE v.status = 'planned' AND v.planned_date < ?
        ORDER BY v.planned_date DESC
    """, (today,)).fetchall()
    conn.close()
    return render_template("elev_missed.html", rows=rows, today=today)

@app.route("/elevators/visits/reschedule/<int:vid>", methods=["POST"])
@login_required
def elev_visit_reschedule(vid):
    """تعیین تاریخ جدید برای نوبت انجام‌نشده"""
    new_date = normalize_jalali_date(request.form.get("new_date"), today_jalali())
    conn = get_connection()
    conn.execute("UPDATE service_visits SET planned_date=? WHERE id=?", (new_date, vid))
    conn.commit()
    conn.close()
    flash("نوبت به تاریخ جدید موکول شد.", "success")
    return redirect(url_for("elev_missed"))

@app.route("/elevators/faults")
@login_required
def elev_faults():
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, e.code as elev_code, e.name as elev_name, t.name as tech_name
        FROM faults f
        LEFT JOIN elevators e ON e.id=f.elevator_id
        LEFT JOIN technicians t ON t.id=f.technician_id
        ORDER BY f.id DESC LIMIT 100
    """).fetchall()
    elevators = conn.execute("SELECT id,code,name FROM elevators").fetchall()
    techs = conn.execute("SELECT id,name FROM technicians WHERE is_active=1").fetchall()
    conn.close()
    return render_template("elev_faults.html", rows=rows, elevators=elevators, techs=techs, today=today_jalali())

@app.route("/elevators/faults/add", methods=["POST"])
@login_required
def elev_fault_add():
    conn = get_connection()
    conn.execute(
        """INSERT INTO faults (elevator_id,report_date,report_time,reporter_name,reporter_phone,description,priority,status,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (request.form.get("elevator_id"), normalize_jalali_date(request.form.get("report_date"), today_jalali()),
         request.form.get("report_time"), request.form.get("reporter_name"), request.form.get("reporter_phone"),
         request.form.get("description"), request.form.get("priority") or "normal", "open", datetime.now().isoformat())
    )
    conn.commit(); conn.close()
    flash("خرابی ثبت شد.", "success")
    return redirect(url_for("elev_faults"))

@app.route("/elevators/faults/dispatch/<int:fid>", methods=["POST"])
@login_required
def elev_fault_dispatch(fid):
    conn = get_connection()
    conn.execute(
        "UPDATE faults SET status='dispatched', technician_id=?, dispatch_date=? WHERE id=?",
        (request.form.get("technician_id"), today_jalali(), fid)
    )
    conn.commit(); conn.close()
    flash("سرویس‌کار اعزام شد.", "success")
    return redirect(url_for("elev_faults"))

@app.route("/elevators/faults/close/<int:fid>", methods=["POST"])
@login_required
def elev_fault_close(fid):
    conn = get_connection()
    conn.execute(
        "UPDATE faults SET status='closed', close_date=?, close_report=? WHERE id=?",
        (today_jalali(), request.form.get("close_report"), fid)
    )
    # optional repair record
    elev = conn.execute("SELECT elevator_id FROM faults WHERE id=?", (fid,)).fetchone()
    if elev and request.form.get("create_repair"):
        labor = float(request.form.get("labor_cost") or 0)
        parts = float(request.form.get("parts_cost") or 0)
        conn.execute(
            """INSERT INTO repairs (fault_id,elevator_id,repair_date,technician_id,description,labor_cost,parts_cost,total_cost,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fid, elev["elevator_id"], today_jalali(), request.form.get("technician_id") or None,
             request.form.get("close_report"), labor, parts, labor+parts, datetime.now().isoformat())
        )
    conn.commit(); conn.close()
    flash("خرابی بسته شد.", "success")
    return redirect(url_for("elev_faults"))

@app.route("/elevators/repairs")
@login_required
def elev_repairs():
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.*, e.code as elev_code, t.name as tech_name
        FROM repairs r
        LEFT JOIN elevators e ON e.id=r.elevator_id
        LEFT JOIN technicians t ON t.id=r.technician_id
        ORDER BY r.repair_date DESC
    """).fetchall()
    conn.close()
    return render_template("elev_repairs.html", rows=rows, today=today_jalali())

@app.route("/elevators/technicians")
@login_required
def elev_technicians():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM technicians ORDER BY name").fetchall()
    conn.close()
    return render_template("elev_technicians.html", rows=rows, today=today_jalali())

@app.route("/elevators/technicians/add", methods=["POST"])
@login_required
def elev_tech_add():
    conn = get_connection()
    conn.execute(
        "INSERT INTO technicians (code,name,phone,skill,created_at) VALUES (?,?,?,?,?)",
        (request.form.get("code"), request.form.get("name"), request.form.get("phone"),
         request.form.get("skill"), datetime.now().isoformat())
    )
    conn.commit(); conn.close()
    flash("سرویس‌کار ثبت شد.", "success")
    return redirect(url_for("elev_technicians"))

@app.route("/elevators/profit")
@login_required
def elev_profit():
    """گزارش سود تقریبی هر قرارداد / ساختمان"""
    conn = get_connection()
    by_contract = conn.execute("""
        SELECT c.contract_no, c.amount as contract_amount, p.name as customer_name, b.name as building_name,
               COALESCE((SELECT SUM(total_cost) FROM repairs r WHERE r.elevator_id=c.elevator_id),0) as repair_cost,
               COALESCE((SELECT SUM(amount) FROM service_visits v WHERE v.contract_id=c.id AND v.status='done'),0) as visit_income
        FROM contracts c
        LEFT JOIN parties p ON p.id=c.party_id
        LEFT JOIN buildings b ON b.id=c.building_id
        ORDER BY c.id DESC
    """).fetchall()
    by_building = conn.execute("""
        SELECT b.name as building_name,
               COALESCE(SUM(c.amount),0) as contract_sum,
               COALESCE((SELECT SUM(r.total_cost) FROM repairs r
                         JOIN elevators e2 ON e2.id=r.elevator_id WHERE e2.building_id=b.id),0) as repair_sum
        FROM buildings b
        LEFT JOIN contracts c ON c.building_id=b.id
        GROUP BY b.id
    """).fetchall()
    conn.close()
    return render_template("elev_profit.html", by_contract=by_contract, by_building=by_building, today=today_jalali())



# ==================== پنل سرویس‌کار (موبایل) ====================

@app.route("/tech")
@login_required
def tech_home():
    """صفحه اصلی سرویس‌کار: کارهای امروز + خرابی‌های محول‌شده"""
    tid = session.get("technician_id")
    today = today_jalali()
    conn = get_connection()
    visits = conn.execute("""
        SELECT v.*, e.code as elev_code, e.name as elev_name,
               b.name as building_name, b.address as building_address,
               p.name as customer_name, p.phone as customer_phone
        FROM service_visits v
        LEFT JOIN elevators e ON e.id=v.elevator_id
        LEFT JOIN buildings b ON b.id=e.building_id
        LEFT JOIN contracts c ON c.id=v.contract_id
        LEFT JOIN parties p ON p.id=COALESCE(c.party_id, b.party_id)
        WHERE v.planned_date=? AND v.status='planned'
          AND (v.technician_id=? OR v.technician_id IS NULL OR ? IS NULL)
        ORDER BY b.name, e.code
    """, (today, tid, tid)).fetchall()
    faults = conn.execute("""
        SELECT f.*, e.code as elev_code, e.name as elev_name, b.name as building_name, p.phone as customer_phone
        FROM faults f
        LEFT JOIN elevators e ON e.id=f.elevator_id
        LEFT JOIN buildings b ON b.id=e.building_id
        LEFT JOIN parties p ON p.id=b.party_id
        WHERE f.status IN ('open','dispatched')
          AND (f.technician_id=? OR f.technician_id IS NULL OR ? IS NULL)
        ORDER BY f.priority DESC, f.report_date
    """, (tid, tid)).fetchall()
    done_today = conn.execute(
        "SELECT COUNT(*) FROM service_visits WHERE visit_date=? AND status='done' AND (technician_id=? OR ?=0)",
        (today, tid or 0, tid or 0)
    ).fetchone()[0]
    conn.close()
    return render_template("tech_home.html", visits=visits, faults=faults, done_today=done_today, today=today)

@app.route("/tech/visit/<int:vid>", methods=["GET", "POST"])
@login_required
def tech_visit_report(vid):
    """ثبت گزارش سرویس + چک‌لیست + امضا"""
    conn = get_connection()
    visit = conn.execute("""
        SELECT v.*, e.code as elev_code, e.name as elev_name, b.name as building_name, b.address as building_address,
               p.name as customer_name, p.phone as customer_phone
        FROM service_visits v
        LEFT JOIN elevators e ON e.id=v.elevator_id
        LEFT JOIN buildings b ON b.id=e.building_id
        LEFT JOIN contracts c ON c.id=v.contract_id
        LEFT JOIN parties p ON p.id=COALESCE(c.party_id, b.party_id)
        WHERE v.id=?
    """, (vid,)).fetchone()
    if not visit:
        conn.close()
        flash("نوبت یافت نشد.", "danger")
        return redirect(url_for("tech_home"))

    # کنترل دسترسی: یک سرویس‌کار فقط به نوبت‌های محول‌شده به خودش (یا نوبت‌های بدون سرویس‌کار مشخص) دسترسی دارد
    if session.get("role") == "technician":
        my_tid = session.get("technician_id")
        if visit["technician_id"] is not None and visit["technician_id"] != my_tid:
            conn.close()
            flash("این نوبت به سرویس‌کار دیگری محول شده و امکان دسترسی ندارید.", "danger")
            return redirect(url_for("tech_home"))

    if request.method == "POST":
        report = request.form.get("report_text") or ""
        sign = request.form.get("customer_sign") or ""
        signature_data = request.form.get("signature_data") or ""
        photo_data = request.form.get("photo_data") or ""
        # جلوگیری از ذخیره یک کنواس کاملاً خالی به‌عنوان امضا
        if signature_data and len(signature_data) < 100:
            signature_data = ""
        conn.execute(
            """UPDATE service_visits SET status='done', visit_date=?, report_text=?, customer_sign=?,
               signature_data=?, photo_data=?, technician_id=COALESCE(technician_id, ?) WHERE id=?""",
            (today_jalali(), report, sign, signature_data, photo_data, session.get("technician_id"), vid)
        )
        conn.execute("DELETE FROM visit_checklist WHERE visit_id=?", (vid,))
        for key, label in SERVICE_CHECKLIST:
            ok = 1 if request.form.get(f"chk_{key}") == "1" else 0
            note = request.form.get(f"note_{key}") or ""
            conn.execute(
                "INSERT INTO visit_checklist (visit_id, item_key, item_label, is_ok, note) VALUES (?,?,?,?,?)",
                (vid, key, label, ok, note)
            )
        conn.commit()
        conn.close()
        flash("گزارش سرویس و چک‌لیست ثبت شد.", "success")
        return redirect(url_for("tech_home"))

    conn.close()
    return render_template("tech_visit_report.html", visit=visit, checklist=SERVICE_CHECKLIST, today=today_jalali())


if __name__ == "__main__":
    init_db()
    init_elevator_tables()
    seed_elevator_sample()
    create_indexes()
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  Ario Accounting - Online Ready")
    print(f"  Port: {port}")
    print("  Login: admin / admin")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
