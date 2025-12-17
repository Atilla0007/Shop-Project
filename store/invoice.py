from __future__ import annotations

from datetime import timedelta
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
from core.utils.jalali import PERSIAN_DIGITS_TRANS, format_jalali


BORDER_COLOR = colors.HexColor("#C0C0C0")
TEXT_COLOR = colors.HexColor("#000000")


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


def _wrap_rtl_lines(text: str, *, font_name: str, font_size: int, max_width: float) -> list[str]:
    """Wrap a RTL string into multiple lines based on rendered width (simple word wrap)."""
    text = (text or "").strip()
    if not text:
        return []

    words = text.split()
    lines: list[str] = []
    current: str = ""

    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        shaped = _rtl(candidate)
        if pdfmetrics.stringWidth(shaped, font_name, font_size) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
        current = word

    if current:
        lines.append(current)
    return lines


def _company_invoice_lines() -> list[str]:
    company_name = getattr(settings, "SITE_NAME", "استیرا")
    address = (getattr(settings, "COMPANY_ADDRESS", "") or "").strip()
    phone = (getattr(settings, "COMPANY_PHONE", "") or "").strip()
    email = (getattr(settings, "COMPANY_EMAIL", "") or "").strip()
    if not email:
        email = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()

    lines: list[str] = []
    if address:
        lines.extend([ln.strip() for ln in address.splitlines() if ln.strip()])
    if phone or email:
        contact = " | ".join([p for p in [phone, email] if p])
        lines.append(contact)

    if not lines:
        lines.append("اطلاعات فروشنده از تنظیمات سایت قابل تغییر است.")

    return [company_name, *lines]


