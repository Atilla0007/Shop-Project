from django.contrib import admin

from .models import EmailOTPDevice


@admin.register(EmailOTPDevice)
class EmailOTPDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "email",
        "confirmed",
        "valid_until",
        "last_sent_at",
        "send_count_in_window",
        "verify_fail_count",
    )
    list_filter = ("confirmed",)
    search_fields = ("email", "user__username", "user__email")

