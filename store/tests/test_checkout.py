from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from core.models import DiscountCode, DiscountRedemption
from core.models import ShippingSettings
from store.models import CartItem, Category, Order, OrderItem, Product


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

    def test_checkout_creates_single_order_for_multiple_items(self):
        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self.client.force_login(self.user)

        product2 = Product.objects.create(
            name="محصول دوم",
            description="توضیحات",
            price=50000,
            domain="test",
            category=self.category,
        )
        CartItem.objects.create(user=self.user, product=self.product, quantity=1)
        CartItem.objects.create(user=self.user, product=product2, quantity=2)  # 100000

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "علی",
                "last_name": "رضایی",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
                "address": "تهران، خیابان مثال، پلاک ۱",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        order = Order.objects.get(user=self.user)
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 2)
        self.assertEqual(response["Location"], reverse("payment", args=[order.id]))
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

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
                "address": "تهران، خیابان مثال، پلاک ۱",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_price, 160000)
        self.assertEqual(order.shipping_fee_per_item, 10000)
        self.assertEqual(order.shipping_item_count, 1)
        self.assertEqual(order.shipping_total, 10000)
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
                "address": "تهران، خیابان مثال، پلاک ۱",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_price, 300000)
        self.assertEqual(order.shipping_total, 0)
        self.assertTrue(order.shipping_is_free)
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
                "address": "تهران، خیابان مثال، پلاک ۱",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.assertTrue(CartItem.objects.filter(user=self.user).exists())

        content = response.content.decode("utf-8")
        self.assertIn("شماره موبایل تایید نشده است", content)
        self.assertIn(reverse("phone_otp_verify_page"), content)

    def test_discount_code_applies_to_items_only(self):
        DiscountCode.objects.create(code="OFF10", percent=10, is_active=True, is_public=False)

        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart(quantity=1)  # 150000

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "علی",
                "last_name": "رضایی",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
                "discount_code": "OFF10",
                "discount_code_applied": "OFF10",
                "address": "تهران، خیابان مثال، پلاک ۱",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_price, 145000)
        self.assertEqual(order.items_subtotal, 150000)
        self.assertEqual(order.discount_amount, 15000)
        self.assertEqual(order.shipping_total, 10000)

    def test_discount_code_max_uses_rejects_when_limit_reached(self):
        DiscountCode.objects.create(
            code="LIMIT1",
            percent=10,
            is_active=True,
            is_public=False,
            max_uses=1,
            uses_count=1,
        )

        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart(quantity=1)

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "تست",
                "last_name": "کاربر",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
                "discount_code": "LIMIT1",
                "discount_code_applied": "LIMIT1",
                "address": "خیابان تست",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.assertIn("ظرفیت استفاده از این کد تکمیل شده است.", response.content.decode("utf-8"))

    def test_discount_code_assigned_user_only(self):
        other = User.objects.create_user(username="u2", password="pass12345", email="u2@example.com")
        DiscountCode.objects.create(
            code="PRIVATE10",
            percent=10,
            is_active=True,
            is_public=False,
            assigned_user=other,
        )

        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart(quantity=1)

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "تست",
                "last_name": "کاربر",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
                "discount_code": "PRIVATE10",
                "discount_code_applied": "PRIVATE10",
                "address": "خیابان تست",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("فقط برای کاربر مشخص شده", response.content.decode("utf-8"))

        DiscountCode.objects.filter(code="PRIVATE10").update(assigned_user=self.user)
        response_ok = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "تست",
                "last_name": "کاربر",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
                "discount_code": "PRIVATE10",
                "discount_code_applied": "PRIVATE10",
                "address": "خیابان تست",
            },
        )
        self.assertEqual(response_ok.status_code, 302)

    def test_discount_code_per_user_limit(self):
        code = DiscountCode.objects.create(
            code="ONCE",
            percent=10,
            is_active=True,
            is_public=False,
            max_uses_per_user=1,
        )
        DiscountRedemption.objects.create(discount_code=code, user=self.user, order_id=1)

        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])
        self._login_and_seed_cart(quantity=1)

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "تست",
                "last_name": "کاربر",
                "phone": "09120000000",
                "province": "تهران",
                "city": "تهران",
                "discount_code": "ONCE",
                "discount_code_applied": "ONCE",
                "address": "خیابان تست",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("قبلاً توسط شما استفاده شده است", response.content.decode("utf-8"))

    def test_checkout_does_not_update_account_profile_fields(self):
        self.user.first_name = "Account"
        self.user.last_name = "Owner"
        self.user.save(update_fields=["first_name", "last_name"])

        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])

        self._login_and_seed_cart(quantity=1)

        response = self.client.post(
            reverse("checkout"),
            data={
                "recipient_is_other": "1",
                "first_name": "Receiver",
                "last_name": "Person",
                "phone": "09129999999",
                "province": "تهران",
                "city": "تهران",
                "address": "تهران، خیابان مثال، پلاک ۱",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Account")
        self.assertEqual(self.user.last_name, "Owner")
        self.assertEqual(self.profile.phone, "09120000000")
        self.assertTrue(self.profile.phone_verified)

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.first_name, "Receiver")
        self.assertEqual(order.last_name, "Person")
        self.assertEqual(order.phone, "09129999999")

    def test_checkout_uses_account_fields_when_recipient_toggle_off(self):
        self.user.first_name = "Account"
        self.user.last_name = "Owner"
        self.user.save(update_fields=["first_name", "last_name"])

        self.profile.phone = "09120000000"
        self.profile.phone_verified = True
        self.profile.save(update_fields=["phone", "phone_verified"])

        self._login_and_seed_cart(quantity=1)

        response = self.client.post(
            reverse("checkout"),
            data={
                "first_name": "Receiver",
                "last_name": "Person",
                "phone": "09129999999",
                "province": "تهران",
                "city": "تهران",
                "address": "تهران، خیابان مثال، پلاک ۱",
            },
        )
        self.assertEqual(response.status_code, 302)

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.first_name, "Account")
        self.assertEqual(order.last_name, "Owner")
        self.assertEqual(order.phone, "09120000000")
