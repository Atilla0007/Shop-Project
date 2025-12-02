
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Product, CartItem, Order, OrderItem, Category


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



@login_required
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.quantity += 1
        item.save()
    return redirect('cart')


@login_required
def cart(request):
    items = CartItem.objects.filter(user=request.user)
    total = sum(i.total_price() for i in items)
    return render(request, 'store/cart.html', {'items': items, 'total': total})


@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total_price() for item in cart_items)

    if request.method == 'POST':
        if cart_items.exists():
            order = Order.objects.create(
                user=request.user,
                total_price=total,
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
        return render(request, 'store/checkout_success.html', {'total': total})

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'total': total
    })


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
