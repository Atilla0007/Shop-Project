import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import PaymentSettings
from store.models import Order


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
)
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass12345", email="u1@example.com")
        self.client.force_login(self.user)

        PaymentSettings.objects.update_or_create(
            pk=1,
            defaults={
                "card_number": "6037991234567890",
                "card_holder": "استیرا",
                "telegram_username": "@styra_support",
                "whatsapp_number": "+989111111111",
            },
        )

        self.order = Order.objects.create(
            user=self.user,
            total_price=123000,
            status="unpaid",
            payment_status="unpaid",
            items_subtotal=120000,
            shipping_total=3000,
            shipping_item_count=1,
            shipping_fee_per_item=3000,
            shipping_total_full=3000,
        )

    def test_payment_page_renders(self):
        response = self.client.get(reverse("payment", args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_admin_payment_sets_submitted(self):
        response = self.client.post(
            reverse("payment_contact_admin", args=[self.order.id]),
            data={},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_method, "contact_admin")
        self.assertEqual(self.order.payment_status, "submitted")
        self.assertEqual(len(mail.outbox), 1)
        attachments = mail.outbox[0].attachments
        self.assertTrue(any(name.endswith(".pdf") for (name, _content, _mime) in attachments))
        pdf = next(content for (name, content, _mime) in attachments if name.endswith(".pdf"))
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_card_to_card_requires_receipt(self):
        response = self.client.post(
            reverse("payment_card_to_card", args=[self.order.id]),
            data={},
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "unpaid")
        self.assertEqual(len(mail.outbox), 0)

    def test_card_to_card_upload_sets_receipt(self):
        receipt = SimpleUploadedFile("receipt.png", b"fakepng", content_type="image/png")
        response = self.client.post(
            reverse("payment_card_to_card", args=[self.order.id]),
            data={"receipt": receipt},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_method, "card_to_card")
        self.assertEqual(self.order.payment_status, "submitted")
        self.assertTrue(bool(self.order.receipt_file))
        self.assertEqual(Path(self.order.receipt_file.name).name, f"{self.order.id:07d}.png")
        self.assertEqual(len(mail.outbox), 1)
        attachments = mail.outbox[0].attachments
        self.assertTrue(any(name.endswith(".pdf") for (name, _content, _mime) in attachments))

    def test_proforma_pdf_download(self):
        response = self.client.get(reverse("proforma_pdf", args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
