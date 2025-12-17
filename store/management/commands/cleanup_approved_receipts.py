from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from store.models import Order


def _purge_delay_seconds() -> int:
    try:
        return int(getattr(settings, "RECEIPT_PURGE_DELAY_SECONDS", 2 * 60 * 60))
    except (TypeError, ValueError):
        return 2 * 60 * 60


def _safe_write(command: BaseCommand, message: str) -> None:
    encoding = getattr(command.stdout, "encoding", None) or "utf-8"
    safe_message = message.encode(encoding, errors="backslashreplace").decode(encoding, errors="ignore")
    command.stdout.write(safe_message)


class Command(BaseCommand):
    help = "حذف خودکار فایل فیش سفارش‌های تاییدشده (بعد از گذشت زمان مشخص)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seconds",
            type=int,
            default=None,
            help="تاخیر پاکسازی (ثانیه). پیش‌فرض از settings.RECEIPT_PURGE_DELAY_SECONDS (پیش‌فرض 7200).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="فقط نمایش تعداد، بدون پاک کردن واقعی فایل‌ها.",
        )

    def handle(self, *args, **options):
        delay_seconds = options.get("seconds")
        if delay_seconds is None:
            delay_seconds = _purge_delay_seconds()

        dry_run = bool(options.get("dry_run"))
        threshold = timezone.now() - timedelta(seconds=int(delay_seconds))

        qs = (
            Order.objects.filter(
                payment_status="approved",
                receipt_file__isnull=False,
                payment_reviewed_at__isnull=False,
                payment_reviewed_at__lte=threshold,
            )
            .only("id", "receipt_file", "payment_reviewed_at")
            .order_by("id")
        )

        orders = list(qs)
        if not orders:
            _safe_write(self, self.style.SUCCESS("هیچ فیش قابل پاکسازی یافت نشد."))
            return

        if dry_run:
            _safe_write(self, self.style.WARNING(f"DRY RUN: {len(orders)} فیش قابل پاکسازی است."))
            return

        purged = 0
        for o in orders:
            if not o.receipt_file:
                continue

            try:
                o.receipt_file.delete(save=False)
            except Exception:
                # Keep going even if storage delete fails; we still clear the DB field.
                pass

            o.receipt_file = None
            o.save(update_fields=["receipt_file"])
            purged += 1

        _safe_write(self, self.style.SUCCESS(f"{purged} فیش پاکسازی شد."))
