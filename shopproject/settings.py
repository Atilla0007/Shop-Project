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

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.getenv("SECRET_KEY", "dev-unsafe-change-me")
DEBUG = _env_bool("DEBUG", False)

_allowed_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
if _allowed_hosts:
    ALLOWED_HOSTS = _allowed_hosts
elif DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]
else:
    ALLOWED_HOSTS = []

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
if not CSRF_TRUSTED_ORIGINS and DEBUG:
    CSRF_TRUSTED_ORIGINS = ["http://localhost", "http://127.0.0.1"]

if _env_bool("SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Localization
LANGUAGE_CODE='fa'
TIME_ZONE='Asia/Tehran'
USE_I18N=True
USE_TZ=True

INSTALLED_APPS=[
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_otp',
    'auth_security',
    'core',
    'store',
    'accounts',
    'otp_email',
    'otp_sms',
]
MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    'core.middleware.ExceptionLoggingMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'core.middleware.SiteVisitMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'auth_security.middleware.LoginProtectionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'core.middleware.AdminEnglishMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF='shopproject.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','core.context_processors.site_info','core.context_processors.public_promo']}}]

# تنظیم ASGI
ASGI_APPLICATION = 'shopproject.asgi.application'

DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3").strip()
USE_PYMYSQL = _env_bool("USE_PYMYSQL", True)
if DB_ENGINE == "django.db.backends.mysql" and USE_PYMYSQL:
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except Exception:
        pass

DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_CONN_MAX_AGE = int(os.getenv("DB_CONN_MAX_AGE", "60"))

if DB_ENGINE == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": DB_NAME or str(BASE_DIR / "db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "OPTIONS": {"charset": "utf8mb4"},
            "CONN_MAX_AGE": DB_CONN_MAX_AGE,
        }
    }

STATIC_URL = os.getenv("STATIC_URL", "/static/")
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles")))
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
LOGIN_REDIRECT_URL='/'
LOGOUT_REDIRECT_URL='/'

LOGIN_URL = '/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security defaults (production settings are enabled automatically when DEBUG is false)
X_FRAME_OPTIONS = os.getenv("X_FRAME_OPTIONS", "DENY")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "same-origin")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")

if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", True)
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", True)

# Static files caching/compression (WhiteNoise)
WHITENOISE_MAX_AGE = int(os.getenv("WHITENOISE_MAX_AGE", "31536000"))
WHITENOISE_AUTOREFRESH = _env_bool("WHITENOISE_AUTOREFRESH", DEBUG)
WHITENOISE_USE_FINDERS = _env_bool("WHITENOISE_USE_FINDERS", DEBUG)
if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"



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

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "file_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "errors.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": True,
        },
        "core.errors": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# Branding / Invoice company info
SITE_NAME = os.getenv('SITE_NAME', 'استیرا')
ABOUT_TEMPLATE = os.getenv('ABOUT_TEMPLATE', 'about.html')
COMPANY_ADDRESS = os.getenv('COMPANY_ADDRESS', '').replace('\\n', '\n')
COMPANY_PHONE = os.getenv('COMPANY_PHONE', '')
COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', '')
COMPANY_TELEGRAM = os.getenv('COMPANY_TELEGRAM', 'styra_steel')

# Base URL (optional) - used for links in admin digest emails (e.g. https://styra.ir)
SITE_BASE_URL = os.getenv('SITE_BASE_URL', '')

# Receipt maintenance
RECEIPT_PURGE_DELAY_SECONDS = int(os.getenv('RECEIPT_PURGE_DELAY_SECONDS', '7200'))

# Authentication security (login brute-force protection)
AUTH_SECURITY_LOGIN_PATHS = os.getenv("AUTH_SECURITY_LOGIN_PATHS", "/login/,/admin/login/")
AUTH_SECURITY_PROTECTED_PATHS = os.getenv(
    "AUTH_SECURITY_PROTECTED_PATHS",
    "/auth/email-otp/verify/,/auth/phone-otp/verify/,/password-reset/,/password_reset/",
)
AUTH_SECURITY_TRUST_X_FORWARDED_FOR = _env_bool("AUTH_SECURITY_TRUST_X_FORWARDED_FOR", False)
AUTH_SECURITY_LOGIN_IP_MAX_ATTEMPTS = int(os.getenv("AUTH_SECURITY_LOGIN_IP_MAX_ATTEMPTS", "10"))
AUTH_SECURITY_LOGIN_IP_WINDOW_SECONDS = int(os.getenv("AUTH_SECURITY_LOGIN_IP_WINDOW_SECONDS", "600"))
AUTH_SECURITY_LOGIN_IP_BLOCK_AFTER_ATTEMPTS = int(
    os.getenv("AUTH_SECURITY_LOGIN_IP_BLOCK_AFTER_ATTEMPTS", str(AUTH_SECURITY_LOGIN_IP_MAX_ATTEMPTS))
)
AUTH_SECURITY_IP_BLOCK_SECONDS = int(os.getenv("AUTH_SECURITY_IP_BLOCK_SECONDS", "1800"))
AUTH_SECURITY_LOGIN_IDENTIFIER_MAX_ATTEMPTS = int(os.getenv("AUTH_SECURITY_LOGIN_IDENTIFIER_MAX_ATTEMPTS", "5"))
AUTH_SECURITY_LOGIN_IDENTIFIER_WINDOW_SECONDS = int(os.getenv("AUTH_SECURITY_LOGIN_IDENTIFIER_WINDOW_SECONDS", "600"))

# Security headers
CSP_DEFAULT = os.getenv(
    "CSP_DEFAULT",
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self' data:;",
)
SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "same-origin")
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

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
