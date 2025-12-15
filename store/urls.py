
from django.urls import path
from . import views

urlpatterns = [
    path('', views.shop, name='shop'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart, name='cart'),
    path('cart/preview/', views.cart_preview, name='cart_preview'),
    path('cart/remove/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/discount-preview/', views.discount_preview, name='discount_preview'),
    path('payment/<int:order_id>/', views.payment, name='payment'),
    path('payment/<int:order_id>/proforma.pdf', views.proforma_pdf, name='proforma_pdf'),
    path('compare/', views.compare, name='compare'),
    path('compare/add/<int:pk>/', views.add_to_compare, name='add_to_compare'),
    path('compare/remove/<int:pk>/', views.remove_from_compare, name='remove_from_compare'),
]
