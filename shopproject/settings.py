import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY='test'
DEBUG=True
ALLOWED_HOSTS=[]
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
    'channels',
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
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]

# تنظیم نام صحیح ASGI برای پشتیبانی از WebSocket
ASGI_APPLICATION = 'shopproject.asgi.application'
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
STATIC_URL='/static/'
STATICFILES_DIRS=[BASE_DIR/'static']
LOGIN_REDIRECT_URL='/'
LOGOUT_REDIRECT_URL='/'

LOGIN_URL = '/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# SMS settings
SMS_BACKEND = os.getenv('SMS_BACKEND', 'console')  # console | kavenegar
KAVENEGAR_API_KEY = os.getenv('KAVENEGAR_API_KEY', '')
KAVENEGAR_SENDER = os.getenv('KAVENEGAR_SENDER', '')

# Email settings (dev defaults to console backend)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@example.com')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'

# Email OTP settings
EMAIL_OTP_LENGTH = int(os.getenv('EMAIL_OTP_LENGTH', '6'))
EMAIL_OTP_TTL_SECONDS = int(os.getenv('EMAIL_OTP_TTL_SECONDS', '300'))
EMAIL_OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv('EMAIL_OTP_RESEND_COOLDOWN_SECONDS', '60'))
EMAIL_OTP_MAX_SEND_PER_WINDOW = int(os.getenv('EMAIL_OTP_MAX_SEND_PER_WINDOW', '3'))
EMAIL_OTP_SEND_WINDOW_SECONDS = int(os.getenv('EMAIL_OTP_SEND_WINDOW_SECONDS', '600'))
EMAIL_OTP_MAX_VERIFY_ATTEMPTS = int(os.getenv('EMAIL_OTP_MAX_VERIFY_ATTEMPTS', '5'))
