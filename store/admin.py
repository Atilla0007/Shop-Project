from django.contrib import admin
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import format_html

from accounts.sms import send_sms
from .emails import send_order_payment_approved_email
from .models import CartItem, Category, ManualInvoiceSequence, Order, OrderItem, Product, ProductReview, ShippingAddress


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "domain", "price", "is_available", "view_count", "sales_count")
    list_filter = ("category", "domain", "is_available")
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
        if order.payment_status == "approved":
            try:
                send_order_payment_approved_email(order=order)
            except Exception:
                pass
        else:
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
        if order.payment_status == "approved":
            continue
        order.payment_status = "approved"
        order.status = "paid"
        order.payment_reviewed_at = now
        order.save(update_fields=["payment_status", "status", "payment_reviewed_at"])
        _notify_order(order, "تایید پرداخت سفارش", f"پرداخت سفارش شماره {order.id} تایید شد. ممنون از خرید شما.")
        order.mark_sales_counted()


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
    list_display = ("id", "receipt_preview", "user", "status", "payment_status", "payment_method", "total_price", "created_at")
    list_display_links = ("id",)
    list_editable = ("status", "payment_status")
    list_filter = ("status", "payment_status", "payment_method", "created_at")
    search_fields = ("id", "user__username", "phone", "email")
    readonly_fields = ("created_at", "payment_submitted_at", "payment_reviewed_at")
    inlines = [OrderItemInline]
    actions = [approve_payment, reject_payment]

    def save_model(self, request, obj, form, change):
        payment_status_changed = bool(
            change and form and "payment_status" in getattr(form, "changed_data", [])
        )
        previous_payment_status = form.initial.get("payment_status") if payment_status_changed else None

        if payment_status_changed and previous_payment_status != obj.payment_status:
            now = timezone.now()
            obj.payment_reviewed_at = now
            if obj.payment_status == "approved":
                if obj.status != "canceled":
                    obj.status = "paid"
            elif obj.payment_status == "rejected":
                obj.status = "canceled"

        super().save_model(request, obj, form, change)

        if payment_status_changed and previous_payment_status != obj.payment_status:
            if obj.payment_status == "approved":
                _notify_order(
                    obj,
                    "تایید پرداخت سفارش شما",
                    f"پرداخت سفارش شماره {obj.id} تایید شد. سفارش شما در حال پردازش است.",
                )
                obj.mark_sales_counted()
            elif obj.payment_status == "rejected":
                _notify_order(
                    obj,
                    "رد پرداخت سفارش شما",
                    f"پرداخت سفارش شماره {obj.id} رد شد و سفارش لغو گردید. لطفاً برای بررسی با پشتیبانی هماهنگ کنید.",
                )
    def receipt_preview(self, obj: Order):
        if not obj.receipt_file:
            return "—"
        url = obj.receipt_file.url
        lower = url.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            return format_html(
                '<a href="{}" target="_blank" rel="noopener"><img src="{}" alt="فیش" style="height:48px;width:48px;object-fit:cover;border-radius:10px;border:1px solid rgba(0,0,0,0.15)" /></a>',
                url,
                url,
            )
        return format_html('<a href="{}" target="_blank" rel="noopener">مشاهده فایل</a>', url)

    receipt_preview.short_description = "فیش"


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "name", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("product__name", "name", "comment")
    list_editable = ("is_approved",)


@admin.register(ManualInvoiceSequence)
class ManualInvoiceSequenceAdmin(admin.ModelAdmin):
    list_display = ("id", "last_number", "updated_at")
    readonly_fields = ("updated_at",)


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "province", "is_default", "updated_at")
    list_filter = ("is_default", "province")
    search_fields = ("label", "city", "province", "address", "user__username", "user__email", "phone")
