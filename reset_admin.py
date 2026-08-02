# -*- coding: utf-8 -*-
"""بازنشانی رمز admin و tech به مقدار پیش‌فرض (admin / tech)"""
from database import get_connection, init_db, _hash_password, create_indexes
from elevator_models import init_elevator_tables

if __name__ == "__main__":
    init_db()
    init_elevator_tables()
    create_indexes()
    conn = get_connection()
    for uname, raw, full, role in [
        ("admin", "admin", "مدیر سیستم", "admin"),
        ("tech", "tech", "سرویس‌کار نمونه", "technician"),
    ]:
        row = conn.execute("SELECT id FROM users WHERE username=?", (uname,)).fetchone()
        if row:
            conn.execute("UPDATE users SET password=?, full_name=?, role=? WHERE username=?",
                         (_hash_password(raw), full, role, uname))
            print(f"رمز کاربر «{uname}» به «{raw}» بازنشانی شد.")
        else:
            conn.execute(
                "INSERT INTO users (username, password, full_name, role) VALUES (?,?,?,?)",
                (uname, _hash_password(raw), full, role),
            )
            print(f"کاربر «{uname}» ساخته شد (رمز: {raw}).")
    conn.commit()
    conn.close()
    print("تمام. دوباره برنامه را اجرا کنید و با admin / admin وارد شوید.")
