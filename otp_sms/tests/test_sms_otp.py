from datetime import timedelta
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from django_otp import DEVICE_ID_SESSION_KEY

from accounts.models import UserProfile
from otp_sms.models import SmsOTPDevice


@override_settings(
    SMS_OTP_LENGTH=6,
    SMS_OTP_TTL_SECONDS=300,
    SMS_OTP_RESEND_COOLDOWN_SECONDS=60,
    SMS_OTP_MAX_SEND_PER_WINDOW=3,
    SMS_OTP_SEND_WINDOW_SECONDS=600,
    SMS_OTP_MAX_VERIFY_ATTEMPTS=5,
)
class SmsOTPDeviceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password")
        self.device = SmsOTPDevice.objects.create(user=self.user, phone="09120000000", name="SMS")

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

    def test_send_challenge_sends_sms(self):
        with patch("otp_sms.models.send_sms") as send_sms:
            self.device.send_challenge()
            self.assertEqual(send_sms.call_count, 1)
            _to, message = send_sms.call_args[0]
            match = re.search(r"(?<!\d)(\d{6})(?!\d)", message)
            self.assertIsNotNone(match, message)

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
    SMS_OTP_LENGTH=6,
    SMS_OTP_TTL_SECONDS=300,
    SMS_OTP_RESEND_COOLDOWN_SECONDS=60,
    SMS_OTP_MAX_SEND_PER_WINDOW=3,
    SMS_OTP_SEND_WINDOW_SECONDS=600,
    SMS_OTP_MAX_VERIFY_ATTEMPTS=5,
)
class SmsOTPViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="bob", password="password", email="bob@example.com"
        )
        UserProfile.objects.create(user=self.user, phone="09121111111")
        self.client.login(username="bob", password="password")

    def test_request_and_verify_flow_sets_otp_session(self):
        with patch("otp_sms.models.send_sms") as send_sms:
            resp = self.client.post(
                "/auth/sms-otp/request/",
                data={"phone": "09121111111"},
            )
            self.assertEqual(resp.status_code, 200, resp.content.decode("utf-8", "ignore"))
            self.assertEqual(send_sms.call_count, 1)

            _to, message = send_sms.call_args[0]
            match = re.search(r"(?<!\d)(\d{6})(?!\d)", message)
            self.assertIsNotNone(match, message)
            token = match.group(1)

        resp = self.client.post(
            "/auth/sms-otp/verify/",
            data={"phone": "09121111111", "token": token},
        )
        self.assertEqual(resp.status_code, 200, resp.content.decode("utf-8", "ignore"))

        session = self.client.session
        self.assertIn(DEVICE_ID_SESSION_KEY, session)
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.phone_verified)
