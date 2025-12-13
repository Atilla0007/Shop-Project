
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('otp_email.urls')),
    path('', include('core.urls')),
    path('shop/', include('store.urls')),
    path('', include('accounts.urls')),
]
