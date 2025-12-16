from __future__ import annotations

from io import BytesIO
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from core.utils.formatting import format_money
from core.utils.jalali import format_jalali


def _rtl(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text or ""))


def _register_invoice_font() -> str:
    fonts_dir = Path(settings.BASE_DIR) / "static" / "fonts"
    preferred_path = fonts_dir / "IRAN-Kharazmi.ttf"
    fallback_path = fonts_dir / "Vazirmatn-Regular.ttf"

    if preferred_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("IranKharazmi", str(preferred_path)))
        except Exception:
            pass
        return "IranKharazmi"

    if fallback_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("Vazirmatn", str(fallback_path)))
        except Exception:
            pass
        return "Vazirmatn"

    return "Helvetica"


def render_order_invoice_pdf(*, order, title: str = "فیش سفارش استیرا") -> bytes:
    """Generate a styled PDF invoice/receipt for an order and return bytes."""
    font_name = _register_invoice_font()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header bar
    header_h = 128
    c.setFillColor(colors.HexColor("#2F4550"))
    c.rect(0, height - header_h, width, header_h, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#F4F4F9"))

    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "logo-styra.png"
    if logo_path.exists():
        try:
            logo_box = 46
            c.drawImage(
                str(logo_path),
                40,
                height - header_h + (header_h - logo_box) / 2,
                width=logo_box,
                height=logo_box,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    c.setFont(font_name, 18)
    c.drawRightString(width - 40, height - 52, _rtl(title))

    c.setFont(font_name, 11)
    c.drawRightString(width - 40, height - 74, _rtl(f"شماره سفارش: {order.id}"))
    c.drawRightString(
        width - 40,
        height - 92,
        _rtl(f"تاریخ: {format_jalali(order.created_at, 'Y/m/d - H:i')}"),
    )

    # Body
    y = height - header_h - 28
    c.setFillColor(colors.HexColor("#000000"))

    c.setFont(font_name, 11)
    full_name = f"{order.first_name} {order.last_name}".strip()
    if full_name:
        c.drawRightString(width - 40, y, _rtl(f"نام: {full_name}"))
        y -= 18
    if order.phone:
        c.drawRightString(width - 40, y, _rtl(f"شماره موبایل: {order.phone}"))
        y -= 18
    if order.province or order.city:
        c.drawRightString(width - 40, y, _rtl(f"استان/شهر: {order.province} - {order.city}".strip(" -")))
        y -= 18
    if order.address:
        c.drawRightString(width - 40, y, _rtl(f"آدرس: {order.address}"))
        y -= 18

    y -= 6
    c.setStrokeColor(colors.HexColor("#586F7C"))
    c.setLineWidth(1)
    c.line(40, y, width - 40, y)
    y -= 18

    # Items header
    c.setFont(font_name, 12)
    c.drawRightString(width - 40, y, _rtl("اقلام سفارش"))
    y -= 18

    c.setFont(font_name, 10)
    for it in order.items.all():
        line_total = int(it.unit_price) * int(it.quantity)
        c.drawRightString(
            width - 40,
            y,
            _rtl(f"{it.product.name} | تعداد: {it.quantity} | مبلغ: {format_money(line_total)} تومان"),
        )
        y -= 16
        if y < 140:
            c.showPage()
            c.setFont(font_name, 10)
            y = height - 60

    y -= 6
    c.setStrokeColor(colors.HexColor("#586F7C"))
    c.line(40, y, width - 40, y)
    y -= 18

    # Totals
    c.setFont(font_name, 11)
    c.drawRightString(width - 40, y, _rtl(f"جمع کالاها: {format_money(order.items_subtotal)} تومان"))
    y -= 16
    if order.discount_amount:
        c.drawRightString(
            width - 40,
            y,
            _rtl(f"تخفیف ({order.discount_percent}٪): -{format_money(order.discount_amount)} تومان"),
        )
        y -= 16
        after_discount = int(order.items_subtotal) - int(order.discount_amount)
        c.drawRightString(width - 40, y, _rtl(f"جمع بعد از تخفیف: {format_money(after_discount)} تومان"))
        y -= 16

    if order.shipping_item_count and order.shipping_fee_per_item:
        if order.shipping_is_free and order.shipping_total_full:
            c.drawRightString(
                width - 40,
                y,
                _rtl(f"هزینه ارسال: {format_money(order.shipping_total_full)} تومان (رایگان شد)"),
            )
        else:
            c.drawRightString(width - 40, y, _rtl(f"هزینه ارسال: {format_money(order.shipping_total)} تومان"))
        y -= 16

    c.setFont(font_name, 13)
    c.drawRightString(width - 40, y, _rtl(f"مبلغ قابل پرداخت: {format_money(order.total_price)} تومان"))

    c.showPage()
    c.save()
    return buffer.getvalue()
