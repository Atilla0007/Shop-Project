
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from .models import Product, CartItem, Order, OrderItem, Category
from accounts.models import UserProfile
from core.models import ShippingSettings


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

    category_id = request.GET.get('category')
    domain = request.GET.get('domain')

    if category_id:
        products = products.filter(category_id=category_id)
    if domain:
        products = products.filter(domain__icontains=domain)

    return render(request, 'store/shop.html', {
        'products': products,
        'categories': categories,
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
    if request.user.is_authenticated:
        _merge_session_cart_into_user(request)
        item, created = CartItem.objects.get_or_create(user=request.user, product=product)
        if not created:
            item.quantity += 1
            item.save(update_fields=['quantity'])
    else:
        _add_to_session_cart(request, product.id, 1)

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
def checkout(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.email_verified:
        verify_url = reverse("email_otp_verify_page")
        return redirect(f"{verify_url}?next={quote(request.get_full_path())}")

    _merge_session_cart_into_user(request)
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')
    subtotal = sum(item.total_price() for item in cart_items)

    shipping_settings = ShippingSettings.get_solo()
    shipping_fee = int(shipping_settings.shipping_fee or 0)
    free_shipping_min_total = int(shipping_settings.free_shipping_min_total or 0)

    def normalize_digits(value: str) -> str:
        if not value:
            return value
        return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

    def compute_shipping(province_value: str | None) -> tuple[int, bool, bool]:
        province_selected = bool((province_value or "").strip())
        if not province_selected:
            return 0, False, False
        is_free = bool(free_shipping_min_total) and subtotal >= free_shipping_min_total
        applied_fee = 0 if is_free else shipping_fee
        return applied_fee, True, is_free

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
        }

        errors: dict[str, str] = {}
        if not values['first_name']:
            errors['first_name'] = 'نام را وارد کنید.'
        if not values['last_name']:
            errors['last_name'] = 'نام خانوادگی را وارد کنید.'
        if not values['phone']:
            errors['phone'] = 'شماره موبایل را وارد کنید.'

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

        if not errors:
            if values['first_name'] != (request.user.first_name or ''):
                request.user.first_name = values['first_name']
            if values['last_name'] != (request.user.last_name or ''):
                request.user.last_name = values['last_name']
            request.user.save(update_fields=['first_name', 'last_name'])

        shipping_applied, shipping_applicable, shipping_is_free = compute_shipping(values['province'])
        total_payable = int(subtotal) + int(shipping_applied)

        if not cart_items.exists():
            errors['cart'] = 'سبد خرید شما خالی است.'

        if errors:
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'subtotal': subtotal,
                'shipping_fee': shipping_fee,
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
            status='paid'
        )
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.product.price,
            )
        cart_items.delete()
        return render(request, 'store/checkout_success.html', {
            'order': order,
            'subtotal': subtotal,
            'shipping_fee': shipping_fee,
            'shipping_applicable': shipping_applicable,
            'shipping_is_free': shipping_is_free,
            'shipping_applied': shipping_applied,
            'total_payable': total_payable,
        })

    values = {
        'first_name': (request.user.first_name or '').strip(),
        'last_name': (request.user.last_name or '').strip(),
        'phone': (profile.phone or '').strip(),
        'email': (request.user.email or '').strip(),
        'province': '',
        'city': '',
        'address': '',
        'note': '',
    }
    shipping_applied, shipping_applicable, shipping_is_free = compute_shipping(values['province'])
    total_payable = int(subtotal) + int(shipping_applied)

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_fee': shipping_fee,
        'free_shipping_min_total': free_shipping_min_total,
        'shipping_applicable': shipping_applicable,
        'shipping_is_free': shipping_is_free,
        'shipping_applied': shipping_applied,
        'total_payable': total_payable,
        'values': values,
        'errors': {},
        'show_phone_verify_modal': bool(values['phone'] and not profile.phone_verified),
    })


@require_GET
def cart_preview(request):
    if request.user.is_authenticated:
        _merge_session_cart_into_user(request)
        cart_items = list(CartItem.objects.filter(user=request.user).select_related('product'))
        items = []
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
        return JsonResponse({'items': items, 'total': total})

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
        items.append({
            'id': int(product_id),
            'name': product.name,
            'quantity': int(quantity),
            'unit_price': int(product.price),
            'total_price': item_total,
        })
        total += item_total
    return JsonResponse({'items': items, 'total': total})

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
        "values": [f"{p.price:,.0f} تومان" for p in products],
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
