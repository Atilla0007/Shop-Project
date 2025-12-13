# Email OTP (django-otp plugin)

This app adds an email-based OTP device using the `django-otp` framework.

## Setup

- Add apps and middleware:
  - `django_otp` and `otp_email` in `INSTALLED_APPS`
  - `django_otp.middleware.OTPMiddleware` after `django.contrib.auth.middleware.AuthenticationMiddleware`

- Include URLs:
  - `path('', include('otp_email.urls'))`

## Endpoints

- `POST /auth/email-otp/request/` JSON or form data: `{ "email": "user@example.com" }`
- `POST /auth/email-otp/verify/` JSON or form data: `{ "email": "user@example.com", "token": "123456" }`

On successful verification, `django_otp.login(request, device)` is called and the verified device is persisted in the session.

## Settings

Email backend (defaults to console backend for local dev):

- `EMAIL_BACKEND`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`

OTP tuning:

- `EMAIL_OTP_LENGTH` (default `6`)
- `EMAIL_OTP_TTL_SECONDS` (default `300`)
- `EMAIL_OTP_RESEND_COOLDOWN_SECONDS` (default `60`)
- `EMAIL_OTP_MAX_SEND_PER_WINDOW` (default `3`)
- `EMAIL_OTP_SEND_WINDOW_SECONDS` (default `600`)
- `EMAIL_OTP_MAX_VERIFY_ATTEMPTS` (default `5`)

Optional:

- `EMAIL_OTP_SUBJECT`
- `EMAIL_OTP_BODY_TEMPLATE` (uses `{token}` and `{minutes}`)

