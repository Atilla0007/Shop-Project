
from django.urls import path
from . import views

urlpatterns = [
    path('', views.shop, name='shop'),
    path('suggest/', views.shop_suggest, name='shop_suggest'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart, name='cart'),
    path('cart/preview/', views.cart_preview, name='cart_preview'),
    path('cart/remove/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/discount-preview/', views.discount_preview, name='discount_preview'),
    path('payment/<int:order_id>/', views.payment, name='payment'),
    path('payment/<int:order_id>/card-to-card/', views.payment_card_to_card, name='payment_card_to_card'),
    path('payment/<int:order_id>/contact-admin/', views.payment_contact_admin, name='payment_contact_admin'),
    path('payment/<int:order_id>/invoice-email/', views.payment_invoice_email, name='payment_invoice_email'),
    path('payment/<int:order_id>/proforma.pdf', views.proforma_pdf, name='proforma_pdf'),
    path('payment/<int:order_id>/invoice.pdf', views.order_invoice_pdf, name='order_invoice_pdf'),
    path('invoice/manual/', views.manual_invoice, name='manual_invoice'),
    path('invoice/manual/pdf/', views.manual_invoice_pdf, name='manual_invoice_pdf'),
    path('compare/', views.compare, name='compare'),
    path('compare/add/<int:pk>/', views.add_to_compare, name='add_to_compare'),
    path('compare/remove/<int:pk>/', views.remove_from_compare, name='remove_from_compare'),
]
