from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from core.utils.formatting import format_money
from core.utils.jalali import format_jalali
from store.invoice import render_order_invoice_pdf


@dataclass(frozen=True)
class _DummyUser:
    email: str = ""


@dataclass(frozen=True)
class _DummyProduct:
    name: str


@dataclass(frozen=True)
class _DummyItem:
    product: _DummyProduct
    quantity: int
    unit_price: int


class _DummyItems:
    def __init__(self, items: list[_DummyItem]):
        self._items = items

    def all(self) -> list[_DummyItem]:
        return self._items


class _DummyOrder:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _send_email_message(message: EmailMultiAlternatives) -> None:
    message.send(fail_silently=False)


def _build_items_context(items: list[_DummyItem]) -> list[dict]:
    out = []
    for it in items:
        total = int(it.unit_price) * int(it.quantity)
        out.append(
            {
                "name": it.product.name,
                "qty": int(it.quantity),
                "total": f"{format_money(total)} تومان",
            }
        )
    return out


class Command(BaseCommand):
    help = "ارسال نمونه‌ی ایمیل‌های فاکتور/پیش‌فاکتور به یک ایمیل مشخص (برای تست SMTP و طراحی)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            required=True,
            help="ایمیل مقصد (می‌توانید چند ایمیل را با کاما جدا کنید).",
        )

    def handle(self, *args, **options):
        raw_to = (options.get("to") or "").strip()
        recipients = [x.strip() for x in raw_to.split(",") if x.strip()]
        if not recipients:
            self.stderr.write(self.style.ERROR("ایمیل مقصد نامعتبر است."))
            return

        brand = getattr(settings, "SITE_NAME", "استیرا")
        now = timezone.now()

        items = [
            _DummyItem(product=_DummyProduct(name="یخچال و فریزر صنعتی ایستاده"), quantity=1, unit_price=42_000_000),
            _DummyItem(product=_DummyProduct(name="فر پیتزا صندوقی دو طبقه"), quantity=2, unit_price=15_000_000),
        ]
        items_subtotal = sum(int(i.unit_price) * int(i.quantity) for i in items)
        discount_percent = 10
        discount_amount = int(items_subtotal * discount_percent / 100)
        shipping_fee_per_item = 250_000
        shipping_item_count = sum(int(i.quantity) for i in items)
        shipping_total = shipping_fee_per_item * shipping_item_count
        total_price = (items_subtotal - discount_amount) + shipping_total

        order = _DummyOrder(
            id=424773,
            created_at=now - timedelta(minutes=35),
            payment_submitted_at=now - timedelta(minutes=20),
            payment_reviewed_at=now - timedelta(minutes=5),
            first_name="آتیلا",
            last_name="حاتفی",
            phone="09120000000",
            email=recipients[0],
            province="تهران",
            city="تهران",
            address="تهران، خیابان نمونه، پلاک ۱۲، واحد ۳",
            items_subtotal=items_subtotal,
            discount_code="TEST10",
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            shipping_fee_per_item=shipping_fee_per_item,
            shipping_item_count=shipping_item_count,
            shipping_total_full=shipping_total,
            shipping_total=shipping_total,
            shipping_is_free=False,
            total_price=total_price,
            items=_DummyItems(items),
            user=_DummyUser(email=recipients[0]),
        )

        submitted_context = {
            "title": "نمونه ایمیل ثبت سفارش",
            "preheader": f"سفارش شماره {order.id} ثبت شد و برای بررسی پرداخت ارسال گردید.",
            "brand": brand,
            "subtitle": "این یک ایمیل نمونه برای بررسی طراحی و تست ارسال SMTP است.",
            "order_id": order.id,
            "created_at": format_jalali(order.created_at, "Y/m/d - H:i"),
            "items": _build_items_context(items),
            "items_subtotal": f"{format_money(order.items_subtotal)} تومان",
            "discount_amount": f"{format_money(order.discount_amount)} تومان" if order.discount_amount else "",
            "shipping_total": f"{format_money(order.shipping_total)} تومان",
            "total_price": f"{format_money(order.total_price)} تومان",
            "cta_url": None,
            "footer": "این ایمیل صرفاً نمونه است و به معنای ثبت سفارش واقعی نیست.",
        }

        submitted_html = render_to_string("emails/order_submitted.html", submitted_context)
        submitted_text = (
            f"نمونه ایمیل ثبت سفارش - {brand}\n"
            f"سفارش #{order.id}\n"
            f"مبلغ قابل پرداخت: {format_money(order.total_price)} تومان\n"
        )
        submitted_pdf = render_order_invoice_pdf(order=order, title="پیش‌فاکتور استیرا")

        msg = EmailMultiAlternatives(
            subject=f"نمونه پیش‌فاکتور - {brand}",
            body=submitted_text,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=recipients,
        )
        msg.attach_alternative(submitted_html, "text/html")
        msg.attach(f"proforma-sample-{order.id}.pdf", submitted_pdf, "application/pdf")
        _send_email_message(msg)

        approved_context = {
            "title": "نمونه ایمیل تایید نهایی",
            "preheader": f"پرداخت سفارش شماره {order.id} تایید شد.",
            "brand": brand,
            "subtitle": "این یک ایمیل نمونه برای بررسی طراحی و تست ارسال SMTP است.",
            "order_id": order.id,
            "approved_at": format_jalali(order.payment_reviewed_at, "Y/m/d - H:i"),
            "items": _build_items_context(items),
            "total_price": f"{format_money(order.total_price)} تومان",
            "cta_url": None,
            "footer": "این ایمیل صرفاً نمونه است و به معنای تایید پرداخت واقعی نیست.",
        }

        approved_html = render_to_string("emails/order_approved.html", approved_context)
        approved_text = (
            f"نمونه ایمیل تایید پرداخت - {brand}\n"
            f"سفارش #{order.id}\n"
            f"مبلغ نهایی: {format_money(order.total_price)} تومان\n"
        )
        approved_pdf = render_order_invoice_pdf(order=order, title="فاکتور نهایی استیرا", include_validity=False)

        msg2 = EmailMultiAlternatives(
            subject=f"نمونه فاکتور نهایی - {brand}",
            body=approved_text,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=recipients,
        )
        msg2.attach_alternative(approved_html, "text/html")
        msg2.attach(f"invoice-sample-{order.id}.pdf", approved_pdf, "application/pdf")
        _send_email_message(msg2)

        self.stdout.write(self.style.SUCCESS(f"نمونه‌ها ارسال شد: {', '.join(recipients)}"))
