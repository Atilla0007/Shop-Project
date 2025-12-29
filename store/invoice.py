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
    divan_fanum_path = fonts_dir / "Divan-FaNum-Black.ttf"
    divan_path = fonts_dir / "Divan-Black.ttf"
    preferred_path = fonts_dir / "IRAN-Kharazmi.ttf"
    fallback_path = fonts_dir / "Vazirmatn-Regular.ttf"

    if divan_fanum_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("DivanFaNum", str(divan_fanum_path)))
        except Exception:
            pass
        return "DivanFaNum"

    if divan_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("Divan", str(divan_path)))
        except Exception:
            pass
        return "Divan"

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
    website = (getattr(settings, "COMPANY_WEBSITE", "") or "").strip()

    try:
        from core.models import PaymentSettings

        payment_settings = PaymentSettings.get_solo()
        address = (payment_settings.company_address or address or "").strip()
        phone = (payment_settings.company_phone or phone or "").strip()
        email = (payment_settings.company_email or email or "").strip()
        website = (payment_settings.company_website or website or "").strip()
    except Exception:
        pass

    lines: list[str] = []
    if address:
        lines.extend([ln.strip() for ln in address.splitlines() if ln.strip()])
    if phone or email or website:
        contact = " | ".join([p for p in [phone, email, website] if p])
        lines.append(contact)

    if not lines:
        lines.append("اطلاعات فروشنده از تنظیمات سایت قابل تغییر است.")

    return [company_name, *lines]


