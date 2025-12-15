from django.contrib import admin
from django.core.mail import send_mail
from django.utils import timezone

from accounts.sms import send_sms
from .models import CartItem, Category, Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "domain", "price")
    list_filter = ("category", "domain")
    search_fields = ("name", "domain")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "quantity")
    list_filter = ("user",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price")


def _notify_order(order: Order, subject: str, message: str) -> None:
    to_email = (order.email or (order.user.email if order.user else "")).strip()
    if to_email:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[to_email],
            fail_silently=True,
        )
    if order.phone:
        send_sms(order.phone, message)


@admin.action(description="تایید پرداخت و تغییر وضعیت به پرداخت شده")
def approve_payment(modeladmin, request, queryset):
    now = timezone.now()
    for order in queryset:
        if order.status == "canceled":
            continue
        order.payment_status = "approved"
        order.status = "paid"
        order.payment_reviewed_at = now
        order.save(update_fields=["payment_status", "status", "payment_reviewed_at"])
        _notify_order(order, "تایید پرداخت سفارش", f"پرداخت سفارش شماره {order.id} تایید شد. ممنون از خرید شما.")


@admin.action(description="رد پرداخت و لغو سفارش")
def reject_payment(modeladmin, request, queryset):
    now = timezone.now()
    for order in queryset:
        order.payment_status = "rejected"
        order.status = "canceled"
        order.payment_reviewed_at = now
        order.save(update_fields=["payment_status", "status", "payment_reviewed_at"])
        _notify_order(
            order,
            "رد پرداخت سفارش",
            f"پرداخت سفارش شماره {order.id} تایید نشد و سفارش لغو شد. لطفاً برای پیگیری با پشتیبانی تماس بگیرید.",
        )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "payment_status", "payment_method", "total_price", "created_at")
    list_filter = ("status", "payment_status", "payment_method", "created_at")
    search_fields = ("id", "user__username", "phone", "email")
    readonly_fields = ("created_at", "payment_submitted_at", "payment_reviewed_at")
    inlines = [OrderItemInline]
    actions = [approve_payment, reject_payment]

