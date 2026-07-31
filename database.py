# -*- coding: utf-8 -*-
"""
نرم‌افزار حسابداری آریو - ماژول پایگاه داده
نسخه ۲ - با ماژول مشتریان، نوبت روزانه، غایبین و پرداخت‌ها
"""
import sqlite3
import os
from datetime import datetime
import jdatetime

# On Render (and most cloud hosts) the filesystem is ephemeral; use /tmp which is always writable.
# Locally keep data next to the project.
if os.environ.get("RENDER") or os.environ.get("PORT"):
    DB_PATH = os.path.join("/tmp", "ario.db")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ario.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            parent_code TEXT,
            account_type TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            description TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            party_type TEXT NOT NULL DEFAULT 'customer',
            phone TEXT,
            address TEXT,
            national_id TEXT,
            credit_limit REAL DEFAULT 0,
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            unit TEXT DEFAULT 'عدد',
            group_name TEXT,
            buy_price REAL DEFAULT 0,
            sell_price REAL DEFAULT 0,
            stock_qty REAL DEFAULT 0,
            min_stock REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_no INTEGER UNIQUE,
            voucher_date TEXT NOT NULL,
            description TEXT,
            voucher_type TEXT DEFAULT 'manual',
            created_at TEXT,
            is_posted INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS voucher_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            party_id INTEGER,
            description TEXT,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE,
            invoice_type TEXT NOT NULL,
            invoice_date TEXT NOT NULL,
            party_id INTEGER,
            description TEXT,
            total_amount REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            final_amount REAL DEFAULT 0,
            voucher_id INTEGER,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS invoice_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER,
            description TEXT,
            qty REAL DEFAULT 1,
            unit_price REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            amount REAL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'user'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_id INTEGER NOT NULL,
            appt_date TEXT NOT NULL,
            appt_time TEXT,
            service_type TEXT,
            description TEXT,
            is_done INTEGER DEFAULT 0,
            done_at TEXT,
            amount REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (party_id) REFERENCES parties(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_id INTEGER NOT NULL,
            pay_date TEXT NOT NULL,
            amount REAL NOT NULL,
            method TEXT DEFAULT 'cash',
            description TEXT,
            created_at TEXT,
            FOREIGN KEY (party_id) REFERENCES parties(id)
        )
    """)

    conn.commit()

    c.execute("SELECT COUNT(*) FROM accounts")
    if c.fetchone()[0] == 0:
        sample_accounts = [
            ("1", "دارایی‌ها", None, "asset"),
            ("11", "دارایی‌های جاری", "1", "asset"),
            ("111", "موجودی نقد و بانک", "11", "asset"),
            ("11101", "صندوق", "111", "asset"),
            ("11102", "بانک‌ها", "111", "asset"),
            ("112", "حساب‌های دریافتنی", "11", "asset"),
            ("11201", "بدهکاران تجاری", "112", "asset"),
            ("113", "موجودی کالا", "11", "asset"),
            ("11301", "کالای آماده فروش", "113", "asset"),
            ("2", "بدهی‌ها", None, "liability"),
            ("21", "بدهی‌های جاری", "2", "liability"),
            ("211", "حساب‌های پرداختنی", "21", "liability"),
            ("21101", "بستانکاران تجاری", "211", "liability"),
            ("3", "حقوق صاحبان سهام", None, "equity"),
            ("31", "سرمایه", "3", "equity"),
            ("3101", "سرمایه اولیه", "31", "equity"),
            ("4", "درآمدها", None, "revenue"),
            ("41", "فروش", "4", "revenue"),
            ("4101", "فروش کالا", "41", "revenue"),
            ("5", "هزینه‌ها", None, "expense"),
            ("51", "بهای تمام‌شده کالای فروش‌رفته", "5", "expense"),
            ("5101", "بهای تمام‌شده فروش", "51", "expense"),
            ("52", "هزینه‌های عملیاتی", "5", "expense"),
            ("5201", "هزینه حقوق و دستمزد", "52", "expense"),
            ("5202", "هزینه اجاره", "52", "expense"),
            ("5203", "سایر هزینه‌ها", "52", "expense"),
        ]
        for code, name, parent, atype in sample_accounts:
            c.execute("INSERT INTO accounts (code, name, parent_code, account_type) VALUES (?, ?, ?, ?)", (code, name, parent, atype))

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)", ("admin", "admin", "مدیر سیستم", "admin"))

    c.execute("SELECT COUNT(*) FROM parties")
    if c.fetchone()[0] == 0:
        today = datetime.now().isoformat()
        samples = [
            ("C001", "علی محمدی", "customer", "09121234567", "تهران"),
            ("C002", "مریم احمدی", "customer", "09129876543", "اصفهان"),
            ("C003", "رضا کریمی", "customer", "09351234567", "شیراز"),
            ("C004", "سارا حسینی", "customer", "09121112233", "مشهد"),
            ("C005", "حسین رضایی", "customer", "09123334455", "تبریز"),
            ("S001", "شرکت تأمین‌کننده نمونه", "supplier", "02188776655", "تهران"),
        ]
        for code, name, ptype, phone, addr in samples:
            c.execute("INSERT INTO parties (code, name, party_type, phone, address, created_at) VALUES (?,?,?,?,?,?)", (code, name, ptype, phone, addr, today))

    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO products (code, name, unit, buy_price, sell_price, stock_qty) VALUES (?,?,?,?,?,?)", ("P001", "کالای نمونه ۱", "عدد", 100000, 150000, 50))
        c.execute("INSERT INTO products (code, name, unit, buy_price, sell_price, stock_qty) VALUES (?,?,?,?,?,?)", ("P002", "کالای نمونه ۲", "کیلو", 50000, 80000, 100))

    c.execute("SELECT COUNT(*) FROM appointments")
    if c.fetchone()[0] == 0:
        today_j = jdatetime.date.today().strftime("%Y/%m/%d")
        yesterday = (jdatetime.date.today() - jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
        parties = c.execute("SELECT id FROM parties WHERE party_type='customer' LIMIT 5").fetchall()
        if parties:
            c.execute("INSERT INTO appointments (party_id, appt_date, appt_time, service_type, description, is_done, amount, created_at) VALUES (?,?,?,?,?,?,?,?)",
                      (parties[0]["id"], today_j, "09:00", "سرویس معمولی", "نوبت صبح", 0, 200000, datetime.now().isoformat()))
            if len(parties) > 1:
                c.execute("INSERT INTO appointments (party_id, appt_date, appt_time, service_type, description, is_done, amount, created_at) VALUES (?,?,?,?,?,?,?,?)",
                          (parties[1]["id"], today_j, "11:00", "سرویس ویژه", "نوبت ظهر", 0, 350000, datetime.now().isoformat()))
            if len(parties) > 2:
                c.execute("INSERT INTO appointments (party_id, appt_date, appt_time, service_type, description, is_done, amount, created_at) VALUES (?,?,?,?,?,?,?,?)",
                          (parties[2]["id"], today_j, "14:00", "مشاوره", "", 1, 150000, datetime.now().isoformat()))
            if len(parties) > 3:
                c.execute("INSERT INTO appointments (party_id, appt_date, appt_time, service_type, description, is_done, amount, created_at) VALUES (?,?,?,?,?,?,?,?)",
                          (parties[3]["id"], yesterday, "10:00", "سرویس معمولی", "غایب", 0, 200000, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    print("Database ready.")

def get_next_voucher_no():
    conn = get_connection()
    row = conn.execute("SELECT MAX(voucher_no) FROM vouchers").fetchone()
    conn.close()
    return (row[0] or 0) + 1

def today_jalali():
    return jdatetime.date.today().strftime("%Y/%m/%d")

def current_month_jalali():
    return jdatetime.date.today().strftime("%Y/%m")
