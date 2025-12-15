from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from store.models import CartItem, Category, Product


class CartDrawerTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="دسته‌بندی")
        self.product = Product.objects.create(
            name="محصول تست",
            description="توضیحات",
            price=120000,
            domain="test",
            category=self.category,
        )

    def test_guest_add_to_cart_stores_in_session_and_redirects_with_cart_open(self):
        url = reverse("add_to_cart", args=[self.product.id])
        response = self.client.get(f"{url}?next=/shop/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/shop/?"))
        self.assertIn("cart_open=1", response["Location"])

        session = self.client.session
        self.assertIn("cart", session)
        self.assertEqual(session["cart"].get(str(self.product.id)), 1)

    def test_guest_cart_preview_returns_items(self):
        add_url = reverse("add_to_cart", args=[self.product.id])
        self.client.get(add_url)

        preview_url = reverse("cart_preview")
        response = self.client.get(preview_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["total"], 120000)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id"], self.product.id)
        self.assertEqual(data["items"][0]["quantity"], 1)

    def test_session_cart_merges_into_user_cart_on_cart_view(self):
        add_url = reverse("add_to_cart", args=[self.product.id])
        self.client.get(add_url)

        user = User.objects.create_user(username="u1", password="pass12345")
        self.client.force_login(user)

        cart_url = reverse("cart")
        response = self.client.get(cart_url)
        self.assertEqual(response.status_code, 200)

        item = CartItem.objects.get(user=user, product=self.product)
        self.assertEqual(item.quantity, 1)

        session = self.client.session
        self.assertEqual(session.get("cart", {}), {})

    def test_guest_can_remove_item_from_session_cart(self):
        add_url = reverse("add_to_cart", args=[self.product.id])
        self.client.get(add_url)

        remove_url = reverse("cart_remove")
        response = self.client.post(
            remove_url,
            data={"product_id": self.product.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("total"), 0)
        self.assertEqual(data.get("items"), [])

        session = self.client.session
        self.assertEqual(session.get("cart", {}), {})

    def test_user_can_remove_item_from_db_cart(self):
        user = User.objects.create_user(username="u1", password="pass12345")
        self.client.force_login(user)
        CartItem.objects.create(user=user, product=self.product, quantity=2)

        remove_url = reverse("cart_remove")
        response = self.client.post(
            remove_url,
            data={"product_id": self.product.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("total"), 0)
        self.assertEqual(data.get("items"), [])

        self.assertFalse(CartItem.objects.filter(user=user).exists())
