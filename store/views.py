
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from .invoice import render_order_invoice_pdf
from .models import Product, CartItem, Order, OrderItem, Category
from accounts.models import UserProfile
from core.models import DiscountCode, ShippingSettings
from core.utils.formatting import format_money


SESSION_CART_KEY = 'cart'


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
    raw_qty = raw_qty.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
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
        return JsonResponse({'ok': False, 'message': 'ابتدا ایمیل خود را تایید کنید.'}, status=403)

    _merge_session_cart_into_user(request)
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')
    items_subtotal = int(sum(item.total_price() for item in cart_items))
    if not cart_items.exists():
        return JsonResponse({'ok': False, 'message': 'سبد خرید شما خالی است.'}, status=400)

    code = (request.POST.get('code') or '').strip().upper().replace(' ', '')
    if not code:
        return JsonResponse({
            'ok': True,
            'code': '',
            'percent': 0,
            'amount': 0,
            'items_subtotal': items_subtotal,
            'subtotal': items_subtotal,
            'message': 'کد تخفیف حذف شد.',
        })

    discount = (
        DiscountCode.objects.filter(code=code, is_active=True)
        .order_by('-updated_at')
        .first()
    )
    if not discount:
        return JsonResponse({'ok': False, 'message': 'کد تخفیف نامعتبر است.'})

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
        'message': f'کد {code} اعمال شد ({percent}٪).',
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

    def normalize_digits(value: str) -> str:
        if not value:
            return value
        return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

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
        }

        errors: dict[str, str] = {}
        if not values['first_name']:
            errors['first_name'] = 'نام را وارد کنید.'
        if not values['last_name']:
            errors['last_name'] = 'نام خانوادگی را وارد کنید.'
        if not values['phone']:
            errors['phone'] = 'شماره موبایل را وارد کنید.'
        if not values['province']:
            errors['province'] = 'استان را انتخاب کنید.'
        if not values['city']:
            errors['city'] = 'شهر را انتخاب کنید.'
        if not values['address']:
            errors['address'] = 'آدرس دقیق را وارد کنید.'

        if values['phone']:
            new_phone = values['phone'].replace(' ', '').replace('-', '')
            values['phone'] = new_phone
            if new_phone != (profile.phone or ''):
                profile.phone = new_phone
                profile.phone_verified = False
                profile.phone_verified_at = None
                profile.save(update_fields=['phone', 'phone_verified', 'phone_verified_at'])

        if values['phone'] and not profile.phone_verified:
            errors['phone_verified'] = 'شماره موبایل شما تایید نشده است.'

        discount_code = values.get('discount_code_applied') or ""
        if discount_code:
            discount = (
                DiscountCode.objects.filter(code=discount_code, is_active=True)
                .order_by('-updated_at')
                .first()
            )
            if not discount:
                errors['discount_code'] = 'کد تخفیف نامعتبر است.'
                discount_code = ""
            else:
                discount_percent = int(discount.percent)
                discount_amount = int(items_subtotal) * discount_percent // 100
                subtotal = int(items_subtotal) - int(discount_amount)

        if not errors:
            if values['first_name'] != (request.user.first_name or ''):
                request.user.first_name = values['first_name']
            if values['last_name'] != (request.user.last_name or ''):
                request.user.last_name = values['last_name']
            request.user.save(update_fields=['first_name', 'last_name'])

        shipping_applied, shipping_applicable, shipping_is_free, shipping_total_full = compute_shipping(
            values['province'],
            int(subtotal),
        )
        total_payable = int(subtotal) + int(shipping_applied)

        if not cart_items.exists():
            errors['cart'] = 'سبد خرید شما خالی است.'

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

        order = Order.objects.create(
            user=request.user,
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
        cart_items.delete()
        return redirect(reverse('payment', args=[order.id]))

    values = {
        'first_name': (request.user.first_name or '').strip(),
        'last_name': (request.user.last_name or '').strip(),
        'phone': (profile.phone or '').strip(),
        'email': (request.user.email or '').strip(),
        'province': '',
        'city': '',
        'address': '',
        'note': '',
        'discount_code': '',
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
    from store.emails import send_order_payment_submitted_email

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
            error = 'شماره کارت هنوز توسط ادمین تنظیم نشده است.'
        else:
            receipt = request.FILES.get('receipt')
            if not receipt:
                error = 'لطفاً تصویر فیش واریزی را بارگذاری کنید.'
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
                    try:
                        send_order_payment_submitted_email(order=order, request=request)
                    except Exception:
                        pass

                return redirect(f"{reverse('payment_card_to_card', args=[order.id])}?submitted=1")

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
    from store.emails import send_order_payment_submitted_email

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
            try:
                send_order_payment_submitted_email(order=order, request=request)
            except Exception:
                pass

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

    pdf_bytes = render_order_invoice_pdf(order=order, title="پیش‌فاکتور استیرا")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="proforma-{order.id}.pdf"'
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
            return JsonResponse({'ok': False, 'message': 'آیتم نامعتبر است.', 'items': items, 'total': total}, status=400)
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

    # مرتب‌سازی بر اساس ترتیب انتخاب در سشن
    products.sort(key=lambda p: ids.index(p.id))

    # جمع‌کردن همه نام ویژگی‌ها
    feature_names = set()
    for p in products:
        for f in p.features.all():
            feature_names.add(f.name)
    feature_names = sorted(feature_names)

    # ساخت ردیف‌های جدول برای تمپلیت
    rows = []

    # ردیف‌های پایه
    rows.append({
        "label": "قیمت",
        "values": [f"{format_money(p.price)} تومان" for p in products],
    })
    rows.append({
        "label": "برند",
        "values": [p.brand or "-" for p in products],
    })
    rows.append({
        "label": "دسته‌بندی",
        "values": [p.category.name for p in products],
    })
    rows.append({
        "label": "برچسب‌ها",
        "values": [p.tags or "-" for p in products],
    })

    # ردیف‌های ویژگی‌های فنی
    for fname in feature_names:
        row_vals = []
        for p in products:
            feat = p.features.filter(name=fname).first()
            row_vals.append(feat.value if feat else "-")
        rows.append({
            "label": fname,
            "values": row_vals,
        })

    # داده‌های لیست انتخاب محصول (پاپ‌آپ)
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
