
from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.IntegerField()
    domain = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    # فیلدهای جدید
    brand = models.CharField("برند", max_length=100, blank=True)
    sku = models.CharField("شناسه محصول", max_length=50, blank=True)
    tags = models.CharField(
        "برچسب‌ها",
        max_length=250,
        blank=True,
        help_text="تگ‌ها را با , از هم جدا کنید"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"

    def __str__(self):
        return self.name


class ProductFeature(models.Model):
    """ویژگی‌های فنی محصول برای نمایش و مقایسه"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="features")
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=200)

    class Meta:
        verbose_name = "ویژگی محصول"
        verbose_name_plural = "ویژگی‌های محصول"

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "آیتم سبد خرید"
        verbose_name_plural = "آیتم‌های سبد خرید"

    def total_price(self):
        return self.quantity * self.product.price

    def __str__(self):
        return f"{self.user} - {self.product} ({self.quantity})"

class Order(models.Model):
    STATUS_CHOICES = (
        ('new', 'جدید'),
        ('unpaid', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده'),
        ('sent', 'ارسال شده'),
        ('done', 'تکمیل شده'),
        ('canceled', 'لغو شده'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('card_to_card', 'کارت به کارت'),
        ('contact_admin', 'ارتباط با ادمین'),
    )
    PAYMENT_STATUS_CHOICES = (
        ('unpaid', 'در انتظار پرداخت'),
        ('submitted', 'برای بررسی ارسال شد'),
        ('approved', 'تایید شد'),
        ('rejected', 'رد شد'),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    note = models.TextField(blank=True)

    items_subtotal = models.PositiveIntegerField(default=0)
    discount_code = models.CharField(max_length=50, blank=True)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    discount_amount = models.PositiveIntegerField(default=0)

    shipping_fee_per_item = models.PositiveIntegerField(default=0)
    shipping_item_count = models.PositiveIntegerField(default=0)
    shipping_total_full = models.PositiveIntegerField(default=0)
    shipping_total = models.PositiveIntegerField(default=0)
    shipping_is_free = models.BooleanField(default=False)
    free_shipping_min_total = models.PositiveIntegerField(default=0)

    payment_method = models.CharField(max_length=32, choices=PAYMENT_METHOD_CHOICES, blank=True)
    payment_status = models.CharField(max_length=32, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    receipt_file = models.FileField(upload_to='payments/receipts/', null=True, blank=True)
    payment_submitted_at = models.DateTimeField(null=True, blank=True)
    payment_reviewed_at = models.DateTimeField(null=True, blank=True)
    receipt_digest_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"

    def __str__(self):
        return f"سفارش #{self.id} - {self.user or 'مهمان'}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.IntegerField()

    class Meta:
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
