from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render

from .services import LoginProtectionService, TooManyRequests, get_client_ip, normalize_identifier


class LoginProtectionMiddleware:
    """Protect login endpoints against brute-force attempts.

    Security decisions are centralized in LoginProtectionService.
    This middleware only applies to POST requests on configured login paths.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and self._is_protected_path(request.path):
            ip = get_client_ip(request)
            identifier = normalize_identifier(
                request.POST.get("username")
                or request.POST.get("email")
                or request.POST.get("phone")
                or request.POST.get("identifier")
            )

            if not identifier:
                # Do not proceed to authentication; avoid unnecessary backend work.
                LoginProtectionService.log_rejected_attempt(
                    ip=ip,
                    identifier="",
                    reason="missing_identifier",
                    request=request,
                )
                return self._too_many_response(
                    request,
                    status_code=400,
                    retry_after_seconds=0,
                    message="شناسه کاربری نامعتبر است.",
                )

            try:
                LoginProtectionService.check_login_allowed(ip=ip, identifier=identifier)
            except TooManyRequests as exc:
                LoginProtectionService.log_rejected_attempt(
                    ip=ip,
                    identifier=identifier,
                    reason=exc.decision.reason,
                    request=request,
                )
                return self._too_many_response(
                    request,
                    status_code=exc.decision.status_code,
                    retry_after_seconds=exc.decision.retry_after_seconds,
                    message="تلاش‌های ورود بیش از حد مجاز است. لطفاً بعداً دوباره تلاش کنید.",
                )

        return self.get_response(request)

    def _is_protected_path(self, path: str) -> bool:
        configured_login = getattr(settings, "AUTH_SECURITY_LOGIN_PATHS", ["/login/", "/admin/login/"])
        extra = getattr(settings, "AUTH_SECURITY_PROTECTED_PATHS", [])
        if isinstance(configured_login, str):
            configured_login = [p.strip() for p in configured_login.split(",") if p.strip()]
        if isinstance(extra, str):
            extra = [p.strip() for p in extra.split(",") if p.strip()]
        configured = configured_login + extra
        if isinstance(configured, str):
            configured = [p.strip() for p in configured.split(",") if p.strip()]
        return path in configured

    def _too_many_response(self, request, *, status_code: int, retry_after_seconds: int, message: str) -> HttpResponse:
        if request.path == "/login/":
            next_url = request.POST.get("next") or request.GET.get("next")
            resp = render(request, "accounts/login.html", {"error": message, "next": next_url}, status=status_code)
        else:
            resp = HttpResponse(message, status=status_code)
        if retry_after_seconds and status_code == 429:
            resp["Retry-After"] = str(int(retry_after_seconds))
        return resp
