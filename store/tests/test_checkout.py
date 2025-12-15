from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from core.models import ShippingSettings
from store.models import CartItem, Category, Order, Product


class CheckoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="دسته‌بندی")
        self.product = Product.objects.create(
            name="محصول تست",
            description="توضیحات",
            price=150000,
            domain="test",
            category=self.category,
        )
        self.user = User.objects.create_user(username="u1", password="pass12345", email="u1@example.com")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.email_verified = True
        self.profile.save(update_fields=["email_verified"])

        settings = ShippingSettings.get_solo()
        settings.shipping_fee = 10000
        settings.free_shipping_min_total = 200000
        settings.save(update_fields=["shipping_fee", "free_shipping_min_total"])

    def _login_and_seed_cart(self, quantity=1):
        self.client.force_login(self.user)
        CartItem.objects.create(user=self.user, product=self.product, quantity=quantity)

    def test_checkout_page_shows_items(self):
        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart()

        response = self.client.get(reverse("checkout"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("تسویه حساب", content)
        self.assertIn("محصول تست", content)

    def test_shipping_fee_applies_when_province_selected(self):
        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart(quantity=1)

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "علی",
                "last_name": "رضایی",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
            },
        )
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_price, 160000)
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_free_shipping_when_subtotal_over_threshold(self):
        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart(quantity=2)  # 300000

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "علی",
                "last_name": "رضایی",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
            },
        )
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_price, 300000)
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_unverified_phone_blocks_checkout_and_shows_modal(self):
        self.profile.phone = "09120000000"
        self.profile.phone_verified = False
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart()

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "علی",
                "last_name": "رضایی",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.assertTrue(CartItem.objects.filter(user=self.user).exists())

        content = response.content.decode("utf-8")
        self.assertIn("شماره موبایل تایید نشده است", content)
        self.assertIn(reverse("phone_otp_verify_page"), content)

