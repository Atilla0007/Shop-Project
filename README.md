پروژه Django آماده (اسکلت) — شامل:
- ثبت‌نام/ورود/خروج، فروشگاه ساده، سبد خرید، صفحه نهایی‌سازی، اخبار، تماس، FAQ
- پنل ادمین برای مدیریت محصولات و فیلتر بر اساس domain
- پشتیبانی آنلاین ساده با polling (AJAX)
- رنگ‌بندی سایت بر اساس کدهای شما

فایل زیپ: shopproject.zip

راه‌اندازی محلی (گام به گام) — روی سیستم خود با VS Code و هاست محلی:
1) فایل shopproject.zip را از اینجا دانلود و استخراج کنید.
2) یک محیط مجازی بسازید و فعال کنید:
   python -m venv venv
   # روی ویندوز:
   venv\Scripts\activate
   # لینوکس/مک:
   source venv/bin/activate
3) نصب وابستگی‌ها:
   pip install -r requirements.txt
4) ایجاد مهاجرت‌ها و دیتابیس sqlite:
   python manage.py makemigrations
   python manage.py migrate
5) ایجاد یک ادمین برای ورود به پنل مدیریتی:
   python manage.py createsuperuser
6) اجرای سرور توسعه:
   python manage.py runserver
   سپس در مرورگر به http://127.0.0.1:8000/ بروید
   پنل ادمین: http://127.0.0.1:8000/admin/

آپلود روی سرور/هاست (نمایش به کارفرما از طریق VS Code + سرویس هاست):
A) اگر می‌خواهی سریع با Localtunnel / ngrok نمایش بدی (بدون خرید دامنه):
   - راه اندازی سرور محلی (runserver) و سپس از ngrok استفاده کن:
     ngrok http 8000
   - یا از localtunnel: npx localtunnel --port 8000
   یک URL عمومی بهت می‌دهد که می‌تونی به کارفرما نشان بدهی.
B) استقرار واقعی روی هاست (مثلا VPS مثل DigitalOcean یا سرویس cPanel):
   - اطمینان از Python و pip و git نصب است.
   - کد را روی سرور کپی کن (git push یا scp).
   - در سرور: ایجاد venv، نصب requirements، اجرای migrations.
   - برای production: DEBUG=False، تنظیم ALLOWED_HOSTS، تنظیم سرویس وب مثل gunicorn و reverse-proxy با nginx.
   - تنظیم HTTPS با certbot (Let's Encrypt).
اگر خواستی من فایل nginx و systemd unit آماده برات می‌سازم.
