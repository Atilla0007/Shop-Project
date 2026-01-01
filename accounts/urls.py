from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/addresses/save/', views.address_save, name='address_save'),
    path('profile/addresses/<int:address_id>/save/', views.address_save, name='address_update'),
    path('profile/addresses/<int:address_id>/delete/', views.address_delete, name='address_delete'),
    path('profile/addresses/<int:address_id>/default/', views.address_set_default, name='address_set_default'),
]
