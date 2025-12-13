import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from django_otp import login as otp_login

from .models import EmailOTPDevice


def _request_data(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            body = request.body.decode("utf-8") or "{}"
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    return request.POST


@login_required
@require_POST
def request_otp(request):
    data = _request_data(request)
    email = (data.get("email") or request.user.email or "").strip().lower()
    if not email:
        return JsonResponse({"detail": _("Email is required.")}, status=400)

    if request.user.email and email != (request.user.email or "").strip().lower():
        return JsonResponse({"detail": _("Email does not match your account.")}, status=400)

    with transaction.atomic():
        device, _created = EmailOTPDevice.objects.select_for_update().get_or_create(
            user=request.user,
            email=email,
            defaults={"name": "Email", "confirmed": True},
        )

        allowed, info = device.generate_is_allowed()
        if not allowed:
            retry_after = (info or {}).get("retry_after_seconds")
            payload = {"detail": _("If allowed, an OTP has been sent.")}
            if retry_after is not None:
                payload["retry_after_seconds"] = retry_after
            return JsonResponse(payload, status=429)

        device.send_challenge()

    return JsonResponse({"detail": _("If allowed, an OTP has been sent.")}, status=200)


@login_required
@require_POST
def verify_otp(request):
    data = _request_data(request)
    email = (data.get("email") or request.user.email or "").strip().lower()
    token = (data.get("token") or "").strip()

    if not email or not token:
        return JsonResponse({"detail": _("Email and token are required.")}, status=400)

    if request.user.email and email != (request.user.email or "").strip().lower():
        return JsonResponse({"detail": _("Email does not match your account.")}, status=400)

    with transaction.atomic():
        device = (
            EmailOTPDevice.objects.select_for_update()
            .filter(user=request.user, email=email)
            .first()
        )
        if not device:
            return JsonResponse({"detail": _("Invalid or expired OTP.")}, status=400)

        allowed, info = device.verify_is_allowed()
        if not allowed:
            payload = {"detail": _("Too many failed attempts. Request a new code.")}
            if info and "failure_count" in info:
                payload["failure_count"] = info["failure_count"]
            return JsonResponse(payload, status=429)

        if not device.verify_token(token):
            return JsonResponse({"detail": _("Invalid or expired OTP.")}, status=400)

        otp_login(request, device)

    return JsonResponse({"detail": _("OTP verified.")}, status=200)

