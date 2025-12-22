
from datetime import timedelta
import json
import re
from threading import Thread

from django.conf import settings
from django.db import close_old_connections, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from .invoice import render_manual_invoice_pdf, render_order_invoice_pdf
from .models import Product, CartItem, Order, OrderItem, Category, ManualInvoiceSequence, ShippingAddress
from accounts.models import UserProfile
from core.models import DiscountCode, DiscountRedemption, ShippingSettings
from core.utils.formatting import format_money
from core.utils.jalali import format_jalali


SESSION_CART_KEY = 'cart'


def _send_order_payment_submitted_email_nonblocking(*, order_id: int, request=None) -> None:
    def _send(req=None) -> None:
        close_old_connections()
        try:
            from store.emails import send_order_payment_submitted_email

            order = (
                Order.objects.select_related("user")
                .prefetch_related("items__product")
                .get(pk=order_id)
            )
            send_order_payment_submitted_email(order=order, request=req)
        except Exception:
            pass
        finally:
            close_old_connections()

    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    if "smtp" in backend:
        Thread(target=lambda: _send(None), daemon=True).start()
    else:
        _send(request)


def _get_session_cart(request) -> dict[str, int]:
    cart = request.session.get(SESSION_CART_KEY) or {}
    if not isinstance(cart, dict):
        cart = {}

    normalized: dict[str, int] = {}
    for key, value in cart.items():
        try:
            product_id = int(key)
        except (TypeError, ValueError):
            continue
        try:
            quantity = int(value)
        except (TypeError, ValueError):
            continue

        if quantity <= 0:
            continue
        normalized[str(product_id)] = quantity

    if normalized != cart:
        request.session[SESSION_CART_KEY] = normalized
        request.session.modified = True

    return normalized


def _set_session_cart(request, cart: dict[str, int]) -> None:
    request.session[SESSION_CART_KEY] = cart


def _check_discount_eligibility(discount: DiscountCode, user) -> tuple[bool, str]:
    """Return eligibility for a discount code (limits + assigned user)."""

    if discount.assigned_user_id and discount.assigned_user_id != user.id:
        return False, 'ط§غŒظ† ع©ط¯ ظپظ‚ط· ط¨ط±ط§غŒ ع©ط§ط±ط¨ط± ظ…ط´ط®طµ ط´ط¯ظ‡ ظ‚ط§ط¨ظ„ ط§ط³طھظپط§ط¯ظ‡ ط§ط³طھ.'

    if discount.max_uses is not None and int(discount.uses_count or 0) >= int(discount.max_uses):
        return False, 'ط¸ط±ظپغŒطھ ط§ط³طھظپط§ط¯ظ‡ ط§ط² ط§غŒظ† ع©ط¯ طھع©ظ…غŒظ„ ط´ط¯ظ‡ ط§ط³طھ.'

    if discount.max_uses_per_user:
        used_by_user = DiscountRedemption.objects.filter(discount_code=discount, user=user).count()
        if used_by_user >= int(discount.max_uses_per_user):
            return False, 'ط§غŒظ† ع©ط¯ ظ‚ط¨ظ„ط§ظ‹ طھظˆط³ط· ط´ظ…ط§ ط§ط³طھظپط§ط¯ظ‡ ط´ط¯ظ‡ ط§ط³طھ.'

    return True, ""
    request.session.modified = True


def _add_to_session_cart(request, product_id: int, quantity_delta: int = 1) -> None:
    cart = _get_session_cart(request)
    key = str(product_id)
    cart[key] = max(1, int(cart.get(key, 0)) + int(quantity_delta))
    _set_session_cart(request, cart)


def _merge_session_cart_into_user(request) -> None:
    if not request.user.is_authenticated:
        return

    cart = _get_session_cart(request)
    if not cart:
        return

    products = Product.objects.filter(id__in=list(cart.keys()))
    for product in products:
        quantity = int(cart.get(str(product.id), 0))
        if quantity <= 0:
            continue
        item, created = CartItem.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': quantity},
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity'])

    _set_session_cart(request, {})


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


def _add_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query[key] = [value]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _get_compare_list(request):
    return request.session.get('compare_list', [])


def _save_compare_list(request, ids):
    request.session['compare_list'] = ids
    request.session.modified = True


