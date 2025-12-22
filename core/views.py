from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives, get_connection
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from store.models import Category, Product

from .forms import ContactForm
from .models import News
from core.utils.jalali import format_jalali

logger = logging.getLogger(__name__)


def home(request):
    """Render home page with highlighted products and news."""
    products = Product.objects.filter(is_available=True)[:8]
    news = News.objects.all()[:3]
    categories = Category.objects.all()
    cart_product_ids: set[int] = set()
    try:
        from store.models import CartItem
        from store.views import _get_session_cart, _merge_session_cart_into_user

        if request.user.is_authenticated:
            _merge_session_cart_into_user(request)
            cart_product_ids = set(
                CartItem.objects.filter(user=request.user).values_list("product_id", flat=True)
            )
        else:
            session_cart = _get_session_cart(request)
            cart_product_ids = {int(k) for k in session_cart.keys() if str(k).isdigit()}
    except Exception:
        cart_product_ids = set()

    context = {
        "products": products,
        "news": news,
        "categories": categories,
        "cart_product_ids": cart_product_ids,
    }
    return render(request, "home.html", context)


def contact(request):
    """Handle contact form submission and render the contact page."""

    def _admin_emails():
        return list(
            User.objects.filter(is_superuser=True, email__isnull=False)
            .exclude(email="")
            .values_list("email", flat=True)
        )

    def _send_email_message(message: EmailMultiAlternatives) -> None:
        try:
            message.send(fail_silently=False)
            return
        except Exception:
            if not getattr(settings, "DEBUG", False):
                logger.exception("Failed to send contact email")
                return

        # Fallback to filebased backend in DEBUG to avoid SMTP/console issues.
        try:
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
        except Exception:
            logger.exception("Failed to send contact email (filebased fallback)")

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            message = form.save()

            support_email = (getattr(settings, "COMPANY_EMAIL", "") or "").strip()
            if not support_email:
                support_email = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()

            admin_emails = _admin_emails()
            bcc_emails = sorted({email for email in admin_emails if email and email != support_email})

            if support_email:
                created_at = format_jalali(message.created_at, "Y/m/d - H:i")
                base_url = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
                admin_url = f"{base_url}/admin/core/contactmessage/{message.id}/change/" if base_url else ""

                brand = getattr(settings, "SITE_NAME", "استیرا")
                subject = f"پیام جدید تماس با ما | {message.name}"
                text_body = (
                    "یک پیام جدید از فرم تماس سایت دریافت شد.\n\n"
                    f"نام: {message.name}\n"
                    f"ایمیل: {message.email}\n"
                    f"??????: {message.phone or '-'}\n"
                    f"زمان: {created_at}\n\n"
                    f"متن پیام:\n{message.message}"
                )
                html_body = render_to_string(
                    "emails/contact_message.html",
                    {
                        "title": "پیام جدید تماس با ما",
                        "preheader": f"پیام جدید از {message.name}",
                        "brand": brand,
                        "subtitle": "یک پیام جدید از فرم تماس سایت دریافت شد.",
                        "name": message.name,
                        "email": message.email,
                        "phone": message.phone,
                        "created_at": created_at,
                        "message_text": message.message,
                        "admin_url": admin_url,
                        "footer": "این پیام به صورت خودکار از سایت استیرا ارسال شده است.",
                    },
                )

                try:
                    email_message = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                        to=[support_email],
                        bcc=bcc_emails,
                        reply_to=[message.email],
                    )
                    email_message.attach_alternative(html_body, "text/html")
                    _send_email_message(email_message)
                except Exception:
                    logger.exception("Failed to build/send contact email")

            return render(
                request,
                "contact.html",
                {
                    "form": ContactForm(),
                    "success": True,
                },
            )
    else:
        form = ContactForm()

    return render(request, "contact.html", {"form": form})


def news_list(request):
    """List news items."""
    news = News.objects.all()
    return render(request, "news_list.html", {"news": news})


def news_detail(request, pk):
    """Show a single news item."""
    item = get_object_or_404(News, pk=pk)
    latest = News.objects.exclude(pk=pk)[:4]
    return render(request, "news_detail.html", {"item": item, "latest": latest})


def faq(request):
    """Render FAQ page."""
    return render(request, "faq.html")


def terms(request):
    """Render Terms & Conditions page."""
    return render(request, "terms.html")


def privacy(request):
    """Render Privacy Policy page."""
    return render(request, "privacy.html")