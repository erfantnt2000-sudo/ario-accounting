# راهنمای آنلاین کردن حسابداری آریو (رایگان)

بعد از انجام این مراحل، برنامه روی اینترنت قرار می‌گیرد و از ویندوز، اندروید و هر دستگاهی با مرورگر قابل استفاده است.
همه کاربران به یک دیتابیس مشترک وصل می‌شوند و تغییرات آنلاین ذخیره می‌شود.

## روش ۱ — Render.com (پیشنهادی و رایگان)

1. بروید به: https://render.com و با GitHub یا ایمیل ثبت‌نام کنید.
2. روی **New +** → **Web Service** کلیک کنید.
3. اگر پروژه را در GitHub ندارید:
   - می‌توانید از گزینه **Deploy from existing image** استفاده نکنید.
   - ساده‌تر: فایل‌های پوشه `ario_accounting` را در یک مخزن GitHub قرار دهید (یا از «Deploy from ZIP» اگر موجود بود).
4. تنظیمات:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type:** Free
5. Environment Variables:
   - `SECRET_KEY` = یک رشته تصادفی (مثلاً `ario-online-2026-secret`)
6. Deploy را بزنید. بعد از چند دقیقه یک آدرس مثل زیر می‌گیرید:
   ```
   https://ario-accounting-xxxx.onrender.com
   ```
7. این آدرس را در مرورگر ویندوز یا اندروید باز کنید.
   ورود: **admin** / **admin**

نکته: در پلن رایگان Render اگر مدتی استفاده نشود ممکن است sleep شود و اولین باز شدن کمی طول بکشد.

## روش ۲ — Railway.app

1. https://railway.app → ثبت‌نام با GitHub
2. New Project → Deploy from GitHub (یا Upload)
3. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. بعد از Deploy لینک عمومی می‌گیرید.

## روش ۳ — PythonAnywhere (ساده‌تر برای مبتدی)

1. https://www.pythonanywhere.com → حساب رایگان بسازید.
2. در بخش Files فایل‌های پروژه را آپلود کنید.
3. در Web tab یک Web App جدید از نوع Manual بسازید و به فایل `app.py` اشاره دهید.
4. بعد از Reload آدرس `yourusername.pythonanywhere.com` فعال می‌شود.

## استفاده از اندروید

هیچ اپ جداگانه‌ای لازم نیست.
در Chrome اندروید همان آدرس را باز کنید و در صورت تمایل «Add to Home Screen» بزنید تا مثل اپ باز شود.

## امنیت مهم

- حتماً رمز admin را بعد از اولین ورود عوض کنید (فعلاً در کد ساده است).
- برای استفاده واقعی چندکاربره بهتر است دیتابیس را به PostgreSQL تغییر دهید (در صورت نیاز بگویید اضافه می‌کنم).

