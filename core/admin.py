from django.contrib import admin
from .models import News, ContactMessage, ChatMessage, ChatThread, ShippingSettings, DiscountCode, PaymentSettings


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title',)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at')
    search_fields = ('name', 'email')


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__username',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('thread', 'sender', 'short_text', 'is_admin',
                    'is_read_by_admin', 'is_read_by_user', 'created_at')
    list_filter = ('is_admin', 'is_read_by_admin', 'is_read_by_user')
    search_fields = ('text', 'sender__username', 'thread__user__username')

    def short_text(self, obj):
        return obj.text[:40]
    short_text.short_description = "متن"


@admin.register(ShippingSettings)
class ShippingSettingsAdmin(admin.ModelAdmin):
    list_display = ("shipping_fee", "free_shipping_min_total", "updated_at")

    def has_add_permission(self, request):
        return not ShippingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent", "is_active", "is_public", "updated_at")
    list_editable = ("is_active", "is_public")
    search_fields = ("code",)
    list_filter = ("is_active", "is_public")


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ("card_number", "telegram_username", "whatsapp_number", "updated_at")

    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
