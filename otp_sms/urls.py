from django.urls import path

from . import views

urlpatterns = [
    path("auth/sms-otp/", views.verify_page, name="sms_otp_verify_page"),
    path("auth/sms-otp/request/", views.request_otp, name="sms_otp_request"),
    path("auth/sms-otp/verify/", views.verify_otp, name="sms_otp_verify"),
]

