from __future__ import annotations

from django.utils import translation


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
