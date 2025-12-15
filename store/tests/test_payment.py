import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from store.models import Order


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass12345", email="u1@example.com")
        self.client.force_login(self.user)

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

    def test_contact_admin_payment_sets_submitted(self):
        response = self.client.post(
            reverse("payment", args=[self.order.id]),
            data={"method": "contact_admin"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_method, "contact_admin")
        self.assertEqual(self.order.payment_status, "submitted")

    def test_card_to_card_requires_receipt(self):
        response = self.client.post(
            reverse("payment", args=[self.order.id]),
            data={"method": "card_to_card"},
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "unpaid")

    def test_card_to_card_upload_sets_receipt(self):
        receipt = SimpleUploadedFile("receipt.png", b"fakepng", content_type="image/png")
        response = self.client.post(
            reverse("payment", args=[self.order.id]),
            data={"method": "card_to_card", "receipt": receipt},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_method, "card_to_card")
        self.assertEqual(self.order.payment_status, "submitted")
        self.assertTrue(bool(self.order.receipt_file))

    def test_proforma_pdf_download(self):
        response = self.client.get(reverse("proforma_pdf", args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

