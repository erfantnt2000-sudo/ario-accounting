# -*- coding: utf-8 -*-
"""جداول تخصصی مدیریت سرویس آسانسور"""
from database import get_connection
from datetime import datetime
import jdatetime

def init_elevator_tables():
    conn = get_connection()
    c = conn.cursor()

    # مجتمع / پروژه
    c.execute("""
        CREATE TABLE IF NOT EXISTS complexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            manager_name TEXT,
            manager_phone TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    # ساختمان
    c.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complex_id INTEGER,
            code TEXT,
            name TEXT NOT NULL,
            address TEXT,
            floors INTEGER DEFAULT 0,
            units INTEGER DEFAULT 0,
            party_id INTEGER,
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY (complex_id) REFERENCES complexes(id),
            FOREIGN KEY (party_id) REFERENCES parties(id)
        )
    """)

    # پرونده آسانسور
    c.execute("""
        CREATE TABLE IF NOT EXISTS elevators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            code TEXT UNIQUE,
            name TEXT,
            brand TEXT,
            model TEXT,
            capacity TEXT,
            install_year TEXT,
            serial_no TEXT,
            stops INTEGER DEFAULT 0,
            drive_type TEXT,
            door_type TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings(id)
        )
    """)

    # قرارداد سرویس
    c.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_no TEXT UNIQUE,
            party_id INTEGER,
            building_id INTEGER,
            elevator_id INTEGER,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            amount REAL DEFAULT 0,
            visit_per_month INTEGER DEFAULT 1,
            payment_type TEXT DEFAULT 'monthly',
            status TEXT DEFAULT 'active',
            description TEXT,
            created_at TEXT,
            FOREIGN KEY (party_id) REFERENCES parties(id),
            FOREIGN KEY (building_id) REFERENCES buildings(id),
            FOREIGN KEY (elevator_id) REFERENCES elevators(id)
        )
    """)

    # برنامه سرویس ماهانه / بازدید
    c.execute("""
        CREATE TABLE IF NOT EXISTS service_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER,
            elevator_id INTEGER,
            technician_id INTEGER,
            planned_date TEXT NOT NULL,
            visit_date TEXT,
            visit_type TEXT DEFAULT 'periodic',
            status TEXT DEFAULT 'planned',
            report_text TEXT,
            customer_sign TEXT,
            photo_note TEXT,
            amount REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (contract_id) REFERENCES contracts(id),
            FOREIGN KEY (elevator_id) REFERENCES elevators(id)
        )
    """)

    # خرابی و اعزام
    c.execute("""
        CREATE TABLE IF NOT EXISTS faults (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elevator_id INTEGER NOT NULL,
            report_date TEXT NOT NULL,
            report_time TEXT,
            reporter_name TEXT,
            reporter_phone TEXT,
            description TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'open',
            technician_id INTEGER,
            dispatch_date TEXT,
            close_date TEXT,
            close_report TEXT,
            created_at TEXT,
            FOREIGN KEY (elevator_id) REFERENCES elevators(id)
        )
    """)

    # تاریخچه تعمیرات و قطعات
    c.execute("""
        CREATE TABLE IF NOT EXISTS repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fault_id INTEGER,
            elevator_id INTEGER NOT NULL,
            repair_date TEXT NOT NULL,
            technician_id INTEGER,
            description TEXT,
            labor_cost REAL DEFAULT 0,
            parts_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (fault_id) REFERENCES faults(id),
            FOREIGN KEY (elevator_id) REFERENCES elevators(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS repair_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_id INTEGER NOT NULL,
            product_id INTEGER,
            part_name TEXT,
            qty REAL DEFAULT 1,
            unit_price REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            FOREIGN KEY (repair_id) REFERENCES repairs(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # سرویس‌کار (تکنسین)
    c.execute("""
        CREATE TABLE IF NOT EXISTS technicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            phone TEXT,
            skill TEXT,
            is_active INTEGER DEFAULT 1,
            user_id INTEGER,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS visit_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            item_label TEXT,
            is_ok INTEGER DEFAULT 0,
            note TEXT,
            FOREIGN KEY (visit_id) REFERENCES service_visits(id)
        )
    """)
    # link sample tech user if exists
    try:
        u = c.execute("SELECT id FROM users WHERE username='tech'").fetchone()
        if u:
            c.execute("UPDATE technicians SET user_id=? WHERE code='T01' AND (user_id IS NULL OR user_id=0)", (u[0] if not hasattr(u,'keys') else u['id'],))
    except Exception:
        pass

    # مهاجرت: ستون‌های امضای دیجیتال (کنواس) و عکس واقعی بازدید (base64) برای دیتابیس‌های قدیمی‌تر
    for col_sql in [
        "ALTER TABLE service_visits ADD COLUMN signature_data TEXT",
        "ALTER TABLE service_visits ADD COLUMN photo_data TEXT",
        "ALTER TABLE service_visits ADD COLUMN rating INTEGER",
        "ALTER TABLE service_visits ADD COLUMN rating_comment TEXT",
        "ALTER TABLE contracts ADD COLUMN insurance_expiry TEXT",
    ]:
        try:
            c.execute(col_sql)
        except Exception:
            pass  # ستون از قبل وجود دارد

    conn.commit()
    conn.close()
    print("Elevator tables ready.")

def seed_elevator_sample():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM complexes")
    if c.fetchone()[0] > 0:
        conn.close()
        return
    now = datetime.now().isoformat()
    today = jdatetime.date.today()
    c.execute("INSERT INTO complexes (code,name,address,city,manager_name,manager_phone,created_at) VALUES (?,?,?,?,?,?,?)",
              ("CX01", "مجتمع نمونه آریا", "خیابان ولیعصر", "تهران", "آقای موسوی", "09121111111", now))
    cx = c.lastrowid
    # party for customer
    c.execute("SELECT id FROM parties WHERE party_type='customer' LIMIT 1")
    party = c.fetchone()
    pid = party["id"] if party else None
    c.execute("INSERT INTO buildings (complex_id,code,name,address,floors,units,party_id,created_at) VALUES (?,?,?,?,?,?,?,?)",
              (cx, "B01", "برج A", "واحد مدیریت", 12, 48, pid, now))
    bid = c.lastrowid
    c.execute("INSERT INTO elevators (building_id,code,name,brand,model,capacity,stops,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (bid, "EL-001", "آسانسور شماره ۱", "اوتیس", "Gen2", "8 نفر", 12, "active", now))
    eid = c.lastrowid
    c.execute("INSERT INTO elevators (building_id,code,name,brand,model,capacity,stops,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (bid, "EL-002", "آسانسور شماره ۲", "شindler", "3300", "10 نفر", 12, "active", now))
    end = (today + jdatetime.timedelta(days=60)).strftime("%Y/%m/%d")
    start = today.strftime("%Y/%m/%d")
    c.execute("""INSERT INTO contracts (contract_no,party_id,building_id,elevator_id,start_date,end_date,amount,visit_per_month,status,created_at)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              ("CT-1404-001", pid, bid, eid, start, end, 15000000, 1, "active", now))
    c.execute("INSERT INTO technicians (code,name,phone,skill,created_at) VALUES (?,?,?,?,?)",
              ("T01", "مهدی رضایی", "09121234567", "سرویس و تعمیر", now))
    c.execute("INSERT INTO technicians (code,name,phone,skill,created_at) VALUES (?,?,?,?,?)",
              ("T02", "علی اکبری", "09129876543", "خرابی اضطراری", now))
    # planned visit
    c.execute("""INSERT INTO service_visits (contract_id,elevator_id,technician_id,planned_date,status,created_at)
                 VALUES (?,?,?,?,?,?)""", (c.execute("SELECT id FROM contracts LIMIT 1").fetchone()[0], eid, 1, start, "planned", now))
    # link tech user before close
    try:
        u = c.execute("SELECT id FROM users WHERE username='tech'").fetchone()
        if u:
            uid = u[0]
            c.execute("UPDATE technicians SET user_id=? WHERE id=(SELECT id FROM technicians ORDER BY id LIMIT 1)", (uid,))
    except Exception as e:
        print("tech link:", e)
    conn.commit()
    conn.close()
    print("Sample elevator data seeded.")
