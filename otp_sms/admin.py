from django.contrib import admin

from .models import SmsOTPDevice


@admin.register(SmsOTPDevice)
class SmsOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "name", "confirmed", "last_sent_at", "valid_until", "verify_fail_count")
    search_fields = ("user__username", "user__email", "phone")
    list_filter = ("confirmed",)