def shop(request):
    products = Product.objects.all()
    categories = Category.objects.all()

    if request.user.is_authenticated:
        _merge_session_cart_into_user(request)
        cart_product_ids = set(CartItem.objects.filter(user=request.user).values_list('product_id', flat=True))
    else:
        session_cart = _get_session_cart(request)
        cart_product_ids = {int(k) for k in session_cart.keys() if str(k).isdigit()}

    category_id = request.GET.get('category')
    domain = request.GET.get('domain')

    if category_id:
        products = products.filter(category_id=category_id)
    if domain:
        products = products.filter(domain__icontains=domain)

    return render(request, 'store/shop.html', {
        'products': products,
        'categories': categories,
        'cart_product_ids': cart_product_ids,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    features = product.features.all()
    absolute_url = request.build_absolute_uri()
    return render(request, 'store/product_detail.html', {
        'product': product,
        'features': features,
        'absolute_url': absolute_url,
    })



def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    raw_qty = (request.POST.get('qty') or request.GET.get('qty') or '1').strip()
    raw_qty = raw_qty.translate(str.maketrans("غ°غ±غ²غ³غ´غµغ¶غ·غ¸غ¹ظ ظ،ظ¢ظ£ظ¤ظ¥ظ¦ظ§ظ¨ظ©", "01234567890123456789"))
    try:
        qty = int(raw_qty)
    except (TypeError, ValueError):
        qty = 1
    qty = max(1, min(99, qty))

    if request.user.is_authenticated:
        _merge_session_cart_into_user(request)
        item, created = CartItem.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': qty},
        )
        if not created:
            item.quantity += qty
            item.save(update_fields=['quantity'])
    else:
        _add_to_session_cart(request, product.id, qty)

    next_url = (
        _safe_next_url(request, request.GET.get('next'))
        or _safe_next_url(request, request.META.get('HTTP_REFERER'))
        or reverse('cart')
    )
    return redirect(_add_query_param(next_url, 'cart_open', '1'))


def cart(request):
    if request.user.is_authenticated:
        _merge_session_cart_into_user(request)
        items_qs = CartItem.objects.filter(user=request.user).select_related('product')
        total = sum(i.total_price() for i in items_qs)
        return render(request, 'store/cart.html', {'items': items_qs, 'total': total})

    session_cart = _get_session_cart(request)
    products = list(Product.objects.filter(id__in=list(session_cart.keys())))
    products_by_id = {str(p.id): p for p in products}
    items = []
    total = 0
    for product_id, quantity in session_cart.items():
        product = products_by_id.get(product_id)
        if not product:
            continue
        item_total = int(product.price) * int(quantity)
        items.append({'product': product, 'quantity': int(quantity), 'total_price': item_total})
        total += item_total

    return render(request, 'store/cart.html', {'items': items, 'total': total})

@login_required
@require_POST
def discount_preview(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.email_verified:
        return JsonResponse({'ok': False, 'message': 'ط§ط¨طھط¯ط§ ط§غŒظ…غŒظ„ ط®ظˆط¯ ط±ط§ طھط§غŒغŒط¯ ع©ظ†غŒط¯.'}, status=403)

    _merge_session_cart_into_user(request)
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')
    items_subtotal = int(sum(item.total_price() for item in cart_items))
    if not cart_items.exists():
        return JsonResponse({'ok': False, 'message': 'ط³ط¨ط¯ ط®ط±غŒط¯ ط´ظ…ط§ ط®ط§ظ„غŒ ط§ط³طھ.'}, status=400)

    code = (request.POST.get('code') or '').strip().upper().replace(' ', '')
    if not code:
        return JsonResponse({
            'ok': True,
            'code': '',
            'percent': 0,
            'amount': 0,
            'items_subtotal': items_subtotal,
            'subtotal': items_subtotal,
            'message': 'ع©ط¯ طھط®ظپغŒظپ ط­ط°ظپ ط´ط¯.',
        })

    discount = (
        DiscountCode.objects.filter(code=code, is_active=True)
        .order_by('-updated_at')
        .first()
    )
    if not discount:
        return JsonResponse({'ok': False, 'message': 'ع©ط¯ طھط®ظپغŒظپ ظ†ط§ظ…ط¹طھط¨ط± ط§ط³طھ.'})

    is_ok, message = _check_discount_eligibility(discount, request.user)
    if not is_ok:
        return JsonResponse({'ok': False, 'message': message})

    percent = int(discount.percent)
    amount = int(items_subtotal) * percent // 100
    subtotal = int(items_subtotal) - int(amount)
    return JsonResponse({
        'ok': True,
        'code': code,
        'percent': percent,
        'amount': amount,
        'items_subtotal': items_subtotal,
        'subtotal': subtotal,
        'message': f'ع©ط¯ {code} ط§ط¹ظ…ط§ظ„ ط´ط¯ ({percent}ظھ).',
    })


@login_required
def checkout(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.email_verified:
        verify_url = reverse("email_otp_verify_page")
        return redirect(f"{verify_url}?next={quote(request.get_full_path())}")

    _merge_session_cart_into_user(request)
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')
    items_subtotal = sum(item.total_price() for item in cart_items)
    subtotal = int(items_subtotal)
    item_count = sum(int(item.quantity) for item in cart_items)

    shipping_settings = ShippingSettings.get_solo()
    shipping_fee_per_item = int(shipping_settings.shipping_fee or 0)
    free_shipping_min_total = int(shipping_settings.free_shipping_min_total or 0)

    account_first_name = (request.user.first_name or "").strip()
    account_last_name = (request.user.last_name or "").strip()
    default_address = ShippingAddress.objects.filter(user=request.user, is_default=True).first()

    def normalize_digits(value: str) -> str:
        if not value:
            return value
        return value.translate(str.maketrans("غ°غ±غ²غ³غ´غµغ¶غ·غ¸غ¹ظ ظ،ظ¢ظ£ظ¤ظ¥ظ¦ظ§ظ¨ظ©", "01234567890123456789"))

    def compute_shipping(province_value: str | None, effective_subtotal: int) -> tuple[int, bool, bool, int]:
        province_selected = bool((province_value or "").strip())
        if not province_selected:
            return 0, False, False, 0

        shipping_total_full = int(shipping_fee_per_item) * int(item_count)
        is_free = bool(free_shipping_min_total) and int(effective_subtotal) >= int(free_shipping_min_total)
        applied_fee = 0 if is_free else shipping_total_full
        return applied_fee, True, is_free, shipping_total_full

    discount_code = ""
    discount_percent = 0
    discount_amount = 0

    def _normalize_discount_code(raw: str) -> str:
        return (raw or "").strip().upper().replace(" ", "")

    if request.method == 'POST':
        recipient_is_other = bool(request.POST.get('recipient_is_other'))
        if not account_first_name or not account_last_name:
            recipient_is_other = True

        account_phone = normalize_digits((profile.phone or '').strip()).replace(' ', '').replace('-', '')

        values = {
            'first_name': (request.POST.get('first_name') or '').strip(),
            'last_name': (request.POST.get('last_name') or '').strip(),
            'phone': normalize_digits((request.POST.get('phone') or '').strip()),
            'email': (request.POST.get('email') or '').strip(),
            'province': (request.POST.get('province') or '').strip(),
            'city': (request.POST.get('city') or '').strip(),
            'address': (request.POST.get('address') or '').strip(),
            'note': (request.POST.get('note') or '').strip(),
            'discount_code': _normalize_discount_code(request.POST.get('discount_code') or ''),
            'discount_code_applied': _normalize_discount_code(request.POST.get('discount_code_applied') or ''),
            'recipient_is_other': recipient_is_other,
            'address_id': (request.POST.get('address_id') or '').strip(),
            'accept_terms': bool(request.POST.get('accept_terms')),
            'optin_email': bool(request.POST.get('optin_email')),
            'optin_sms': bool(request.POST.get('optin_sms')),
        }

        if not recipient_is_other:
            values['first_name'] = account_first_name
            values['last_name'] = account_last_name
            values['phone'] = account_phone

        selected_address = default_address
        if values['address_id'].isdigit():
            selected_address = ShippingAddress.objects.filter(user=request.user, pk=int(values['address_id'])).first()

                errors: dict[str, str] = {}
        if not values['first_name']:
            errors['first_name'] = 'باید نام را وارد کنید.'
        if not values['last_name']:
            errors['last_name'] = 'باید نام خانوادگی را وارد کنید.'
        if not values['phone']:
            errors['phone'] = 'باید شماره موبایل را وارد کنید.'
        if not values['province']:
            errors['province'] = 'باید استان را انتخاب کنید.'
        if not values['city']:
            errors['city'] = 'باید شهر را انتخاب کنید.'
        if not values['address']:
            errors['address'] = 'باید آدرس کامل را وارد کنید.'
        if not values['accept_terms']:
            errors['accept_terms'] = 'لطفاً با قوانین و حریم خصوصی موافقت کنید.'

        if values['phone']:
            new_phone = values['phone'].replace(' ', '').replace('-', '')
            values['phone'] = new_phone

        if not profile.phone_verified:
            errors['phone_verified'] = 'برای ثبت سفارش باید موبایل خود را تأیید کنید.'
            errors['phone_verified'] = 'برای ثبت سفارش باید موبایل خود را تأیید کنید.'

        discount_code = values.get('discount_code_applied') or ""
        if discount_code:
            discount = (
                DiscountCode.objects.filter(code=discount_code, is_active=True)
                .order_by('-updated_at')
                .first()
            )
            if not discount:
                errors['discount_code'] = 'ع©ط¯ طھط®ظپغŒظپ ظ†ط§ظ…ط¹طھط¨ط± ط§ط³طھ.'
                discount_code = ""
            else:
                is_ok, message = _check_discount_eligibility(discount, request.user)
                if not is_ok:
                    errors['discount_code'] = message
                    discount_code = ""
                else:
                    discount_percent = int(discount.percent)
                    discount_amount = int(items_subtotal) * discount_percent // 100
                    subtotal = int(items_subtotal) - int(discount_amount)

        shipping_applied, shipping_applicable, shipping_is_free, shipping_total_full = compute_shipping(
            values['province'],
            int(subtotal),
        )
        total_payable = int(subtotal) + int(shipping_applied)

        if not cart_items.exists():
            errors['cart'] = 'ط³ط¨ط¯ ط®ط±غŒط¯ ط´ظ…ط§ ط®ط§ظ„غŒ ط§ط³طھ.'

        if errors:
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'items_subtotal': items_subtotal,
                'subtotal': subtotal,
                'discount_code': discount_code,
                'discount_percent': discount_percent,
                'discount_amount': discount_amount,
                'shipping_fee_per_item': shipping_fee_per_item,
                'shipping_item_count': item_count,
                'shipping_total_full': shipping_total_full,
                'free_shipping_min_total': free_shipping_min_total,
                'shipping_applicable': shipping_applicable,
                'shipping_is_free': shipping_is_free,
                'shipping_applied': shipping_applied,
                'total_payable': total_payable,
                'values': values,
                'errors': errors,
                'show_phone_verify_modal': bool(errors.get('phone_verified')),
            })

        recheck_error = ""
        order = None
        with transaction.atomic():
            applied_discount = None
            if discount_code:
                applied_discount = (
                    DiscountCode.objects.select_for_update()
                    .filter(code=discount_code, is_active=True)
                    .first()
                )
                if not applied_discount:
                    recheck_error = 'ع©ط¯ طھط®ظپغŒظپ ظ†ط§ظ…ط¹طھط¨ط± ط§ط³طھ.'
                else:
                    is_ok, message = _check_discount_eligibility(applied_discount, request.user)
                    if not is_ok:
                        recheck_error = message
                    else:
                        discount_percent = int(applied_discount.percent)
                        discount_amount = int(items_subtotal) * discount_percent // 100
                        subtotal = int(items_subtotal) - int(discount_amount)
                        (
                            shipping_applied,
                            shipping_applicable,
                            shipping_is_free,
                            shipping_total_full,
                        ) = compute_shipping(values['province'], int(subtotal))
                        total_payable = int(subtotal) + int(shipping_applied)

            if recheck_error:
                pass
            else:
                order = Order.objects.create(
                    user=request.user,
                    shipping_address=selected_address,
                    total_price=total_payable,
                    status='unpaid',
                    first_name=values['first_name'],
                    last_name=values['last_name'],
                    phone=values['phone'],
                    email=values['email'] or (request.user.email or ''),
                    province=values['province'],
                    city=values['city'],
                    address=values['address'],
                    note=values['note'],
                    items_subtotal=int(items_subtotal),
                    discount_code=discount_code,
                    discount_percent=discount_percent,
                    discount_amount=discount_amount,
                    shipping_fee_per_item=shipping_fee_per_item,
                    shipping_item_count=item_count,
                    shipping_total_full=shipping_total_full,
                    shipping_total=shipping_applied,
                    shipping_is_free=shipping_is_free,
                    free_shipping_min_total=free_shipping_min_total,
                    payment_status='unpaid',
                )
                for item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        unit_price=item.product.price,
                    )

                if applied_discount:
                    DiscountRedemption.objects.create(
                        discount_code=applied_discount,
                        user=request.user,
                        order_id=order.id,
                    )
                    applied_discount.uses_count = int(applied_discount.uses_count or 0) + 1
                    applied_discount.save(update_fields=["uses_count", "updated_at"])

                cart_items.delete()

        if not recheck_error and values.get("accept_terms"):
            update_fields = []
            if not getattr(profile, "privacy_accepted_at", None):
                profile.privacy_accepted_at = timezone.now()
                update_fields.append("privacy_accepted_at")
            email_opt = bool(values.get("optin_email"))
            sms_opt = bool(values.get("optin_sms"))
            if getattr(profile, "marketing_email_opt_in", False) != email_opt or getattr(profile, "marketing_sms_opt_in", False) != sms_opt:
                profile.marketing_email_opt_in = email_opt
                profile.marketing_sms_opt_in = sms_opt
                profile.marketing_opt_in_updated_at = timezone.now()
                update_fields.extend(["marketing_email_opt_in", "marketing_sms_opt_in", "marketing_opt_in_updated_at"])
            if update_fields:
                profile.save(update_fields=update_fields)
        if recheck_error:
            discount_code = ""
            discount_percent = 0
            discount_amount = 0
            subtotal = int(items_subtotal)
            (
                shipping_applied,
                shipping_applicable,
                shipping_is_free,
                shipping_total_full,
            ) = compute_shipping(values['province'], int(subtotal))
            total_payable = int(subtotal) + int(shipping_applied)
            errors['discount_code'] = recheck_error
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'items_subtotal': items_subtotal,
                'subtotal': subtotal,
                'discount_code': discount_code,
                'discount_percent': discount_percent,
                'discount_amount': discount_amount,
                'shipping_fee_per_item': shipping_fee_per_item,
                'shipping_item_count': item_count,
                'shipping_total_full': shipping_total_full,
                'free_shipping_min_total': free_shipping_min_total,
                'shipping_applicable': shipping_applicable,
                'shipping_is_free': shipping_is_free,
                'shipping_applied': shipping_applied,
                'total_payable': total_payable,
                'values': values,
                'errors': errors,
                'show_phone_verify_modal': bool(errors.get('phone_verified')),
            })

        return redirect(reverse('payment', args=[order.id]))

    values = {
        'first_name': account_first_name,
        'last_name': account_last_name,
        'phone': normalize_digits((profile.phone or '').strip()).replace(' ', '').replace('-', ''),
        'email': (request.user.email or '').strip(),
        'province': default_address.province if default_address else '',
        'city': default_address.city if default_address else '',
        'address': default_address.address if default_address else '',
        'note': '',
        'discount_code': '',
        'recipient_is_other': bool(not account_first_name or not account_last_name),
        'address_id': str(default_address.id) if default_address else '',
        'accept_terms': False,
        'optin_email': bool(getattr(profile,'marketing_email_opt_in', False)),
        'optin_sms': bool(getattr(profile,'marketing_sms_opt_in', False)),
    }
    shipping_applied, shipping_applicable, shipping_is_free, shipping_total_full = compute_shipping(
        values['province'],
        int(subtotal),
    )
    total_payable = int(subtotal) + int(shipping_applied)

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'items_subtotal': items_subtotal,
        'subtotal': subtotal,
        'discount_code': discount_code,
        'discount_percent': discount_percent,
        'discount_amount': discount_amount,
        'shipping_fee_per_item': shipping_fee_per_item,
        'shipping_item_count': item_count,
        'shipping_total_full': shipping_total_full,
        'free_shipping_min_total': free_shipping_min_total,
        'shipping_applicable': shipping_applicable,
        'shipping_is_free': shipping_is_free,
        'shipping_applied': shipping_applied,
        'total_payable': total_payable,
        'values': values,
        'errors': {},
        'show_phone_verify_modal': bool(values['phone'] and not profile.phone_verified),
    })


