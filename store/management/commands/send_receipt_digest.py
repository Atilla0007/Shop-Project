from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from core.utils.formatting import format_money
from core.utils.jalali import format_jalali
from store.models import Order


User = get_user_model()


@dataclass(frozen=True)
class _AdminRecipient:
    to: list[str]
    bcc: list[str]


def _admin_emails() -> list[str]:
    return list(
        User.objects.filter(is_staff=True, is_active=True, email__isnull=False)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _recipient_lists(emails: list[str]) -> _AdminRecipient:
    emails = [e.strip() for e in emails if (e or "").strip()]
    emails = list(dict.fromkeys(emails))  # keep order, drop duplicates
    if not emails:
        return _AdminRecipient(to=[], bcc=[])
    return _AdminRecipient(to=[emails[0]], bcc=emails[1:])


def _send_email_message(message: EmailMultiAlternatives) -> None:
    try:
        message.send(fail_silently=False)
        return
    except Exception:
        if not getattr(settings, "DEBUG", False):
            raise

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        file_path = base_dir / "tmp" / "emails"
        file_path.mkdir(parents=True, exist_ok=True)
        connection = get_connection(
            "django.core.mail.backends.filebased.EmailBackend",
            fail_silently=False,
            file_path=str(file_path),
        )
        message.connection = connection
        message.send(fail_silently=False)


def _safe_write(command: BaseCommand, message: str) -> None:
    encoding = getattr(command.stdout, "encoding", None) or "utf-8"
    safe_message = message.encode(encoding, errors="backslashreplace").decode(encoding, errors="ignore")
    command.stdout.write(safe_message)


class Command(BaseCommand):
    help = "ارسال خلاصه فیش‌های پرداخت کارت‌به‌کارت برای ادمین‌ها (Digest)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="تاریخ مورد نظر (YYYY-MM-DD). پیش‌فرض: امروز (Asia/Tehran).",
            default="",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="ارسال حتی اگر قبلاً برای سفارش‌ها digest ارسال شده باشد.",
        )

    def handle(self, *args, **options):
        date_str = (options.get("date") or "").strip()
        force = bool(options.get("force"))

        target_date = timezone.localdate()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise SystemExit("فرمت تاریخ نامعتبر است. نمونه: 2025-12-16")

        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(target_date, time.min), tz)
        end = start + timedelta(days=1)

        orders = (
            Order.objects.filter(
                payment_method="card_to_card",
                payment_status="submitted",
                receipt_file__isnull=False,
                payment_submitted_at__gte=start,
                payment_submitted_at__lt=end,
            )
            .select_related("user")
            .order_by("id")
        )
        if not force:
            orders = orders.filter(receipt_digest_sent_at__isnull=True)

        orders_list = list(orders)
        if not orders_list:
            _safe_write(self, self.style.SUCCESS("هیچ فیش جدیدی برای ارسال یافت نشد."))
            return

        emails = _admin_emails()
        recipients = _recipient_lists(emails)
        if not recipients.to:
            _safe_write(self, self.style.WARNING("هیچ ایمیل ادمینی (is_staff) برای ارسال یافت نشد."))
            return

        brand = getattr(settings, "SITE_NAME", "استیرا")
        day_jalali = format_jalali(start, "Y/m/d")
        subject = f"فیش‌های پرداختی کارت‌به‌کارت ({day_jalali}) - {brand}"

        base_url = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
        digest_items = []
        attachments = []
        for o in orders_list:
            admin_path = f"/admin/store/order/{o.id}/change/"
            admin_url = f"{base_url}{admin_path}" if base_url else admin_path
            submitted_at = format_jalali(o.payment_submitted_at or o.created_at, "Y/m/d - H:i")
            full_name = f"{o.first_name} {o.last_name}".strip() or (o.user.username if o.user else "میهمان")

            receipt_name = ""
            receipt_url = ""
            if o.receipt_file:
                receipt_name = Path(o.receipt_file.name).name
                try:
                    receipt_url = o.receipt_file.url
                except Exception:
                    receipt_url = ""

                try:
                    content = o.receipt_file.read()
                    attachments.append((f"receipt-order-{o.id}-{receipt_name}", content, None))
                except Exception:
                    # If attachment can't be read, still include the digest row.
                    pass

            digest_items.append(
                {
                    "id": o.id,
                    "full_name": full_name,
                    "phone": o.phone or "",
                    "email": (o.email or (o.user.email if o.user else "") or "").strip(),
                    "total": f"{format_money(o.total_price)} تومان",
                    "submitted_at": submitted_at,
                    "admin_url": admin_url,
                    "receipt_name": receipt_name,
                    "receipt_url": receipt_url,
                }
            )

        text_body_lines = [
            f"فیش‌های کارت‌به‌کارت ({day_jalali})",
            "",
        ]
        for it in digest_items:
            text_body_lines.append(
                f"سفارش #{it['id']} | {it['full_name']} | مبلغ: {it['total']} | {it['submitted_at']}"
            )
            if it["admin_url"]:
                text_body_lines.append(f"پنل ادمین: {it['admin_url']}")
            if it["receipt_url"]:
                text_body_lines.append(f"فیش: {it['receipt_url']}")
            text_body_lines.append("")
        text_body = "\n".join(text_body_lines).strip()

        html_body = render_to_string(
            "emails/receipt_digest.html",
            {
                "title": "فیش‌های پرداختی کارت‌به‌کارت",
                "preheader": f"{len(digest_items)} فیش جدید برای بررسی",
                "brand": brand,
                "subtitle": "برای تایید/رد پرداخت‌ها وارد پنل ادمین شوید.",
                "day": day_jalali,
                "items": digest_items,
                "footer": "این ایمیل به صورت خودکار ارسال شده است.",
            },
        )

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=recipients.to,
            bcc=recipients.bcc,
        )
        message.attach_alternative(html_body, "text/html")
        for (name, content, mime) in attachments:
            message.attach(name, content, mime or "application/octet-stream")

        _send_email_message(message)

        now = timezone.now()
        Order.objects.filter(pk__in=[o.id for o in orders_list]).update(receipt_digest_sent_at=now)
        _safe_write(self, self.style.SUCCESS(f"{len(orders_list)} فیش برای ادمین‌ها ارسال شد."))