def render_order_invoice_pdf(*, order, title: str = "فاکتور") -> bytes:
    """Generate a PDF invoice/proforma for an order and return bytes.

    Layout is based on the provided HTML invoice template (title box, centered logo,
    header with seller/buyer details + summary table, items table, totals box).
    """
    font_name = _register_invoice_font()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 40
    margin_y = 40
    content_w = width - (2 * margin_x)
    y = height - margin_y

    c.setTitle(f"invoice-{getattr(order, 'id', '')}")

    raw_order_id = str(getattr(order, "id", "")).strip()
    order_id_text = raw_order_id.zfill(6).translate(PERSIAN_DIGITS_TRANS) if raw_order_id else ""
    invoice_title = f"{title} #{order_id_text}".strip()

    # Title box
    title_box_h = 34
    y -= title_box_h
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(1)
    c.rect(margin_x, y, content_w, title_box_h, stroke=1, fill=0)
    c.setFillColor(TEXT_COLOR)
    c.setFont(font_name, 16)
    c.drawCentredString(width / 2, y + 10, _rtl(invoice_title))

    # Logo (centered)
    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "logo-styra.png"
    y -= 18
    if logo_path.exists():
        try:
            logo_box = 90
            c.drawImage(
                str(logo_path),
                (width - logo_box) / 2,
                y - logo_box,
                width=logo_box,
                height=logo_box,
                preserveAspectRatio=True,
                mask="auto",
            )
            y -= logo_box
        except Exception:
            pass
    y -= 18

    # Header (seller/buyer + summary table)
    gap = 18
    summary_w = content_w * 0.38
    details_w = content_w - summary_w - gap
    x_summary = margin_x
    x_details = margin_x + summary_w + gap
    details_right = x_details + details_w

    issue_dt = getattr(order, "payment_submitted_at", None) or getattr(order, "created_at", None)
    issue_date = format_jalali(issue_dt, "Y/m/d - H:i") if issue_dt else ""
    due_date = format_jalali(issue_dt + timedelta(days=1), "Y/m/d - H:i") if issue_dt else ""

    summary_rows = [
        ("تاریخ صدور", issue_date),
        ("سررسید", due_date),
        ("جمع کالاها", f"{format_money(getattr(order, 'items_subtotal', 0))} تومان"),
        ("مبلغ نهایی", f"{format_money(getattr(order, 'total_price', 0))} تومان"),
    ]

    row_h = 22
    table_h = row_h * len(summary_rows)
    c.setStrokeColor(BORDER_COLOR)
    c.rect(x_summary, y - table_h, summary_w, table_h, stroke=1, fill=0)
    split = summary_w * 0.46
    c.line(x_summary + (summary_w - split), y, x_summary + (summary_w - split), y - table_h)
    for i in range(1, len(summary_rows)):
        c.line(x_summary, y - (row_h * i), x_summary + summary_w, y - (row_h * i))

    c.setFont(font_name, 10)
    c.setFillColor(TEXT_COLOR)
    for idx, (label, value) in enumerate(summary_rows):
        row_top = y - (row_h * idx)
        row_mid_y = row_top - 15
        # label cell (right side)
        c.drawRightString(x_summary + summary_w - 6, row_mid_y, _rtl(label))
        # value cell (left side)
        c.drawRightString(x_summary + (summary_w - split) - 6, row_mid_y, _rtl(value))

    # Details column: seller + buyer
    cursor_y = y
    seller_lines = _company_invoice_lines()
    seller_name = seller_lines[0]
    seller_rest = seller_lines[1:]

    c.setFont(font_name, 13)
    c.drawRightString(details_right, cursor_y - 2, _rtl(seller_name))
    cursor_y -= 18
    c.setFont(font_name, 10)
    for line in seller_rest:
        for wrapped in _wrap_rtl_lines(line, font_name=font_name, font_size=10, max_width=details_w):
            c.drawRightString(details_right, cursor_y, _rtl(wrapped))
            cursor_y -= 14
    cursor_y -= 8

    c.setFont(font_name, 13)
    c.drawRightString(details_right, cursor_y, _rtl("مشخصات خریدار"))
    cursor_y -= 18
    c.setFont(font_name, 10)

    full_name = f"{getattr(order, 'first_name', '')} {getattr(order, 'last_name', '')}".strip() or "-"
    buyer_email = (getattr(order, "email", "") or "").strip()
    if not buyer_email and getattr(order, "user", None):
        buyer_email = (getattr(order.user, "email", "") or "").strip()
    buyer_phone = (getattr(order, "phone", "") or "").strip() or "-"
    province = (getattr(order, "province", "") or "").strip()
    city = (getattr(order, "city", "") or "").strip()
    address = (getattr(order, "address", "") or "").strip()

    buyer_lines = [
        f"نام: {full_name}",
        f"موبایل: {buyer_phone}",
    ]
    if buyer_email:
        buyer_lines.append(f"ایمیل: {buyer_email}")
    if province or city:
        buyer_lines.append(f"استان / شهر: {province} - {city}".strip(" -"))
    if address:
        buyer_lines.append(f"آدرس: {address}")

    for line in buyer_lines:
        wrapped_lines = _wrap_rtl_lines(line, font_name=font_name, font_size=10, max_width=details_w)
        if not wrapped_lines:
            continue
        for wrapped in wrapped_lines[:3]:
            c.drawRightString(details_right, cursor_y, _rtl(wrapped))
            cursor_y -= 14

    header_bottom = min(y - table_h, cursor_y)
    y = header_bottom - 24

    # Items table
    items = list(getattr(order, "items", []).all())
    if not items:
        c.setFont(font_name, 11)
        c.drawRightString(margin_x + content_w, y, _rtl("هیچ آیتمی برای نمایش وجود ندارد."))
        y -= 18
    else:
        col_price = content_w * 0.22
        col_qty = content_w * 0.14
        col_product = content_w - col_price - col_qty

        def draw_items_header(at_y: float) -> float:
            header_h = 26
            c.setStrokeColor(BORDER_COLOR)
            c.setFillColor(colors.HexColor("#F4F4F9"))
            c.rect(margin_x, at_y - header_h, content_w, header_h, stroke=1, fill=1)
            c.setFillColor(TEXT_COLOR)
            # vertical lines
            c.line(margin_x + col_price, at_y, margin_x + col_price, at_y - header_h)
            c.line(margin_x + col_price + col_qty, at_y, margin_x + col_price + col_qty, at_y - header_h)
            c.setFont(font_name, 11)
            c.drawRightString(margin_x + content_w - 6, at_y - 17, _rtl("کالا"))
            c.drawRightString(margin_x + col_price + col_qty - 6, at_y - 17, _rtl("تعداد"))
            c.drawRightString(margin_x + col_price - 6, at_y - 17, _rtl("مبلغ"))
            return at_y - header_h

        y = draw_items_header(y)
        row_h_item = 24
        c.setFont(font_name, 10)

        for it in items:
            if y - row_h_item < margin_y + 120:
                c.showPage()
                y = height - margin_y
                y = draw_items_header(y)
                c.setFont(font_name, 10)

            line_total = int(getattr(it, "unit_price", 0)) * int(getattr(it, "quantity", 0))
            price_text = f"{format_money(line_total)} تومان"
            qty_text = str(getattr(it, "quantity", "")).translate(PERSIAN_DIGITS_TRANS)
            name = (getattr(getattr(it, "product", None), "name", "") or "").strip()
            if len(name) > 80:
                name = name[:77] + "…"

            c.setStrokeColor(BORDER_COLOR)
            c.setFillColor(colors.white)
            c.rect(margin_x, y - row_h_item, content_w, row_h_item, stroke=1, fill=1)
            c.setFillColor(TEXT_COLOR)
            c.line(margin_x + col_price, y, margin_x + col_price, y - row_h_item)
            c.line(margin_x + col_price + col_qty, y, margin_x + col_price + col_qty, y - row_h_item)

            baseline_y = y - 16
            c.drawRightString(margin_x + content_w - 6, baseline_y, _rtl(name))
            c.drawRightString(margin_x + col_price + col_qty - 6, baseline_y, _rtl(qty_text))
            c.drawRightString(margin_x + col_price - 6, baseline_y, _rtl(price_text))

            y -= row_h_item

    # Footer totals table (right aligned)
    y -= 18
    totals_w = min(260, content_w * 0.48)
    x_totals = margin_x + content_w - totals_w
    totals_rows: list[tuple[str, str]] = [
        ("جمع کالاها", f"{format_money(getattr(order, 'items_subtotal', 0))} تومان"),
    ]

    if getattr(order, "discount_amount", 0):
        percent = str(getattr(order, "discount_percent", 0)).translate(PERSIAN_DIGITS_TRANS)
        totals_rows.append((f"تخفیف ({percent}٪)", f"-{format_money(getattr(order, 'discount_amount', 0))} تومان"))

    if getattr(order, "shipping_item_count", 0) and getattr(order, "shipping_fee_per_item", 0):
        if getattr(order, "shipping_is_free", False):
            totals_rows.append(("هزینه ارسال", "رایگان"))
        else:
            totals_rows.append(("هزینه ارسال", f"{format_money(getattr(order, 'shipping_total', 0))} تومان"))

    totals_rows.append(("مبلغ قابل پرداخت", f"{format_money(getattr(order, 'total_price', 0))} تومان"))

    tot_row_h = 22
    tot_h = tot_row_h * len(totals_rows)
    c.setStrokeColor(BORDER_COLOR)
    c.rect(x_totals, y - tot_h, totals_w, tot_h, stroke=1, fill=0)
    split2 = totals_w * 0.56
    c.line(x_totals + (totals_w - split2), y, x_totals + (totals_w - split2), y - tot_h)
    for i in range(1, len(totals_rows)):
        c.line(x_totals, y - (tot_row_h * i), x_totals + totals_w, y - (tot_row_h * i))

    c.setFont(font_name, 10)
    for idx, (label, value) in enumerate(totals_rows):
        row_top = y - (tot_row_h * idx)
        row_mid_y = row_top - 15
        c.drawRightString(x_totals + totals_w - 6, row_mid_y, _rtl(label))
        c.drawRightString(x_totals + (totals_w - split2) - 6, row_mid_y, _rtl(value))

    c.save()
    return buffer.getvalue()
