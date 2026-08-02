# راهنمای آنلاین کردن حسابداری آریو روی Render

## علت اصلی مشکل لاگین روی Render

1. **چند Worker بدون SECRET_KEY مشترک** → نشست و CSRF بین workerها خراب می‌شد (اصلاح شد: ۱ worker).
2. **نبود متغیر SECRET_KEY** → هر ری‌استارت کلید عوض می‌شد.
3. **فایل‌سیستم موقت** → دیتابیس در `/tmp` است و با sleep/ری‌استارت پاک می‌شود (طبیعی پلن رایگان).

---

## مراحل دیپلوی روی Render.com

### ۱) مخزن GitHub
پوشه `ario_accounting` را در یک ریپوی GitHub بگذارید (همه فایل‌ها: `app.py`, `database.py`, `templates`, ...).

### ۲) ساخت Web Service
1. بروید به [render.com](https://render.com) و ثبت‌نام کنید.
2. **New +** → **Web Service**
3. ریپو را وصل کنید.
4. تنظیمات:

| فیلد | مقدار |
|------|--------|
| **Name** | مثلاً `ario-elevator` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --worker-class gthread --timeout 120` |
| **Instance Type** | Free |

> اگر Root Directory جدا دارید، آن را روی پوشه `ario_accounting` بگذارید.

### ۳) Environment Variables (خیلی مهم)

در بخش **Environment** این متغیر را **حتماً** اضافه کنید:

| Key | Value |
|-----|--------|
| `SECRET_KEY` | یک رشته تصادفی بلند، مثلاً: `ario-2026-xK9mP2qR7vL4nB8w` |

بدون `SECRET_KEY` هم برنامه بالا می‌آید، ولی برای امنیت و پایداری نشست حتماً تنظیم کنید.

### ۴) Deploy
دکمه **Deploy** را بزنید. بعد از ۱–۳ دقیقه آدرسی مثل این می‌گیرید:

```
https://ario-elevator-xxxx.onrender.com
```

### ۵) ورود
- آدرس بالا را در مرورگر باز کنید
- **نام کاربری:** `admin`
- **رمز:** `admin`

اگر لاگین نشد:
1. یک‌بار صفحه را Hard Refresh کنید (`Ctrl+Shift+R`)
2. کوکی‌های سایت را پاک کنید یا حالت ناشناس باز کنید
3. در Render → Logs خطا را ببینید

---

## نکات مهم پلن رایگان Render

| موضوع | توضیح |
|--------|--------|
| **Sleep** | اگر حدود ۱۵ دقیقه کسی نیاید، سرویس می‌خوابد. اولین باز شدن بعدی ۳۰–۶۰ ثانیه طول می‌کشد. |
| **دیتابیس** | روی `/tmp` است → با هر Deploy یا Sleep طولانی **داده‌ها پاک می‌شوند**. برای کار واقعی باید PostgreSQL وصل شود. |
| **Worker** | الان ۱ worker است (مناسب SQLite). چند worker با SQLite و بدون SECRET_KEY مشترک لاگین را خراب می‌کند. |

---

## اگر بعد از Deploy هنوز لاگین نمی‌شود

1. در Render → **Environment** مقدار `SECRET_KEY` را چک کنید.
2. **Manual Deploy** → Clear build cache → Deploy again.
3. Logs را باز کنید و ببینید `Database ready` و `Elevator tables ready` چاپ شده یا نه.
4. آدرس `/health` را باز کنید؛ باید `{"status":"ok"}` ببینید.

---

## روش‌های دیگر

- **Railway.app**: مشابه Render، `SECRET_KEY` را در Variables بگذارید.
- **PythonAnywhere**: برای مبتدی ساده‌تر است؛ فایل‌ها را آپلود کنید و WSGI را به `app:app` وصل کنید.
