from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from django.db.models import Q

from store.models import Order, ShippingAddress

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

    error = ""
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            if not request.POST.get("accept_terms"):
                error = "برای ایجاد حساب باید با قوانین و حریم خصوصی موافقت کنید."
            else:
                user = form.save()
                profile = _get_profile(user)
                profile.privacy_accepted_at = timezone.now()
                profile.marketing_email_opt_in = bool(request.POST.get("optin_email"))
                profile.marketing_sms_opt_in = bool(request.POST.get("optin_sms"))
                profile.marketing_opt_in_updated_at = timezone.now()
                profile.save(
                    update_fields=[
                        "privacy_accepted_at",
                        "marketing_email_opt_in",
                        "marketing_sms_opt_in",
                        "marketing_opt_in_updated_at",
                    ]
                )
                login(request, user)
                return redirect(next_url or "home")
        return render(request, "accounts/signup.html", {"form": form, "next": next_url, "error": error})

    form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form, "next": next_url, "error": error})


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def profile_view(request):
    profile = _get_profile(request.user)

    status_filter = (request.GET.get("status") or "").strip()
    search_term = (request.GET.get("q") or "").strip()

    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items", "items__product")
        .order_by("-created_at")
    )
    if status_filter:
        orders = orders.filter(status=status_filter)
    if search_term:
        digits = "".join(ch for ch in search_term if ch.isdigit())
        q_objects = Q(items__product__name__icontains=search_term) | Q(city__icontains=search_term) | Q(
            province__icontains=search_term
        ) | Q(address__icontains=search_term)
        if digits:
            try:
                numeric_id = int(digits)
                q_objects |= Q(id=numeric_id)
            except ValueError:
                pass
        orders = orders.filter(q_objects).distinct()

    addresses = (
        ShippingAddress.objects.filter(user=request.user)
        .order_by("-is_default", "-updated_at")
    )

    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile,
            "orders": orders,
            "order_statuses": Order.STATUS_CHOICES,
            "active_status": status_filter,
            "search_term": search_term,
            "addresses": addresses,
        },
    )


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


@login_required
def address_save(request, address_id: int | None = None):
    if request.method != "POST":
        return redirect("profile")

    instance = None
    if address_id:
        instance = ShippingAddress.objects.filter(pk=address_id, user=request.user).first()
        if not instance:
            return redirect("profile")

    data = {
        "label": (request.POST.get("label") or "").strip(),
        "first_name": (request.POST.get("first_name") or "").strip(),
        "last_name": (request.POST.get("last_name") or "").strip(),
        "phone": (request.POST.get("phone") or "").strip(),
        "email": (request.POST.get("email") or "").strip(),
        "province": (request.POST.get("province") or "").strip(),
        "city": (request.POST.get("city") or "").strip(),
        "address": (request.POST.get("address") or "").strip(),
        "is_default": bool(request.POST.get("is_default")),
    }

    target = instance or ShippingAddress(user=request.user)
    for field, value in data.items():
        setattr(target, field, value)
    target.save()

    if target.is_default:
        ShippingAddress.objects.filter(user=request.user).exclude(pk=target.pk).update(is_default=False)

    return redirect("profile")


@login_required
def address_delete(request, address_id: int):
    if request.method != "POST":
        return redirect("profile")

    addr = ShippingAddress.objects.filter(pk=address_id, user=request.user).first()
    if not addr:
        return redirect("profile")

    was_default = addr.is_default
    addr.delete()

    if was_default:
        next_default = (
            ShippingAddress.objects.filter(user=request.user).order_by("-updated_at").first()
        )
        if next_default:
            next_default.is_default = True
            next_default.save(update_fields=["is_default"])

    return redirect("profile")


@login_required
def address_set_default(request, address_id: int):
    if request.method != "POST":
        return redirect("profile")

    addr = ShippingAddress.objects.filter(pk=address_id, user=request.user).first()
    if not addr:
        return redirect("profile")

    ShippingAddress.objects.filter(user=request.user).update(is_default=False)
    addr.is_default = True
    addr.save(update_fields=["is_default"])
    return redirect("profile")
