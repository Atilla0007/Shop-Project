from datetime import timedelta
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from django_otp import DEVICE_ID_SESSION_KEY

from otp_email.models import EmailOTPDevice


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
    EMAIL_OTP_LENGTH=6,
    EMAIL_OTP_TTL_SECONDS=300,
    EMAIL_OTP_RESEND_COOLDOWN_SECONDS=60,
    EMAIL_OTP_MAX_SEND_PER_WINDOW=3,
    EMAIL_OTP_SEND_WINDOW_SECONDS=600,
    EMAIL_OTP_MAX_VERIFY_ATTEMPTS=5,
)
class EmailOTPDeviceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alice", password="password", email="alice@example.com"
        )
        self.device = EmailOTPDevice.objects.create(
            user=self.user, email="alice@example.com", name="Email"
        )

    def test_generate_token_hashes_and_sets_expiry(self):
        token = self.device.generate_token()
        self.device.refresh_from_db()

        self.assertIsNotNone(self.device.token_hash)
        self.assertTrue(self.device.token_salt)
        self.assertIsNotNone(self.device.valid_until)
        self.assertNotIn(token, self.device.token_hash)

    def test_expired_token_fails(self):
        token = self.device.generate_token()
        self.device.valid_until = timezone.now() - timedelta(seconds=1)
        self.device.save(update_fields=["valid_until"])
        self.assertFalse(self.device.verify_token(token))

    def test_verify_success_invalidates_token(self):
        token = self.device.generate_token()
        self.assertTrue(self.device.verify_token(token))
        self.device.refresh_from_db()
        self.assertIsNone(self.device.token_hash)
        self.assertIsNone(self.device.valid_until)
        self.assertEqual(self.device.verify_fail_count, 0)

    def test_throttle_cooldown_blocks(self):
        self.device.last_sent_at = timezone.now()
        self.device.save(update_fields=["last_sent_at"])
        allowed, info = self.device.generate_is_allowed()
        self.assertFalse(allowed)
        self.assertIn("retry_after_seconds", info)

    def test_throttle_window_cap_blocks(self):
        now = timezone.now()
        self.device.send_count_window_start = now
        self.device.send_count_in_window = 3
        self.device.save(update_fields=["send_count_window_start", "send_count_in_window"])
        allowed, info = self.device.generate_is_allowed()
        self.assertFalse(allowed)
        self.assertIn("retry_after_seconds", info)

    def test_throttle_window_resets_after_window(self):
        now = timezone.now()
        self.device.send_count_window_start = now - timedelta(seconds=601)
        self.device.send_count_in_window = 3
        self.device.save(update_fields=["send_count_window_start", "send_count_in_window"])
        allowed, _info = self.device.generate_is_allowed()
        self.assertTrue(allowed)

    def test_send_challenge_sends_email(self):
        self.device.send_challenge()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.token_hash)
        self.assertIsNotNone(self.device.valid_until)
        self.assertEqual(self.device.send_count_in_window, 1)

    def test_verify_attempt_lockout_after_max_failures(self):
        self.device.generate_token()
        for _ in range(5):
            self.assertFalse(self.device.verify_token("000000"))
            self.device.refresh_from_db()

        allowed, _info = self.device.verify_is_allowed()
        self.assertFalse(allowed)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.token_hash)
        self.assertIsNone(self.device.valid_until)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
    EMAIL_OTP_LENGTH=6,
    EMAIL_OTP_TTL_SECONDS=300,
    EMAIL_OTP_RESEND_COOLDOWN_SECONDS=60,
    EMAIL_OTP_MAX_SEND_PER_WINDOW=3,
    EMAIL_OTP_SEND_WINDOW_SECONDS=600,
    EMAIL_OTP_MAX_VERIFY_ATTEMPTS=5,
)
class EmailOTPViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="bob", password="password", email="bob@example.com"
        )
        self.client.login(username="bob", password="password")

    def test_request_and_verify_flow_sets_otp_session(self):
        resp = self.client.post(
            "/auth/email-otp/request/",
            data={"email": "bob@example.com"},
        )
        self.assertEqual(resp.status_code, 200, resp.content.decode("utf-8", "ignore"))
        self.assertEqual(len(mail.outbox), 1)

        body = mail.outbox[0].body
        match = re.search(r"(?<!\d)(\d{6})(?!\d)", body)
        self.assertIsNotNone(match, body)
        token = match.group(1)

        resp = self.client.post(
            "/auth/email-otp/verify/",
            data={"email": "bob@example.com", "token": token},
        )
        self.assertEqual(resp.status_code, 200, resp.content.decode("utf-8", "ignore"))
        session = self.client.session
        self.assertIn(DEVICE_ID_SESSION_KEY, session)
