from __future__ import annotations

from django.conf import settings

from core.models import DiscountCode, PaymentSettings


def site_info(request):
    company_phone = (getattr(settings, "COMPANY_PHONE", "") or "").strip()
    company_email = (getattr(settings, "COMPANY_EMAIL", "") or "").strip()
    if not company_email:
        company_email = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    company_address = (getattr(settings, "COMPANY_ADDRESS", "") or "").strip()
    payment_settings = PaymentSettings.get_solo()
    whatsapp_number = (payment_settings.whatsapp_number or "").strip()
    telegram_username = (payment_settings.telegram_username or "").strip().lstrip("@")

    return {
        "site_name": getattr(settings, "SITE_NAME", "استیرا"),
        "company_phone": company_phone,
        "company_email": company_email,
        "company_address": company_address,
        "company_whatsapp": whatsapp_number,
        "company_telegram": telegram_username,
    }


def public_promo(request):
    try:
        match = getattr(request, "resolver_match", None)
        if not match or match.url_name != "home":
            return {"public_promo": None}
    except Exception:
        return {"public_promo": None}

    promo = (
        DiscountCode.objects.filter(is_public=True, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    return {"public_promo": promo}
