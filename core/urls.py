from django.urls import path, include
from . import views

urlpatterns = [
    # صفحه اصلی
    path('', views.home, name='home'),

    # صفحات عمومی
    path('contact/', views.contact, name='contact'),
    path('news/', views.news_list, name='news_list'),
    path('news/<int:pk>/', views.news_detail, name='news_detail'),
    path('faq/', views.faq, name='faq'),
    path('terms/', views.terms, name='terms'),

    # چت کاربر (ویجت و صفحه)
    path('chat/', views.chat, name='chat'),
    path('chat/messages/', views.chat_messages, name='chat_messages'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/bot/', views.chat_bot, name='chat_bot'),
    path('chat/stream/', views.chat_stream, name='chat_stream'),  # جدید - SSE

    # پنل چت ادمین
    path('admin-chat/', views.admin_chat, name='admin_chat'),
    path('admin-chat/<int:user_id>/', views.admin_chat, name='admin_chat_detail'),
    path('admin-chat/<int:user_id>/messages/', views.admin_chat_messages, name='admin_chat_messages'),
    path('admin-chat/<int:user_id>/send/', views.admin_chat_send, name='admin_chat_send'),
    path('admin-chat/<int:user_id>/stream/', views.admin_chat_stream, name='admin_chat_stream'),  # جدید - SSE
]
