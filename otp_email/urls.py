from django.urls import path

from . import views

urlpatterns = [
    path("auth/email-otp/", views.verify_page, name="email_otp_verify_page"),
    path("auth/email-otp/request/", views.request_otp, name="email_otp_request"),
    path("auth/email-otp/verify/", views.verify_otp, name="email_otp_verify"),
]
