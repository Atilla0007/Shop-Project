from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.models import Category, Order, OrderItem, Product


class ProductMetricsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="user", password="pass")
        self.category = Category.objects.create(name="Test")
        self.product = Product.objects.create(
            name="Item",
            description="desc",
            price=10000,
            domain="Test",
            category=self.category,
        )

    def test_product_view_count_increments(self):
        url = reverse("product_detail", args=[self.product.id])
        self.client.get(url)
        self.product.refresh_from_db()
        self.assertEqual(self.product.view_count, 1)

    def test_sales_count_updates_on_order_approval(self):
        order = Order.objects.create(
            user=self.user,
            total_price=10000,
            status="paid",
            payment_status="approved",
        )
        OrderItem.objects.create(order=order, product=self.product, quantity=2, unit_price=10000)

        order.mark_sales_counted()
        self.product.refresh_from_db()
        self.assertEqual(self.product.sales_count, 2)

    def test_review_submission_creates_pending_review(self):
        url = reverse("product_detail", args=[self.product.id])
        response = self.client.post(
            url,
            data={
                "name": "Test User",
                "email": "test@example.com",
                "rating": 5,
                "comment": "Good product",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.reviews.count(), 1)
        review = self.product.reviews.first()
        self.assertFalse(review.is_approved)

        order.mark_sales_counted()
        self.product.refresh_from_db()
        self.assertEqual(self.product.sales_count, 2)
