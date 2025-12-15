from __future__ import annotations

from core.models import DiscountCode


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
