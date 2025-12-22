from __future__ import annotations

import logging

from django.conf import settings
from django.db.models import F
from django.utils import timezone, translation

from core.models import DailyVisitStat, SiteVisit

logger = logging.getLogger(__name__)
error_logger = logging.getLogger("core.errors")


class AdminEnglishMiddleware:
    """Force Django admin UI to English (LTR) while keeping the public site Persian."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        previous_language = translation.get_language()
        try:
            if request.path.startswith("/admin"):
                translation.activate("en")
                request.LANGUAGE_CODE = "en"
            return self.get_response(request)
        finally:
            translation.activate(previous_language)


class SiteVisitMiddleware:
    """Track unique site visits per session per day for analytics."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if request.method not in ("GET", "HEAD"):
                return response

            path = request.path or "/"
            if path.startswith("/admin"):
                return response

            static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
            media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
            if path.startswith(static_url) or path.startswith(media_url):
                return response

            session = request.session
            if not session.session_key:
                session.save()
            session_key = session.session_key
            if not session_key:
                return response

            visited_on = timezone.localdate()
            defaults = {"first_path": path}
            if request.user.is_authenticated:
                defaults["user"] = request.user

            visit, created = SiteVisit.objects.get_or_create(
                session_key=session_key,
                visited_on=visited_on,
                defaults=defaults,
            )

            if request.user.is_authenticated:
                SiteVisit.objects.filter(
                    session_key=session_key,
                    visited_on=visited_on,
                    user__isnull=True,
                ).update(user=request.user)

            stat, _created = DailyVisitStat.objects.get_or_create(date=visited_on)
            DailyVisitStat.objects.filter(pk=stat.pk).update(total_hits=F("total_hits") + 1)
            if created:
                DailyVisitStat.objects.filter(pk=stat.pk).update(
                    unique_sessions=F("unique_sessions") + 1
                )
        except Exception:
            logger.exception("Failed to record site visit")

        return response


class SecurityHeadersMiddleware:
    """Add strict security headers (CSP, clickjacking, XSS)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from core.security import build_csp_header
        from django.conf import settings

        response = self.get_response(request)

        csp_value = build_csp_header()
        if csp_value:
            response["Content-Security-Policy"] = csp_value

        response.setdefault("X-Frame-Options", getattr(settings, "X_FRAME_OPTIONS", "DENY"))
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", getattr(settings, "SECURE_REFERRER_POLICY", "same-origin"))
        response.setdefault("X-XSS-Protection", "1; mode=block")
        return response


class ExceptionLoggingMiddleware:
    """Log unhandled exceptions for centralized monitoring."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception:
            error_logger.exception(
                "Unhandled exception",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "user": getattr(request.user, "id", None),
                },
            )
            raise