def render_order_invoice_pdf(*, order, title: str = "فاکتور", include_validity: bool = True) -> bytes:
    """Generate a PDF invoice/proforma for an order and return bytes.

    Layout is based on the provided HTML invoice template (title box, centered logo,
    header with seller/buyer details + summary table, items table, totals box).
    """
    font_name = _register_invoice_font()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 12
    margin_y = 12
    content_w = width - (2 * margin_x)
    y = height - margin_y

    c.setTitle(f"invoice-{getattr(order, 'id', '')}")

    include_signatures = False
    buyer_signature = ""
    seller_signature = ""
    notes_text = (getattr(order, "note", "") or "").strip()

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
    y -= 22
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
    issue_date = format_jalali(issue_dt, "Y/m/d") if issue_dt else ""
    due_date = format_jalali(issue_dt + timedelta(days=1), "Y/m/d") if issue_dt else ""

    # Keep the top summary focused on dates; totals appear in the footer box.
    summary_rows: list[tuple[str, str]] = [("تاریخ صدور", issue_date)]
    if include_validity:
        summary_rows.append(("مدت اعتبار", due_date))

    row_h = 26
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
        row_mid_y = row_top - 17
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
    cursor_y -= 20
    c.setFont(font_name, 10)
    for line in seller_rest:
        for wrapped in _wrap_rtl_lines(line, font_name=font_name, font_size=10, max_width=details_w):
            c.drawRightString(details_right, cursor_y, _rtl(wrapped))
            cursor_y -= 18
    cursor_y -= 12

    recipient_is_other = bool(getattr(order, "recipient_is_other", False))
    buyer_heading = "تحویل‌گیرنده" if recipient_is_other else "خریدار / تحویل‌گیرنده"
    c.setFont(font_name, 13)
    c.drawRightString(details_right, cursor_y, _rtl(buyer_heading))
    cursor_y -= 20
    c.setFont(font_name, 10)

    full_name = f"{getattr(order, 'first_name', '')} {getattr(order, 'last_name', '')}".strip() or "-"
    buyer_email = (getattr(order, "email", "") or "").strip()
    if not buyer_email and getattr(order, "user", None):
        buyer_email = (getattr(order.user, "email", "") or "").strip()
    buyer_phone = (getattr(order, "phone", "") or "").strip() or "-"
    province = (getattr(order, "province", "") or "").strip()
    city = (getattr(order, "city", "") or "").strip()
    address = (getattr(order, "address", "") or "").strip()

    buyer_lines = []
    if recipient_is_other and getattr(order, "user", None):
        purchaser_name = (getattr(order.user, "get_full_name", lambda: "")() or "").strip()
        if not purchaser_name:
            purchaser_name = (getattr(order.user, "username", "") or "").strip()
        if purchaser_name:
            buyer_lines.append(f"سفارش‌دهنده: {purchaser_name}")

    name_label = "تحویل‌گیرنده" if recipient_is_other else "نام"
    buyer_lines.extend(
        [
            f"{name_label}: {full_name}",
            f"موبایل: {buyer_phone}",
        ]
    )
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
            cursor_y -= 18
    cursor_y -= 6

    cursor_y -= 6
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
            header_h = 28
            c.setStrokeColor(BORDER_COLOR)
            c.setFillColor(colors.HexColor("#F4F4F9"))
            c.rect(margin_x, at_y - header_h, content_w, header_h, stroke=1, fill=1)
            c.setFillColor(TEXT_COLOR)
            # vertical lines
            c.line(margin_x + col_price, at_y, margin_x + col_price, at_y - header_h)
            c.line(margin_x + col_price + col_qty, at_y, margin_x + col_price + col_qty, at_y - header_h)
            c.setFont(font_name, 11)
            c.drawRightString(margin_x + content_w - 6, at_y - 19, _rtl("کالا"))
            c.drawRightString(margin_x + col_price + col_qty - 6, at_y - 19, _rtl("تعداد"))
            c.drawRightString(margin_x + col_price - 6, at_y - 19, _rtl("مبلغ"))
            return at_y - header_h

        y = draw_items_header(y)
        row_h_item = 30
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

            baseline_y = y - 19
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

    tot_row_h = 26
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
        row_mid_y = row_top - 17
        c.drawRightString(x_totals + totals_w - 6, row_mid_y, _rtl(label))
        c.drawRightString(x_totals + (totals_w - split2) - 6, row_mid_y, _rtl(value))

    y = y - tot_h - 18

    notes_h = 110
    if y - notes_h < margin_y:
        c.showPage()
        y = height - margin_y

    c.setStrokeColor(BORDER_COLOR)
    c.rect(margin_x, y - notes_h, content_w, notes_h, stroke=1, fill=0)
    c.setFont(font_name, 10)
    c.setFillColor(TEXT_COLOR)
    c.drawRightString(margin_x + content_w - 6, y - 16, _rtl("توضیحات"))
    if notes_text:
        note_y = y - 38
        max_notes_w = content_w - 14
        for line in _wrap_rtl_lines(notes_text, font_name=font_name, font_size=10, max_width=max_notes_w)[:4]:
            c.drawRightString(margin_x + content_w - 6, note_y, _rtl(line))
            note_y -= 18

    y = y - notes_h - 20

    if include_signatures:
        sig_gap = 18
        sig_h = 70
        sig_w = (content_w - sig_gap) / 2
        buyer_box_x = margin_x + content_w - sig_w
        seller_box_x = margin_x

        if y - sig_h < margin_y:
            c.showPage()
            y = height - margin_y

        c.setStrokeColor(BORDER_COLOR)
        c.rect(buyer_box_x, y - sig_h, sig_w, sig_h, stroke=1, fill=0)
        c.rect(seller_box_x, y - sig_h, sig_w, sig_h, stroke=1, fill=0)

        c.setFont(font_name, 10)
        c.setFillColor(TEXT_COLOR)
        c.drawRightString(buyer_box_x + sig_w - 6, y - 16, _rtl("نام و امضای خریدار"))
        c.drawRightString(seller_box_x + sig_w - 6, y - 16, _rtl("نام و امضای فروشنده"))

        if buyer_signature:
            c.drawRightString(buyer_box_x + sig_w - 6, y - 36, _rtl(buyer_signature))
        if seller_signature:
            c.drawRightString(seller_box_x + sig_w - 6, y - 36, _rtl(seller_signature))

    c.save()
    return buffer.getvalue()


