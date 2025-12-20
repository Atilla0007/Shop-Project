import logging
import secrets

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.template.response import TemplateResponse

from accounts.models import UserProfile
from accounts.sms import send_sms
from store.models import Order

from .models import ContactMessage, DiscountCode, DiscountRedemption, News, PaymentSettings, ShippingSettings

logger = logging.getLogger(__name__)


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
        "source_code",
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
    actions = ["generate_personal_codes"]

    class PersonalCodeForm(forms.Form):
        audience = forms.ChoiceField(
            choices=(
                ("all", "All users"),
                ("buyers", "Users with previous orders"),
            ),
            label="Audience",
        )
        sms_template = forms.CharField(
            required=False,
            widget=forms.Textarea(attrs={"rows": 3}),
            label="SMS template",
            help_text="Placeholders: {code} and {percent}",
        )

    def _generate_unique_code(self, base_code: str) -> str:
        base = (base_code or "").strip().upper().replace(" ", "")
        max_len = 50
        for _ in range(10):
            suffix = secrets.token_hex(3).upper()
            prefix = base[: max_len - 1 - len(suffix)] if base else "OFF"
            candidate = f"{prefix}-{suffix}"
            if not DiscountCode.objects.filter(code=candidate).exists():
                return candidate
        raise RuntimeError("Failed to generate unique discount code")

    def generate_personal_codes(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one base discount code.", level=messages.ERROR)
            return

        discount = queryset.first()
        form = None
        if "apply" in request.POST:
            form = self.PersonalCodeForm(request.POST)
            if form.is_valid():
                audience = form.cleaned_data["audience"]
                sms_template = form.cleaned_data["sms_template"].strip() if form.cleaned_data["sms_template"] else ""
                if not sms_template:
                    sms_template = (
                        "استیرا | کد تخفیف اختصاصی شما: {code} ({percent}٪ تخفیف). "
                        "برای خرید بعدی استفاده کنید: styra.ir"
                    )

                User = get_user_model()
                if audience == "buyers":
                    buyer_ids = (
                        Order.objects.filter(user__isnull=False)
                        .values_list("user_id", flat=True)
                        .distinct()
                    )
                    users_qs = User.objects.filter(id__in=buyer_ids, is_active=True)
                else:
                    users_qs = User.objects.filter(is_active=True)

                profiles = (
                    UserProfile.objects.select_related("user")
                    .filter(user__in=users_qs)
                    .exclude(phone__isnull=True)
                    .exclude(phone="")
                )

                created = 0
                skipped_existing = 0
                skipped_no_phone = users_qs.count() - profiles.count()
                sms_sent = 0
                sms_failed = 0

                for profile in profiles:
                    user = profile.user
                    existing = DiscountCode.objects.filter(
                        source_code=discount.code,
                        assigned_user=user,
                    ).exists()
                    if existing:
                        skipped_existing += 1
                        continue

                    code = self._generate_unique_code(discount.code)
                    personal = DiscountCode.objects.create(
                        code=code,
                        source_code=discount.code,
                        percent=discount.percent,
                        assigned_user=user,
                        is_active=discount.is_active,
                        is_public=False,
                        public_message="",
                        max_uses=discount.max_uses,
                        max_uses_per_user=discount.max_uses_per_user,
                        uses_count=0,
                    )
                    created += 1

                    try:
                        message = sms_template.format(code=personal.code, percent=personal.percent)
                    except Exception:
                        message = (
                            f"استیرا | کد تخفیف اختصاصی شما: {personal.code} ({personal.percent}٪ تخفیف). "
                            "برای خرید بعدی استفاده کنید: styra.ir"
                        )

                    try:
                        send_sms(profile.phone, message)
                        sms_sent += 1
                    except Exception:
                        sms_failed += 1
                        logger.exception("Failed to send discount SMS to %s", profile.phone)

                self.message_user(
                    request,
                    (
                        f"Created {created} personal codes. "
                        f"SMS sent: {sms_sent}, failed: {sms_failed}. "
                        f"Skipped (existing): {skipped_existing}. "
                        f"Skipped (no phone): {skipped_no_phone}."
                    ),
                    level=messages.SUCCESS,
                )
                return
        if form is None:
            form = self.PersonalCodeForm(
                initial={
                    "sms_template": (
                        "استیرا | کد تخفیف اختصاصی شما: {code} ({percent}٪ تخفیف). "
                        "برای خرید بعدی استفاده کنید: styra.ir"
                    )
                }
            )

        return TemplateResponse(
            request,
            "admin/discountcode_generate_personal.html",
            {
                "discount": discount,
                "form": form,
                "title": "Generate personal discount codes",
                "action_name": "generate_personal_codes",
                "queryset": queryset,
            },
        )

    generate_personal_codes.short_description = "Generate personal codes and send SMS"


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