@login_required
def payment(request, order_id: int):
    from core.models import PaymentSettings

    order = get_object_or_404(Order, pk=order_id, user=request.user)
    payment_settings = PaymentSettings.get_solo()
    items_after_discount = int(order.items_subtotal) - int(order.discount_amount or 0)

    telegram_link = ''
    if payment_settings.telegram_username:
        telegram_link = f"https://t.me/{payment_settings.telegram_username.lstrip('@')}"

    whatsapp_link = ''
    if payment_settings.whatsapp_number:
        number = ''.join(ch for ch in payment_settings.whatsapp_number if ch.isdigit() or ch == '+')
        number = number.lstrip('+')
        if number:
            whatsapp_link = f"https://wa.me/{number}"

    can_submit = order.status != 'canceled' and order.payment_status not in ('approved',)

    return render(request, 'store/payment_choose.html', {
        'order': order,
        'items_after_discount': items_after_discount,
        'payment_settings': payment_settings,
        'telegram_link': telegram_link,
        'whatsapp_link': whatsapp_link,
        'can_submit': can_submit,
    })


@login_required
def payment_card_to_card(request, order_id: int):
    from core.models import PaymentSettings

    order = get_object_or_404(Order, pk=order_id, user=request.user)
    payment_settings = PaymentSettings.get_solo()
    items_after_discount = int(order.items_subtotal) - int(order.discount_amount or 0)

    telegram_link = ''
    if payment_settings.telegram_username:
        telegram_link = f"https://t.me/{payment_settings.telegram_username.lstrip('@')}"

    whatsapp_link = ''
    if payment_settings.whatsapp_number:
        number = ''.join(ch for ch in payment_settings.whatsapp_number if ch.isdigit() or ch == '+')
        number = number.lstrip('+')
        if number:
            whatsapp_link = f"https://wa.me/{number}"

    error = None
    submitted = request.GET.get('submitted') == '1'

    if request.method == 'POST' and order.status != 'canceled' and order.payment_status not in ('approved',):
        already_submitted = order.payment_status == 'submitted'
        if not payment_settings.card_number:
            error = 'ط´ظ…ط§ط±ظ‡ ع©ط§ط±طھ ظ‡ظ†ظˆط² طھظˆط³ط· ط§ط¯ظ…غŒظ† طھظ†ط¸غŒظ… ظ†ط´ط¯ظ‡ ط§ط³طھ.'
        else:
            receipt = request.FILES.get('receipt')
            if not receipt:
                error = 'ظ„ط·ظپط§ظ‹ طھطµظˆغŒط± ظپغŒط´ ظˆط§ط±غŒط²غŒ ط±ط§ ط¨ط§ط±ع¯ط°ط§ط±غŒ ع©ظ†غŒط¯.'
            else:
                order.payment_method = 'card_to_card'
                order.payment_status = 'submitted'
                order.payment_submitted_at = timezone.now()
                if order.receipt_file:
                    try:
                        order.receipt_file.delete(save=False)
                    except Exception:
                        pass
                order.receipt_file = receipt
                order.save(update_fields=['payment_method', 'payment_status', 'payment_submitted_at', 'receipt_file'])

                if not already_submitted:
                    _send_order_payment_submitted_email_nonblocking(order_id=order.id, request=request)

                return redirect(f"{reverse('profile')}?payment_submitted=1#orders")

    return render(request, 'store/payment_card_to_card.html', {
        'order': order,
        'items_after_discount': items_after_discount,
        'payment_settings': payment_settings,
        'telegram_link': telegram_link,
        'whatsapp_link': whatsapp_link,
        'submitted': submitted,
        'error': error,
    })


