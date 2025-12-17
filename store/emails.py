from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from core.utils.formatting import format_money
from core.utils.jalali import format_jalali
from store.invoice import render_order_invoice_pdf


def _get_order_to_email(order) -> str | None:
    to_email = (getattr(order, "email", "") or "").strip()
    if not to_email and getattr(order, "user", None):
        to_email = (getattr(order.user, "email", "") or "").strip()
    return to_email or None


def _build_order_items(order) -> list[dict]:
    items = []
    for it in order.items.all():
        total = int(it.unit_price) * int(it.quantity)
        items.append(
            {
                "name": it.product.name,
                "qty": int(it.quantity),
                "total": f"{format_money(total)} تومان",
            }
        )
    return items


def _send_email_message(message: EmailMultiAlternatives) -> None:
    try:
        message.send(fail_silently=False)
        return
    except Exception:
        if not getattr(settings, "DEBUG", False):
            return

        # Fallback to filebased backend in DEBUG to avoid stdout/SMTP issues.
        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        file_path = base_dir / "tmp" / "emails"
        file_path.mkdir(parents=True, exist_ok=True)
        connection = get_connection(
            "django.core.mail.backends.filebased.EmailBackend",
            fail_silently=True,
            file_path=str(file_path),
        )
        message.connection = connection
        message.send(fail_silently=True)


def send_order_payment_submitted_email(*, order, request=None) -> None:
    to_email = _get_order_to_email(order)
    if not to_email:
        return

    brand = getattr(settings, "SITE_NAME", "استیرا")
    subject = f"درخواست پرداخت شما ثبت شد (سفارش #{order.id})"

    cta_url = None
    try:
        from django.urls import reverse

        profile_path = reverse("profile")
        if request is not None:
            cta_url = request.build_absolute_uri(profile_path)
        else:
            base_url = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
            if base_url:
                cta_url = f"{base_url}{profile_path}"
    except Exception:
        cta_url = None

    created_at = format_jalali(order.created_at, "Y/m/d - H:i")

    shipping_total = f"{format_money(order.shipping_total)} تومان"
    if getattr(order, "shipping_is_free", False) and getattr(order, "shipping_total_full", 0):
        shipping_total = f"۰ تومان (رایگان)"

    context = {
        "title": "درخواست پرداخت ثبت شد",
        "preheader": f"سفارش #{order.id} در انتظار بررسی است.",
        "brand": brand,
        "subtitle": "وضعیت پرداخت: در انتظار بررسی",
        "order_id": order.id,
        "created_at": created_at,
        "items": _build_order_items(order),
        "items_subtotal": f"{format_money(order.items_subtotal)} تومان",
        "discount_amount": f"{format_money(order.discount_amount)} تومان" if order.discount_amount else "",
        "shipping_total": shipping_total,
        "total_price": f"{format_money(order.total_price)} تومان",
        "cta_url": cta_url,
        "footer": "در صورت تایید یا رد پرداخت، از طریق ایمیل و پیامک به شما اطلاع می‌دهیم.",
    }

    text_body = (
        f"درخواست پرداخت شما ثبت شد.\n"
        f"سفارش #{order.id}\n"
        f"تاریخ ثبت: {created_at}\n"
        f"مبلغ قابل پرداخت: {format_money(order.total_price)} تومان\n"
        f"فیش/فاکتور سفارش به صورت PDF پیوست شده است."
    )
    html_body = render_to_string("emails/order_submitted.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    pdf_bytes = render_order_invoice_pdf(order=order, title="فیش سفارش استیرا")
    message.attach(f"order-{order.id}.pdf", pdf_bytes, "application/pdf")

    _send_email_message(message)


def send_order_payment_approved_email(*, order, request=None) -> None:
    to_email = _get_order_to_email(order)
    if not to_email:
        return

    brand = getattr(settings, "SITE_NAME", "استیرا")
    subject = f"پرداخت تایید شد (سفارش #{order.id})"

    cta_url = None
    try:
        from django.urls import reverse

        profile_path = reverse("profile")
        if request is not None:
            cta_url = request.build_absolute_uri(profile_path)
        else:
            base_url = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
            if base_url:
                cta_url = f"{base_url}{profile_path}"
    except Exception:
        cta_url = None

    approved_at = (
        format_jalali(order.payment_reviewed_at, "Y/m/d - H:i")
        if getattr(order, "payment_reviewed_at", None)
        else format_jalali(order.created_at, "Y/m/d - H:i")
    )

    context = {
        "title": "پرداخت تایید شد",
        "preheader": f"سفارش #{order.id} تایید شد.",
        "brand": brand,
        "subtitle": "سفارش شما نهایی شد",
        "order_id": order.id,
        "approved_at": approved_at,
        "items": _build_order_items(order),
        "total_price": f"{format_money(order.total_price)} تومان",
        "cta_url": cta_url,
        "footer": "از خرید شما متشکریم. در صورت نیاز با پشتیبانی استیرا در تماس باشید.",
    }

    text_body = (
        f"پرداخت شما تایید شد و سفارش نهایی شد.\n"
        f"سفارش #{order.id}\n"
        f"تاریخ تایید: {approved_at}\n"
        f"مبلغ نهایی: {format_money(order.total_price)} تومان\n"
        f"فیش/فاکتور سفارش به صورت PDF پیوست شده است."
    )
    html_body = render_to_string("emails/order_approved.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    pdf_bytes = render_order_invoice_pdf(order=order, title="فاکتور نهایی استیرا")
    message.attach(f"order-{order.id}.pdf", pdf_bytes, "application/pdf")

    _send_email_message(message)
