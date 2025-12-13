import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from django_otp.models import Device, GenerateNotAllowed, VerifyNotAllowed


def _new_salt() -> str:
    return secrets.token_urlsafe(16)


def _settings_int(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


class EmailOTPDevice(Device):
    email = models.EmailField(db_index=True)

    token_hash = models.CharField(max_length=128, null=True, blank=True)
    token_salt = models.CharField(max_length=64, default=_new_salt)
    valid_until = models.DateTimeField(null=True, blank=True)

    last_sent_at = models.DateTimeField(null=True, blank=True)
    send_count_window_start = models.DateTimeField(null=True, blank=True)
    send_count_in_window = models.PositiveIntegerField(default=0)

    verify_fail_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "email"], name="uniq_email_otp_device_user_email"
            )
        ]

    @staticmethod
    def _hash_token(token: str, salt: str) -> str:
        iterations = _settings_int("EMAIL_OTP_HASH_ITERATIONS", 260_000)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            token.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return digest.hex()

    def _get_token_settings(self) -> tuple[int, int]:
        length = _settings_int("EMAIL_OTP_LENGTH", 6)
        ttl_seconds = _settings_int("EMAIL_OTP_TTL_SECONDS", 300)
        return length, ttl_seconds

    def generate_token(self) -> str:
        length, ttl_seconds = self._get_token_settings()
        token = "".join(str(secrets.randbelow(10)) for _ in range(length))
        salt = _new_salt()
        self.token_salt = salt
        self.token_hash = self._hash_token(token, salt)
        self.valid_until = timezone.now() + timedelta(seconds=ttl_seconds)
        self.verify_fail_count = 0
        self.save(
            update_fields=["token_salt", "token_hash", "valid_until", "verify_fail_count"]
        )
        return token

    def verify_is_allowed(self):
        max_attempts = _settings_int("EMAIL_OTP_MAX_VERIFY_ATTEMPTS", 5)
        if self.verify_fail_count >= max_attempts:
            return (
                False,
                {
                    "reason": VerifyNotAllowed.N_FAILED_ATTEMPTS,
                    "failure_count": self.verify_fail_count,
                },
            )
        return (True, None)

    def verify_token(self, token: str) -> bool:
        is_allowed, _data = self.verify_is_allowed()
        if not is_allowed:
            return False

        now = timezone.now()
        if not self.token_hash or not self.valid_until or now >= self.valid_until:
            return False

        expected_hash = self.token_hash
        candidate_hash = self._hash_token(token, self.token_salt)
        if constant_time_compare(candidate_hash, expected_hash):
            self.token_hash = None
            self.valid_until = None
            self.verify_fail_count = 0
            self.save(update_fields=["token_hash", "valid_until", "verify_fail_count"])
            return True

        self.verify_fail_count += 1
        max_attempts = _settings_int("EMAIL_OTP_MAX_VERIFY_ATTEMPTS", 5)
        if self.verify_fail_count >= max_attempts:
            self.token_hash = None
            self.valid_until = None
            self.save(update_fields=["verify_fail_count", "token_hash", "valid_until"])
        else:
            self.save(update_fields=["verify_fail_count"])
        return False

    def can_send(self) -> bool:
        now = timezone.now()
        cooldown_seconds = _settings_int("EMAIL_OTP_RESEND_COOLDOWN_SECONDS", 60)
        if self.last_sent_at and (
            now - self.last_sent_at
        ).total_seconds() < cooldown_seconds:
            return False

        window_seconds = _settings_int("EMAIL_OTP_SEND_WINDOW_SECONDS", 600)
        window_start = self.send_count_window_start
        if (not window_start) or (now - window_start).total_seconds() >= window_seconds:
            return True

        max_send = _settings_int("EMAIL_OTP_MAX_SEND_PER_WINDOW", 3)
        return self.send_count_in_window < max_send

    def generate_is_allowed(self):
        now = timezone.now()

        cooldown_seconds = _settings_int("EMAIL_OTP_RESEND_COOLDOWN_SECONDS", 60)
        if self.last_sent_at:
            seconds_since = (now - self.last_sent_at).total_seconds()
            if seconds_since < cooldown_seconds:
                return (
                    False,
                    {
                        "reason": GenerateNotAllowed.COOLDOWN_DURATION_PENDING,
                        "retry_after_seconds": int(cooldown_seconds - seconds_since),
                    },
                )

        window_seconds = _settings_int("EMAIL_OTP_SEND_WINDOW_SECONDS", 600)
        window_start = self.send_count_window_start
        if (not window_start) or (now - window_start).total_seconds() >= window_seconds:
            return (True, None)

        max_send = _settings_int("EMAIL_OTP_MAX_SEND_PER_WINDOW", 3)
        if self.send_count_in_window >= max_send:
            retry_after_seconds = int(window_seconds - (now - window_start).total_seconds())
            return (
                False,
                {
                    "error_message": "Too many OTP requests. Try again later.",
                    "retry_after_seconds": max(retry_after_seconds, 0),
                },
            )

        return (True, None)

    def send_challenge(self) -> None:
        is_allowed, data = self.generate_is_allowed()
        if not is_allowed:
            raise PermissionError(data or {})

        now = timezone.now()
        window_seconds = _settings_int("EMAIL_OTP_SEND_WINDOW_SECONDS", 600)
        if (not self.send_count_window_start) or (
            (now - self.send_count_window_start).total_seconds() >= window_seconds
        ):
            self.send_count_window_start = now
            self.send_count_in_window = 0

        token = self.generate_token()

        self.last_sent_at = now
        self.send_count_in_window += 1
        self.save(
            update_fields=[
                "last_sent_at",
                "send_count_window_start",
                "send_count_in_window",
            ]
        )

        ttl_seconds = _settings_int("EMAIL_OTP_TTL_SECONDS", 300)
        minutes = max(1, int(ttl_seconds // 60))
        subject = getattr(settings, "EMAIL_OTP_SUBJECT", "Your Styra login code")
        body = getattr(
            settings,
            "EMAIL_OTP_BODY_TEMPLATE",
            "Your verification code is {token}. It expires in {minutes} minutes.",
        ).format(token=token, minutes=minutes)

        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[self.email],
            fail_silently=False,
        )

    def generate_challenge(self):
        self.send_challenge()
        return "Email OTP sent"

