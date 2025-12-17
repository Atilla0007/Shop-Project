from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from store.models import Order

from .forms import SignupForm
from .models import UserProfile


def _get_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


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


def login_view(request):
    next_url = _safe_next_url(request, request.GET.get("next") or request.POST.get("next"))
    if request.user.is_authenticated:
        return redirect(next_url or "home")

    if request.method == "POST":
        username = request.POST.get("username") or request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(next_url or "home")
        return render(
            request,
            "accounts/login.html",
            {"error": "نام کاربری یا رمز عبور اشتباه است.", "next": next_url},
        )

    return render(request, "accounts/login.html", {"next": next_url})


def signup(request):
    next_url = _safe_next_url(request, request.GET.get("next") or request.POST.get("next"))
    if request.user.is_authenticated:
        return redirect(next_url or "home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(next_url or "home")
        return render(request, "accounts/signup.html", {"form": form, "next": next_url})

    form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form, "next": next_url})


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def profile_view(request):
    profile = _get_profile(request.user)
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items", "items__product")
        .order_by("-created_at")
    )
    return render(request, "accounts/profile.html", {"profile": profile, "orders": orders})


@login_required
def profile_edit_view(request):
    profile = _get_profile(request.user)

    def current_values():
        return {
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "phone": profile.phone,
        }

    if request.method != "POST":
        return render(request, "accounts/profile_edit.html", {"values": current_values()})

    values = {
        "first_name": (request.POST.get("first_name") or "").strip(),
        "last_name": (request.POST.get("last_name") or "").strip(),
        "email": (request.POST.get("email") or "").strip(),
        "phone": (request.POST.get("phone") or "").strip(),
    }

    if request.POST.get("confirm") != "1":
        return render(request, "accounts/profile_confirm.html", {"values": values})

    request.user.first_name = values["first_name"]
    request.user.last_name = values["last_name"]
    old_email = (request.user.email or "").strip()
    request.user.email = values["email"]
    request.user.save(update_fields=["first_name", "last_name", "email"])

    email_changed = (values["email"] or "").strip() != old_email
    phone_changed = values["phone"] != profile.phone

    if email_changed:
        profile.email_verified = False
        profile.email_verified_at = None

    if phone_changed:
        profile.phone = values["phone"]
        profile.phone_verified = False
        profile.phone_verified_at = None

    update_fields = []
    if email_changed:
        update_fields.extend(["email_verified", "email_verified_at"])
    if phone_changed:
        update_fields.extend(["phone", "phone_verified", "phone_verified_at"])
    if update_fields:
        profile.save(update_fields=update_fields)

    return redirect("profile")

