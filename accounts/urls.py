from django.urls import path
from . import views
from otp_sms import views as sms_views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('verify-phone/', sms_views.verify_page, name='verify_phone'),
    path('auth/phone-otp/', sms_views.verify_page, name='phone_otp_verify_page'),
]