@login_required
def payment_contact_admin(request, order_id: int):
    from core.models import PaymentSettings

    order = get_object_or_404(Order, pk=order_id, user=request.user)
    payment_settings = PaymentSettings.get_solo()
    items_after_discount = int(order.items_subtotal) - int(order.discount_amount or 0)

    telegram_link = ''
    if payment_settings.telegram_username:
        telegram_link = f"https://t.me/{payment_settings.telegram_username.lstrip('@')}"

    whatsapp_link = ''
    if payment_settings.whatsapp_number:
        number = ''.join(ch for ch in payment_settings.whatsapp_number if ch.isdigit() or ch == '+')
        number = number.lstrip('+')
        if number:
            whatsapp_link = f"https://wa.me/{number}"

    error = None
    submitted = request.GET.get('submitted') == '1'

    if request.method == 'POST' and order.status != 'canceled' and order.payment_status not in ('approved',):
        already_submitted = order.payment_status == 'submitted'

        order.payment_method = 'contact_admin'
        order.payment_status = 'submitted'
        order.payment_submitted_at = timezone.now()
        # If user switches to contact_admin, the receipt is not required.
        order.receipt_file = None
        order.save(update_fields=['payment_method', 'payment_status', 'payment_submitted_at', 'receipt_file'])

        if not already_submitted:
            _send_order_payment_submitted_email_nonblocking(order_id=order.id, request=request)

        return redirect(f"{reverse('payment_contact_admin', args=[order.id])}?submitted=1")

    return render(request, 'store/payment_contact_admin.html', {
        'order': order,
        'items_after_discount': items_after_discount,
        'payment_settings': payment_settings,
        'telegram_link': telegram_link,
        'whatsapp_link': whatsapp_link,
        'submitted': submitted,
        'error': error,
    })


