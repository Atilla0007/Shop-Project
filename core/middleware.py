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