def render_manual_invoice_pdf(
    *,
    invoice_number: str,
    title: str = "پیش‌فاکتور",
    issue_date: str = "",
    due_date: str = "",
    buyer_lines: list[str] | None = None,
    items: list[dict] | None = None,
    items_subtotal: int = 0,
    discount: int = 0,
    shipping: int = 0,
    grand_total: int = 0,
    include_signatures: bool = False,
    buyer_signature: str = "",
    seller_signature: str = "",
    notes: str = "",
) -> bytes:
    """Generate a PDF for the manual invoice builder (staff-only UI)."""
    buyer_lines = [ln for ln in (buyer_lines or []) if (ln or "").strip()]
    items = items or []

    if not include_signatures:
        title_compact = (title or "").replace(" ", "").replace("‌", "")
        if "فاکتور" in title_compact and "پیش" not in title_compact:
            include_signatures = True

    font_name = _register_invoice_font()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 12
    margin_y = 12
    content_w = width - (2 * margin_x)
    y = height - margin_y

    safe_number = (invoice_number or "").strip() or "#000000"
    invoice_title = f"{title} {safe_number}".strip()

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

    # Header (seller/buyer + dates only)
    gap = 18
    summary_w = content_w * 0.38
    details_w = content_w - summary_w - gap
    x_summary = margin_x
    x_details = margin_x + summary_w + gap
    details_right = x_details + details_w

    summary_rows: list[tuple[str, str]] = []
    if (issue_date or "").strip():
        summary_rows.append(("تاریخ صدور", (issue_date or "").strip()))
    if (due_date or "").strip():
        summary_rows.append(("مدت اعتبار", (due_date or "").strip()))
    if not summary_rows:
        summary_rows.append(("تاریخ صدور", ""))

    row_h = 26
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
        row_mid_y = row_top - 17
        c.drawRightString(x_summary + summary_w - 6, row_mid_y, _rtl(label))
        c.drawRightString(x_summary + (summary_w - split) - 6, row_mid_y, _rtl(value))

    # Details column: seller + buyer
    cursor_y = y
    seller_lines = _company_invoice_lines()
    seller_name = seller_lines[0]
    seller_rest = seller_lines[1:]

    c.setFont(font_name, 13)
    c.drawRightString(details_right, cursor_y - 2, _rtl(seller_name))
    cursor_y -= 20
    c.setFont(font_name, 10)
    for line in seller_rest:
        for wrapped in _wrap_rtl_lines(line, font_name=font_name, font_size=10, max_width=details_w):
            c.drawRightString(details_right, cursor_y, _rtl(wrapped))
            cursor_y -= 18
    cursor_y -= 12

    c.setFont(font_name, 13)
    c.drawRightString(details_right, cursor_y, _rtl("خریدار / تحویل‌گیرنده"))
    cursor_y -= 20
    c.setFont(font_name, 10)

    if buyer_lines:
        for line in buyer_lines:
            for wrapped in _wrap_rtl_lines(line, font_name=font_name, font_size=10, max_width=details_w)[:3]:
                c.drawRightString(details_right, cursor_y, _rtl(wrapped))
                cursor_y -= 18

    header_bottom = min(y - table_h, cursor_y)
    y = header_bottom - 24

    # Items table
    items = [it for it in items if isinstance(it, dict)]
    if not items:
        c.setFont(font_name, 11)
        c.drawRightString(margin_x + content_w, y, _rtl("هیچ ردیفی برای نمایش ثبت نشده است."))
        y -= 18
    else:
        col_price = content_w * 0.22
        col_qty = content_w * 0.14
        col_product = content_w - col_price - col_qty
        product_right = margin_x + content_w - 6

        def draw_items_header(at_y: float) -> float:
            header_h = 28
            c.setStrokeColor(BORDER_COLOR)
            c.setFillColor(colors.HexColor("#F4F4F9"))
            c.rect(margin_x, at_y - header_h, content_w, header_h, stroke=1, fill=1)
            c.setFillColor(TEXT_COLOR)
            c.line(margin_x + col_price, at_y, margin_x + col_price, at_y - header_h)
            c.line(margin_x + col_price + col_qty, at_y, margin_x + col_price + col_qty, at_y - header_h)
            c.setFont(font_name, 11)
            c.drawRightString(product_right, at_y - 19, _rtl("کالا"))
            c.drawRightString(margin_x + col_price + col_qty - 6, at_y - 19, _rtl("تعداد"))
            c.drawRightString(margin_x + col_price - 6, at_y - 19, _rtl("قیمت واحد"))
            return at_y - header_h

        y = draw_items_header(y)

        for it in items:
            name = (it.get("name") or "").strip()
            desc = (it.get("desc") or "").strip()
            try:
                qty = int(it.get("qty") or 0)
            except Exception:
                qty = 0
            try:
                price = int(it.get("price") or 0)
            except Exception:
                price = 0

            if not name and not desc and qty <= 0 and price <= 0:
                continue
            qty = max(1, qty)
            price = max(0, price)

            max_text_w = col_product - 14
            name_lines = _wrap_rtl_lines(name or "-", font_name=font_name, font_size=10, max_width=max_text_w)
            desc_lines = _wrap_rtl_lines(desc, font_name=font_name, font_size=9, max_width=max_text_w) if desc else []

            row_h_item = max(28, (18 * max(1, len(name_lines))) + (14 * len(desc_lines)) + 8)
            if y - row_h_item < margin_y + 120:
                c.showPage()
                y = height - margin_y
                y = draw_items_header(y)

            c.setStrokeColor(BORDER_COLOR)
            c.setFillColor(colors.white)
            c.rect(margin_x, y - row_h_item, content_w, row_h_item, stroke=1, fill=1)
            c.setFillColor(TEXT_COLOR)
            c.line(margin_x + col_price, y, margin_x + col_price, y - row_h_item)
            c.line(margin_x + col_price + col_qty, y, margin_x + col_price + col_qty, y - row_h_item)

            line_y = y - 19
            c.setFont(font_name, 10)
            for line in name_lines[:3]:
                c.setFillColor(TEXT_COLOR)
                c.drawRightString(product_right, line_y, _rtl(line))
                line_y -= 18

            if desc_lines:
                c.setFont(font_name, 9)
                c.setFillColor(colors.HexColor("#475569"))
                for line in desc_lines[:4]:
                    c.drawRightString(product_right, line_y, _rtl(line))
                    line_y -= 16

            c.setFont(font_name, 10)
            c.setFillColor(TEXT_COLOR)
            qty_text = str(qty).translate(PERSIAN_DIGITS_TRANS)
            price_text = f"{format_money(price)} تومان"
            baseline_y = y - 19
            c.drawRightString(margin_x + col_price + col_qty - 6, baseline_y, _rtl(qty_text))
            c.drawRightString(margin_x + col_price - 6, baseline_y, _rtl(price_text))

            y -= row_h_item

    # Footer totals table (right aligned)
    y -= 22
    totals_w = min(280, content_w * 0.52)
    x_totals = margin_x + content_w - totals_w

    try:
        items_subtotal = int(items_subtotal)
    except Exception:
        items_subtotal = 0
    try:
        discount = int(discount)
    except Exception:
        discount = 0
    try:
        shipping = int(shipping)
    except Exception:
        shipping = 0
    try:
        grand_total = int(grand_total)
    except Exception:
        grand_total = max(0, items_subtotal - max(0, discount)) + max(0, shipping)

    totals_rows: list[tuple[str, str]] = [
        ("جمع کالاها", f"{format_money(items_subtotal)} تومان"),
    ]
    if discount:
        totals_rows.append(("تخفیف", f"-{format_money(abs(discount))} تومان"))
    if shipping:
        totals_rows.append(("هزینه ارسال", f"{format_money(shipping)} تومان"))
    totals_rows.append(("مبلغ نهایی", f"{format_money(grand_total)} تومان"))

    tot_row_h = 26
    tot_h = tot_row_h * len(totals_rows)
    c.setStrokeColor(BORDER_COLOR)
    c.rect(x_totals, y - tot_h, totals_w, tot_h, stroke=1, fill=0)
    split2 = totals_w * 0.56
    c.line(x_totals + (totals_w - split2), y, x_totals + (totals_w - split2), y - tot_h)
    for i in range(1, len(totals_rows)):
        c.line(x_totals, y - (tot_row_h * i), x_totals + totals_w, y - (tot_row_h * i))

    c.setFont(font_name, 10)
    c.setFillColor(TEXT_COLOR)
    for idx, (label, value) in enumerate(totals_rows):
        row_top = y - (tot_row_h * idx)
        row_mid_y = row_top - 17
        c.drawRightString(x_totals + totals_w - 6, row_mid_y, _rtl(label))
        c.drawRightString(x_totals + (totals_w - split2) - 6, row_mid_y, _rtl(value))

    y = y - tot_h - 24

    if include_signatures:
        notes_text = (notes or "").strip()
        notes_h = 110
        sig_gap = 18
        sig_h = 70
        sig_w = (content_w - sig_gap) / 2
        buyer_box_x = margin_x + content_w - sig_w
        seller_box_x = margin_x

        if y - (notes_h + sig_gap + sig_h) < margin_y:
            c.showPage()
            y = height - margin_y

        c.setStrokeColor(BORDER_COLOR)
        c.rect(margin_x, y - notes_h, content_w, notes_h, stroke=1, fill=0)
        c.setFont(font_name, 10)
        c.setFillColor(TEXT_COLOR)
        c.drawRightString(margin_x + content_w - 6, y - 16, _rtl("توضیحات"))

        if notes_text:
            note_y = y - 38
            max_notes_w = content_w - 14
            for line in _wrap_rtl_lines(notes_text, font_name=font_name, font_size=10, max_width=max_notes_w)[:4]:
                c.drawRightString(margin_x + content_w - 6, note_y, _rtl(line))
                note_y -= 18

        y = y - notes_h - sig_gap

        c.rect(buyer_box_x, y - sig_h, sig_w, sig_h, stroke=1, fill=0)
        c.rect(seller_box_x, y - sig_h, sig_w, sig_h, stroke=1, fill=0)

        c.drawRightString(buyer_box_x + sig_w - 6, y - 16, _rtl("نام و امضای خریدار"))
        c.drawRightString(seller_box_x + sig_w - 6, y - 16, _rtl("نام و امضای فروشنده"))

        if buyer_signature:
            c.drawRightString(buyer_box_x + sig_w - 6, y - 36, _rtl(buyer_signature))
        if seller_signature:
            c.drawRightString(seller_box_x + sig_w - 6, y - 36, _rtl(seller_signature))

    c.save()
    return buffer.getvalue()
