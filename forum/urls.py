# forum/urls.py - UPDATE YOUR EXISTING FILE

from django.urls import path
from . import views

urlpatterns = [
    path('login', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    path('register', views.register, name='register'),
    # NEW: Homepage with press focus
    path('', views.index, name='index'),

    # Existing URLs - keep these exactly as they are
    path('ridings/', views.riding_list, name='riding_list'),
    path('riding/<int:riding_id>/', views.riding_detail, name='riding_detail'),
    path('cabinet/', views.cabinet_list, name='cabinet_list'),
    path('cabinet/manage/', views.manage_cabinet, name='manage_cabinet'),
    path('cabinet/add-position/', views.add_cabinet_position, name='add_cabinet_position'),
    path('cabinet/position/<int:position_id>/edit/', views.edit_cabinet_position, name='edit_cabinet_position'),
    path('cabinet/position/<int:position_id>/remove/', views.remove_cabinet_position, name='remove_cabinet_position'),
    path('cabinet/<int:cabinet_id>/', views.cabinet_detail, name='cabinet_detail'),
    path('cabinet/portfolio/<str:portfolio>/', views.cabinet_position_history, name='portfolio_history'),
    path('user/<int:userid>/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]
