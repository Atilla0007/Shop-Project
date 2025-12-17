import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django_otp import login as otp_login

from accounts.models import UserProfile
from .models import SmsOTPDevice


def _request_data(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            body = request.body.decode("utf-8") or "{}"
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    return request.POST


def _safe_next_url(request, next_url: str | None) -> str | None:
    if not next_url:
        return None
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def _get_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _get_or_create_device_for_user(user, phone: str) -> SmsOTPDevice:
    device, _created = SmsOTPDevice.objects.get_or_create(
        user=user,
        phone=phone,
        defaults={"name": "SMS", "confirmed": True},
    )
    return device


@login_required
@require_POST
def request_otp(request):
    data = _request_data(request)
    profile = _get_profile(request.user)
    phone = (data.get("phone") or profile.phone or "").strip()

    if not phone:
        return JsonResponse({"detail": "شماره موبایل وارد نشده است."}, status=400)

    if profile.phone and phone != (profile.phone or "").strip():
        return JsonResponse({"detail": "شماره موبایل با شماره ثبت‌شده در پروفایل مطابقت ندارد."}, status=400)

    with transaction.atomic():
        device = (
            SmsOTPDevice.objects.select_for_update()
            .filter(user=request.user, phone=phone)
            .first()
        )
        if not device:
            device = _get_or_create_device_for_user(request.user, phone)

        allowed, info = device.generate_is_allowed()
        if not allowed:
            retry_after = (info or {}).get("retry_after_seconds")
            payload = {"detail": "درخواست‌های زیادی ثبت شده است. کمی بعد دوباره تلاش کنید."}
            if retry_after is not None:
                payload["retry_after_seconds"] = retry_after
            return JsonResponse(payload, status=429)

        try:
            device.send_challenge()
        except Exception:
            return JsonResponse({"detail": "ارسال پیامک با خطا مواجه شد. لطفاً بعداً تلاش کنید."}, status=500)

    return JsonResponse({"detail": "کد تایید ارسال شد."}, status=200)


@login_required
@require_POST
def verify_otp(request):
    data = _request_data(request)
    profile = _get_profile(request.user)
    phone = (data.get("phone") or profile.phone or "").strip()
    token = (data.get("token") or "").strip()

    if not phone or not token:
        return JsonResponse({"detail": "شماره موبایل و کد را وارد کنید."}, status=400)

    if profile.phone and phone != (profile.phone or "").strip():
        return JsonResponse({"detail": "شماره موبایل با شماره ثبت‌شده در پروفایل مطابقت ندارد."}, status=400)

    with transaction.atomic():
        device = (
            SmsOTPDevice.objects.select_for_update()
            .filter(user=request.user, phone=phone)
            .first()
        )
        if not device:
            return JsonResponse({"detail": "کد تایید معتبر نیست."}, status=400)

        allowed, info = device.verify_is_allowed()
        if not allowed:
            payload = {"detail": "تعداد تلاش‌های ناموفق زیاد است. کمی بعد دوباره تلاش کنید."}
            if info and "failure_count" in info:
                payload["failure_count"] = info["failure_count"]
            return JsonResponse(payload, status=429)

        if not device.verify_token(token):
            return JsonResponse({"detail": "کد تایید معتبر نیست."}, status=400)

        otp_login(request, device)
        if not profile.phone_verified:
            profile.mark_phone_verified()

    return JsonResponse({"detail": "شماره موبایل با موفقیت تایید شد."}, status=200)


@login_required
def verify_page(request):
    profile = _get_profile(request.user)
    if not profile.phone:
        return redirect("profile")

    next_url = _safe_next_url(request, request.GET.get("next") or request.POST.get("next"))
    phone = (profile.phone or "").strip()

    send_error = None

    with transaction.atomic():
        device = (
            SmsOTPDevice.objects.select_for_update()
            .filter(user=request.user, phone=phone)
            .first()
        )
        if not device:
            device = _get_or_create_device_for_user(request.user, phone)

        if request.method == "POST":
            digits = [(request.POST.get(f"d{i}") or "").strip() for i in range(1, 7)]
            token = "".join(digits)

            if len(token) != 6 or not token.isdigit():
                return render(
                    request,
                    "accounts/verify_phone.html",
                    {"profile": profile, "error": "کد را درست وارد کنید.", "next": next_url},
                    status=400,
                )

            allowed, _info = device.verify_is_allowed()
            if not allowed:
                return render(
                    request,
                    "accounts/verify_phone.html",
                    {
                        "profile": profile,
                        "error": "تعداد تلاش‌های ناموفق زیاد است. کمی بعد دوباره تلاش کنید.",
                        "next": next_url,
                    },
                    status=429,
                )

            if device.verify_token(token):
                otp_login(request, device)
                if not profile.phone_verified:
                    profile.mark_phone_verified()
                return redirect(next_url or "profile")

            return render(
                request,
                "accounts/verify_phone.html",
                {"profile": profile, "error": "کد تایید صحیح نیست.", "next": next_url},
                status=400,
            )

        should_resend = request.GET.get("resend") == "1"
        is_expired = (not device.valid_until) or timezone.now() >= device.valid_until
        if should_resend or (not device.token_hash) or is_expired:
            try:
                device.send_challenge()
            except PermissionError:
                pass
            except Exception:
                send_error = "ارسال پیامک با خطا مواجه شد. لطفاً بعداً تلاش کنید."

    return render(
        request,
        "accounts/verify_phone.html",
        {"profile": profile, "next": next_url, "send_error": send_error},
    )
