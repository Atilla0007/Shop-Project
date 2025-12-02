
from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name



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


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "آیتم سبد خرید"
    ...
    def total_price(self):
        return self.quantity * self.product.price


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

from django.contrib.auth.models import User

class Order(models.Model):
    STATUS_CHOICES = (
        ('new', 'جدید'),
        ('paid', 'پرداخت شده'),
        ('sent', 'ارسال شده'),
        ('done', 'تکمیل شده'),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

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