@login_required
def proforma_pdf(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id, user=request.user)

    pdf_bytes = render_order_invoice_pdf(order=order, title="Proforma")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="proforma-{order.id}.pdf"'
    return response


@login_required
def order_invoice_pdf(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    pdf_bytes = render_order_invoice_pdf(order=order, title="Invoice")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{order.id}.pdf"'
    return response


@login_required
def manual_invoice(request):
    """Return an editable HTML invoice template for staff to manually issue invoices."""
    if not request.user.is_staff:
        raise Http404

    company_name = getattr(settings, "SITE_NAME", "ط§ط³طھغŒط±ط§")
    address = (getattr(settings, "COMPANY_ADDRESS", "") or "").strip()
    phone = (getattr(settings, "COMPANY_PHONE", "") or "").strip()
    email = (getattr(settings, "COMPANY_EMAIL", "") or "").strip()
    if not email:
        email = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()

    company_address_lines = [ln.strip() for ln in address.splitlines() if ln.strip()]
    company_contact = " | ".join([p for p in [phone, email] if p])

    now = timezone.now()
    issue_date = format_jalali(now, "Y/m/d")
    due_date = format_jalali(now + timedelta(days=1), "Y/m/d")

    shipping_settings = ShippingSettings.get_solo()
    shipping_fee_per_item = int(shipping_settings.shipping_fee or 0)
    free_shipping_min_total = int(shipping_settings.free_shipping_min_total or 0)

    products = list(Product.objects.order_by("name").values("id", "name", "price"))

    raw_invoice_number = (request.GET.get("invoice_number") or "").strip()
    invoice_number = "#000000"
    match = re.fullmatch(r"#?(\d{1,12})", raw_invoice_number)
    if match:
        digits = match.group(1).lstrip("0") or "0"
        if digits != "0":
            invoice_number = f"#{int(match.group(1)):06d}"

    if invoice_number == "#000000":
        try:
            with transaction.atomic():
                seq, _created = ManualInvoiceSequence.objects.select_for_update().get_or_create(
                    pk=1,
                    defaults={"last_number": 0},
                )
                seq.last_number = int(seq.last_number or 0) + 1
                seq.save(update_fields=["last_number", "updated_at"])
                invoice_number = f"#{seq.last_number:06d}"
        except Exception:
            invoice_number = "#000000"

    response = render(
        request,
        "store/manual_invoice.html",
        {
            "company_name": company_name,
            "company_address_lines": company_address_lines,
            "company_contact": company_contact,
            "issue_date": issue_date,
            "due_date": due_date,
            "invoice_number": invoice_number,
            "shipping_fee_per_item": shipping_fee_per_item,
            "free_shipping_min_total": free_shipping_min_total,
            "products": products,
        },
    )
    if request.GET.get("download") == "1":
        response["Content-Disposition"] = 'attachment; filename="styra-invoice-template.html"'
    return response


@require_POST
def manual_invoice_pdf(request):
    """Generate a clean PDF for the manual invoice builder (avoids browser headers/footers)."""
    if not request.user.is_staff:
        raise Http404

    try:
        payload = json.loads((request.body or b"").decode("utf-8"))
    except Exception:
        return JsonResponse({"detail": "invalid payload"}, status=400)

    invoice_number = str(payload.get("invoice_number") or "").strip() or "#000000"
    title = str(payload.get("title") or "").strip() or "ظ¾غŒط´â€Œظپط§ع©طھظˆط±"
    issue_date = str(payload.get("issue_date") or "").strip()
    due_date = str(payload.get("due_date") or "").strip()

    buyer_lines = payload.get("buyer_lines") or []
    if not isinstance(buyer_lines, list):
        buyer_lines = []
    buyer_lines = [str(x).strip() for x in buyer_lines if str(x).strip()]

    items_in = payload.get("items") or []
    if not isinstance(items_in, list):
        items_in = []
    items: list[dict] = []
    for it in items_in:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        desc = str(it.get("desc") or "").strip()
        try:
            qty = int(it.get("qty") or 0)
        except Exception:
            qty = 0
        try:
            price = int(it.get("price") or 0)
        except Exception:
            price = 0

        if not name and not desc and qty <= 0 and price <= 0:
            continue
        if qty <= 0:
            qty = 1
        if price < 0:
            price = 0
        items.append({"name": name, "desc": desc, "qty": qty, "price": price})

    def _safe_int(value, default=0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    items_subtotal = _safe_int(payload.get("items_subtotal"), 0)
    discount = _safe_int(payload.get("discount"), 0)
    shipping = _safe_int(payload.get("shipping"), 0)
    grand_total = _safe_int(payload.get("grand_total"), max(0, items_subtotal - max(0, discount)) + max(0, shipping))

    pdf_bytes = render_manual_invoice_pdf(
        invoice_number=invoice_number,
        title=title,
        issue_date=issue_date,
        due_date=due_date,
        buyer_lines=buyer_lines,
        items=items,
        items_subtotal=items_subtotal,
        discount=discount,
        shipping=shipping,
        grand_total=grand_total,
    )

    safe_filename_digits = re.sub(r"\D", "", invoice_number)
    filename = safe_filename_digits.zfill(6) if safe_filename_digits else "manual-invoice"

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response


@require_GET
def cart_preview(request):
    items, total = _build_cart_preview_data(request)
    return JsonResponse({'items': items, 'total': total})


def _build_cart_preview_data(request) -> tuple[list[dict], int]:
    if request.user.is_authenticated:
        _merge_session_cart_into_user(request)
        cart_items = list(CartItem.objects.filter(user=request.user).select_related('product'))
        items: list[dict] = []
        total = 0
        for item in cart_items:
            item_total = int(item.total_price())
            items.append({
                'id': item.product_id,
                'name': item.product.name,
                'quantity': int(item.quantity),
                'unit_price': int(item.product.price),
                'total_price': item_total,
            })
            total += item_total
        return items, total

    session_cart = _get_session_cart(request)
    products = list(Product.objects.filter(id__in=list(session_cart.keys())))
    products_by_id = {str(p.id): p for p in products}
    items: list[dict] = []
    total = 0
    for product_id, quantity in session_cart.items():
        product = products_by_id.get(product_id)
        if not product:
            continue
        item_total = int(product.price) * int(quantity)
        items.append({
            'id': int(product_id),
            'name': product.name,
            'quantity': int(quantity),
            'unit_price': int(product.price),
            'total_price': item_total,
        })
        total += item_total
    return items, total


@require_POST
def cart_remove(request):
    raw_product_id = (request.POST.get('product_id') or '').strip()
    try:
        product_id = int(raw_product_id)
    except (TypeError, ValueError):
        product_id = 0

    if product_id <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            items, total = _build_cart_preview_data(request)
            return JsonResponse({'ok': False, 'message': 'ط¢غŒطھظ… ظ†ط§ظ…ط¹طھط¨ط± ط§ط³طھ.', 'items': items, 'total': total}, status=400)
        return redirect(reverse('cart'))

    if request.user.is_authenticated:
        _merge_session_cart_into_user(request)
        CartItem.objects.filter(user=request.user, product_id=product_id).delete()
    else:
        cart = _get_session_cart(request)
        cart.pop(str(product_id), None)
        _set_session_cart(request, cart)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        items, total = _build_cart_preview_data(request)
        return JsonResponse({'ok': True, 'items': items, 'total': total})

    next_url = _safe_next_url(request, request.POST.get('next')) or reverse('cart')
    return redirect(next_url)

def add_to_compare(request, pk):
    ids = _get_compare_list(request)
    pk = int(pk)
    if pk not in ids:
        ids.append(pk)
    _save_compare_list(request, ids)
    return redirect('compare')


def remove_from_compare(request, pk):
    ids = _get_compare_list(request)
    pk = int(pk)
    if pk in ids:
        ids.remove(pk)
    _save_compare_list(request, ids)
    return redirect('compare')


def compare(request):
    ids = _get_compare_list(request)
    products_qs = Product.objects.filter(id__in=ids).select_related('category').prefetch_related('features')
    products = list(products_qs)

    # ظ…ط±طھط¨â€Œط³ط§ط²غŒ ط¨ط± ط§ط³ط§ط³ طھط±طھغŒط¨ ط§ظ†طھط®ط§ط¨ ط¯ط± ط³ط´ظ†
    products.sort(key=lambda p: ids.index(p.id))

    # ط¬ظ…ط¹â€Œع©ط±ط¯ظ† ظ‡ظ…ظ‡ ظ†ط§ظ… ظˆغŒعکع¯غŒâ€Œظ‡ط§
    feature_names = set()
    for p in products:
        for f in p.features.all():
            feature_names.add(f.name)
    feature_names = sorted(feature_names)

    # ط³ط§ط®طھ ط±ط¯غŒظپâ€Œظ‡ط§غŒ ط¬ط¯ظˆظ„ ط¨ط±ط§غŒ طھظ…ظ¾ظ„غŒطھ
    rows = []

    # ط±ط¯غŒظپâ€Œظ‡ط§غŒ ظ¾ط§غŒظ‡
    rows.append({
        "label": "ظ‚غŒظ…طھ",
        "values": [f"{format_money(p.price)} طھظˆظ…ط§ظ†" for p in products],
    })
    rows.append({
        "label": "ط¨ط±ظ†ط¯",
        "values": [p.brand or "-" for p in products],
    })
    rows.append({
        "label": "ط¯ط³طھظ‡â€Œط¨ظ†ط¯غŒ",
        "values": [p.category.name for p in products],
    })
    rows.append({
        "label": "ط¨ط±ع†ط³ط¨â€Œظ‡ط§",
        "values": [p.tags or "-" for p in products],
    })

    # ط±ط¯غŒظپâ€Œظ‡ط§غŒ ظˆغŒعکع¯غŒâ€Œظ‡ط§غŒ ظپظ†غŒ
    for fname in feature_names:
        row_vals = []
        for p in products:
            feat = p.features.filter(name=fname).first()
            row_vals.append(feat.value if feat else "-")
        rows.append({
            "label": fname,
            "values": row_vals,
        })

    # ط¯ط§ط¯ظ‡â€Œظ‡ط§غŒ ظ„غŒط³طھ ط§ظ†طھط®ط§ط¨ ظ…ط­طµظˆظ„ (ظ¾ط§ظ¾â€Œط¢ظ¾)
    all_products = Product.objects.all().select_related('category')

    if products:
        cat_ids = {p.category_id for p in products}
        related_products = list(
            all_products.filter(category_id__in=cat_ids)
                        .exclude(id__in=ids)
                        .distinct()
        )
        related_ids = {p.id for p in related_products}
        other_products = list(
            all_products.exclude(id__in=ids)
                        .exclude(id__in=related_ids)
        )
    else:
        related_products = []
        other_products = list(all_products)

    return render(request, 'store/compare.html', {
        'products': products,
        'rows': rows,
        'related_products': related_products,
        'other_products': other_products,
    })










