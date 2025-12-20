from django.contrib import admin

from .models import ContactMessage, DiscountCode, DiscountRedemption, News, PaymentSettings, ShippingSettings


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "created_at")
    search_fields = ("name", "email")


@admin.register(ShippingSettings)
class ShippingSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "shipping_fee", "free_shipping_min_total", "updated_at")
    list_display_links = ("id",)
    list_editable = ("shipping_fee", "free_shipping_min_total")

    def has_add_permission(self, request):
        return not ShippingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "percent",
        "is_active",
        "is_public",
        "assigned_user",
        "uses_count",
        "max_uses",
        "max_uses_per_user",
        "updated_at",
    )
    list_editable = ("is_active", "is_public")
    search_fields = ("code", "assigned_user__username", "assigned_user__email")
    list_filter = ("is_active", "is_public")


@admin.register(DiscountRedemption)
class DiscountRedemptionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "discount_code", "user", "order_id")
    search_fields = ("discount_code__code", "user__username", "user__email")
    list_filter = ("created_at",)


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "card_number", "card_holder", "telegram_username", "whatsapp_number", "updated_at")
    list_display_links = ("id",)
    list_editable = ("card_number", "card_holder", "telegram_username", "whatsapp_number")

    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
