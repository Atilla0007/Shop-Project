from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html'
    ), name='login'),

    # اینجا دیگه از LogoutView استفاده نمی‌کنیم
    path('logout/', views.logout_view, name='logout'),

    path('signup/', views.signup, name='signup'),
]
