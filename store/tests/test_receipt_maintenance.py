import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from store.models import Order


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class ReceiptMaintenanceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin1",
            password="pass12345",
            email="admin@example.com",
            is_staff=True,
        )
        self.user = User.objects.create_user(username="u1", password="pass12345", email="u1@example.com")

    def test_send_receipt_digest_sends_once_and_marks_sent(self):
        now = timezone.now()
        order = Order.objects.create(
            user=self.user,
            total_price=123000,
            status="unpaid",
            payment_status="submitted",
            payment_method="card_to_card",
            payment_submitted_at=now,
        )
        order.receipt_file.save("receipt.png", ContentFile(b"fakepng"), save=True)

        call_command("send_receipt_digest", date=timezone.localdate().isoformat())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertTrue(any(name.startswith(f"receipt-order-{order.id}-") for (name, _c, _m) in mail.outbox[0].attachments))

        order.refresh_from_db()
        self.assertIsNotNone(order.receipt_digest_sent_at)

        # Running again should not resend (because receipt_digest_sent_at is set)
        call_command("send_receipt_digest", date=timezone.localdate().isoformat())
        self.assertEqual(len(mail.outbox), 1)

    def test_cleanup_approved_receipts_removes_old_approved_only(self):
        media_root = Path(settings.MEDIA_ROOT)

        old_order = Order.objects.create(
            user=self.user,
            total_price=1000,
            status="paid",
            payment_status="approved",
            payment_method="card_to_card",
            payment_reviewed_at=timezone.now() - timedelta(hours=3),
        )
        old_order.receipt_file.save("old.png", ContentFile(b"old"), save=True)
        old_path = Path(old_order.receipt_file.path)
        self.assertTrue(old_path.exists())

        new_order = Order.objects.create(
            user=self.user,
            total_price=2000,
            status="paid",
            payment_status="approved",
            payment_method="card_to_card",
            payment_reviewed_at=timezone.now() - timedelta(hours=1),
        )
        new_order.receipt_file.save("new.png", ContentFile(b"new"), save=True)
        new_path = Path(new_order.receipt_file.path)
        self.assertTrue(new_path.exists())

        self.assertTrue(str(old_path).startswith(str(media_root)))
        self.assertTrue(str(new_path).startswith(str(media_root)))

        call_command("cleanup_approved_receipts", seconds=7200)

        old_order.refresh_from_db()
        new_order.refresh_from_db()
        self.assertFalse(bool(old_order.receipt_file))
        self.assertTrue(bool(new_order.receipt_file))
        self.assertFalse(old_path.exists())
        self.assertTrue(new_path.exists())
