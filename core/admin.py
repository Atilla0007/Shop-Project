from datetime import timedelta
import logging
import secrets

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Avg, Sum
from django.db.models.functions import Coalesce
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from accounts.models import UserProfile
from accounts.sms import send_sms
from store.models import Order

from .models import ContactMessage, DiscountCode, DiscountRedemption, News, PaymentSettings, ShippingSettings, SiteVisit

logger = logging.getLogger(__name__)


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "phone", "status", "created_at", "replied_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "phone")
    actions = ["send_reply"]

    class ReplyForm(forms.Form):
        subject = forms.CharField(required=False, label="Email subject")
        message = forms.CharField(
            required=False,
            widget=forms.Textarea(attrs={"rows": 6}),
            label="Reply message",
        )
        send_email = forms.BooleanField(required=False, initial=True, label="Send email")
        send_sms = forms.BooleanField(required=False, label="Send SMS")

    def _default_reply_message(self) -> str:
        return (
            "پیام شما دریافت شد و توسط تیم استیرا بررسی می‌شود. "
            "در صورت نیاز به اطلاعات تکمیلی با شما تماس می‌گیریم. "
            "از همراهی شما سپاسگزاریم."
        )

    def send_reply(self, request, queryset):
        form = None
        if "apply" in request.POST:
            form = self.ReplyForm(request.POST)
            if form.is_valid():
                subject = (form.cleaned_data.get("subject") or "").strip()
                if not subject:
                    subject = "پاسخ استیرا به پیام شما"
                message_text = (form.cleaned_data.get("message") or "").strip()
                if not message_text:
                    message_text = self._default_reply_message()

                send_email_flag = bool(form.cleaned_data.get("send_email"))
                send_sms_flag = bool(form.cleaned_data.get("send_sms"))

                email_sent = 0
                sms_sent = 0
                email_failed = 0
                sms_failed = 0
                skipped_email = 0
                skipped_sms = 0

                brand = getattr(settings, "SITE_NAME", "Styra")
                now = timezone.now()

                for msg in queryset:
                    if send_email_flag:
                        if msg.email:
                            html_body = render_to_string(
                                "emails/contact_reply.html",
                                {
                                    "title": subject,
                                    "preheader": message_text,
                                    "brand": brand,
                                    "message_text": message_text,
                                    "recipient": msg.name,
                                },
                            )
                            try:
                                email_message = EmailMultiAlternatives(
                                    subject=subject,
                                    body=message_text,
                                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                                    to=[msg.email],
                                )
                                email_message.attach_alternative(html_body, "text/html")
                                email_message.send(fail_silently=False)
                                email_sent += 1
                            except Exception:
                                email_failed += 1
                                logger.exception("Failed to send contact reply email to %s", msg.email)
                        else:
                            skipped_email += 1

                    if send_sms_flag:
                        if msg.phone:
                            try:
                                send_sms(msg.phone, message_text)
                                sms_sent += 1
                            except Exception:
                                sms_failed += 1
                                logger.exception("Failed to send contact reply SMS to %s", msg.phone)
                        else:
                            skipped_sms += 1

                queryset.update(status="replied", replied_at=now)
                self.message_user(
                    request,
                    (
                        f"Reply sent. Email sent: {email_sent}, failed: {email_failed}, skipped: {skipped_email}. "
                        f"SMS sent: {sms_sent}, failed: {sms_failed}, skipped: {skipped_sms}."
                    ),
                    level=messages.SUCCESS,
                )
                return

        if form is None:
            form = self.ReplyForm(
                initial={
                    "subject": "پاسخ استیرا به پیام شما",
                    "message": self._default_reply_message(),
                    "send_email": True,
                }
            )

        return TemplateResponse(
            request,
            "admin/contactmessage_reply.html",
            {
                "form": form,
                "title": "Reply to contact messages",
                "action_name": "send_reply",
                "queryset": queryset,
            },
        )

    send_reply.short_description = "Reply to selected messages"


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


def _format_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def _build_admin_analytics(period_days: int = 30) -> dict:
    now = timezone.now()
    period_start = now - timedelta(days=period_days)

    paid_orders = Order.objects.filter(status__in=["paid", "sent", "done"], payment_status="approved")
    paid_period = paid_orders.filter(created_at__gte=period_start)

    sales_period = paid_period.aggregate(total=Coalesce(Sum("total_price"), 0))["total"] or 0
    sales_total = paid_orders.aggregate(total=Coalesce(Sum("total_price"), 0))["total"] or 0
    avg_basket = paid_period.aggregate(avg=Coalesce(Avg("total_price"), 0))["avg"] or 0
    orders_period = paid_period.count()

    visits_period = (
        SiteVisit.objects.filter(visited_on__gte=period_start.date())
        .values("session_key")
        .distinct()
        .count()
    )

    conversion_rate = (orders_period / visits_period * 100) if visits_period else 0.0

    return {
        "period_days": period_days,
        "sales_period": _format_int(sales_period),
        "sales_total": _format_int(sales_total),
        "avg_basket": _format_int(avg_basket),
        "orders_period": _format_int(orders_period),
        "visits_period": _format_int(visits_period),
        "conversion_rate": f"{conversion_rate:.1f}%",
        "generated_at": now,
    }


def analytics_view(request):
    context = {
        **admin.site.each_context(request),
        "title": "Analytics dashboard",
        "analytics": _build_admin_analytics(),
    }
    return TemplateResponse(request, "admin/analytics_dashboard.html", context)


def _wrap_admin_index(original_index):
    def _index(request, extra_context=None):
        extra = extra_context or {}
        extra["analytics"] = _build_admin_analytics()
        return original_index(request, extra_context=extra)

    return _index


def _wrap_admin_urls(original_get_urls):
    def get_urls():
        urls = original_get_urls()
        custom_urls = [
            path("analytics/", admin.site.admin_view(analytics_view), name="analytics-dashboard"),
        ]
        return custom_urls + urls

    return get_urls


admin.site.index = _wrap_admin_index(admin.site.index)
admin.site.index_template = "admin/index.html"
admin.site.get_urls = _wrap_admin_urls(admin.site.get_urls)
