import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

# بارگذاری تنظیمات محلی از فایل .env (داخل ریپو ذخیره نمی‌شود چون در .gitignore است)
def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")
SECRET_KEY='test'
DEBUG=True
ALLOWED_HOSTS=[]

# Localization
LANGUAGE_CODE='fa'
TIME_ZONE='Asia/Tehran'
USE_I18N=True
USE_TZ=True

INSTALLED_APPS=[
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_otp',
    'core',
    'store',
    'accounts',
    'otp_email',
    'otp_sms',
]
MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]
ROOT_URLCONF='shopproject.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','core.context_processors.public_promo']}}]

# تنظیم ASGI
ASGI_APPLICATION = 'shopproject.asgi.application'
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
STATIC_URL='/static/'
STATICFILES_DIRS=[BASE_DIR/'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
LOGIN_REDIRECT_URL='/'
LOGOUT_REDIRECT_URL='/'

LOGIN_URL = '/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# SMS settings
SMS_BACKEND = os.getenv('SMS_BACKEND', 'console')  # console | kavenegar
KAVENEGAR_API_KEY = os.getenv('KAVENEGAR_API_KEY', '')
KAVENEGAR_SENDER = os.getenv('KAVENEGAR_SENDER', '')

# Email settings (dev defaults to file backend to avoid console issues on some Windows terminals)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.filebased.EmailBackend')
EMAIL_FILE_PATH = os.getenv('EMAIL_FILE_PATH', str(BASE_DIR / 'tmp' / 'emails'))
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@example.com')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1').strip().lower() in ('1', 'true', 'yes', 'on')

# Branding / Invoice company info
SITE_NAME = os.getenv('SITE_NAME', 'استیرا')
COMPANY_ADDRESS = os.getenv('COMPANY_ADDRESS', '').replace('\\n', '\n')
COMPANY_PHONE = os.getenv('COMPANY_PHONE', '')
COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', '')

# Base URL (optional) - used for links in admin digest emails (e.g. https://styra.ir)
SITE_BASE_URL = os.getenv('SITE_BASE_URL', '')

# Receipt maintenance
RECEIPT_PURGE_DELAY_SECONDS = int(os.getenv('RECEIPT_PURGE_DELAY_SECONDS', '7200'))

# Email OTP settings
EMAIL_OTP_LENGTH = int(os.getenv('EMAIL_OTP_LENGTH', '6'))
EMAIL_OTP_TTL_SECONDS = int(os.getenv('EMAIL_OTP_TTL_SECONDS', '300'))
EMAIL_OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv('EMAIL_OTP_RESEND_COOLDOWN_SECONDS', '60'))
EMAIL_OTP_MAX_SEND_PER_WINDOW = int(os.getenv('EMAIL_OTP_MAX_SEND_PER_WINDOW', '3'))
EMAIL_OTP_SEND_WINDOW_SECONDS = int(os.getenv('EMAIL_OTP_SEND_WINDOW_SECONDS', '600'))
EMAIL_OTP_MAX_VERIFY_ATTEMPTS = int(os.getenv('EMAIL_OTP_MAX_VERIFY_ATTEMPTS', '5'))

# SMS OTP settings (provider can be configured via SMS_BACKEND)
SMS_OTP_LENGTH = int(os.getenv('SMS_OTP_LENGTH', '6'))
SMS_OTP_TTL_SECONDS = int(os.getenv('SMS_OTP_TTL_SECONDS', '300'))
SMS_OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv('SMS_OTP_RESEND_COOLDOWN_SECONDS', '60'))
SMS_OTP_MAX_SEND_PER_WINDOW = int(os.getenv('SMS_OTP_MAX_SEND_PER_WINDOW', '3'))
SMS_OTP_SEND_WINDOW_SECONDS = int(os.getenv('SMS_OTP_SEND_WINDOW_SECONDS', '600'))
SMS_OTP_MAX_VERIFY_ATTEMPTS = int(os.getenv('SMS_OTP_MAX_VERIFY_ATTEMPTS', '5'))
