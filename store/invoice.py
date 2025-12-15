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


def render_order_invoice_pdf(*, order, title: str = "فیش سفارش استیرا") -> bytes:
    """Generate a styled PDF invoice/receipt for an order and return bytes."""
    font_path = Path(settings.BASE_DIR) / "static" / "fonts" / "Vazirmatn-Regular.ttf"
    try:
        pdfmetrics.registerFont(TTFont("Vazirmatn", str(font_path)))
    except Exception:
        # Font already registered or missing; fall back to default.
        pass

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header bar
    header_h = 92
    c.setFillColor(colors.HexColor("#2F4550"))
    c.rect(0, height - header_h, width, header_h, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#F4F4F9"))

    c.setFont("Vazirmatn", 18)
    c.drawRightString(width - 40, height - 52, _rtl(title))

    c.setFont("Vazirmatn", 11)
    c.drawRightString(width - 40, height - 74, _rtl(f"شماره سفارش: {order.id}"))
    c.drawRightString(
        width - 40,
        height - 92,
        _rtl(f"تاریخ: {format_jalali(order.created_at, 'Y/m/d - H:i')}"),
    )

    # Body
    y = height - header_h - 28
    c.setFillColor(colors.HexColor("#000000"))

    c.setFont("Vazirmatn", 11)
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
    c.setFont("Vazirmatn", 12)
    c.drawRightString(width - 40, y, _rtl("اقلام سفارش"))
    y -= 18

    c.setFont("Vazirmatn", 10)
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
            c.setFont("Vazirmatn", 10)
            y = height - 60

    y -= 6
    c.setStrokeColor(colors.HexColor("#586F7C"))
    c.line(40, y, width - 40, y)
    y -= 18

    # Totals
    c.setFont("Vazirmatn", 11)
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

    c.setFont("Vazirmatn", 13)
    c.drawRightString(width - 40, y, _rtl(f"مبلغ قابل پرداخت: {format_money(order.total_price)} تومان"))

    c.showPage()
    c.save()
    return buffer.getvalue()

