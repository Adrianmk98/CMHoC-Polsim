# forum/urls.py - UPDATE YOUR EXISTING FILE

from django.urls import path
from . import views

urlpatterns = [
    path('login', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    path('register', views.register, name='register'),
    # NEW: Homepage with press focus
    path('', views.index, name='index'),
    
    # NEW: Forum categories page
    path('forum/', views.forum_categories, name='forum_categories'),
    path('forum/index/', views.forum_index, name='forum_index'),  
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    
    # Existing URLs - keep these exactly as they are
    path('search/', views.search, name='search'),
    path('ridings/', views.riding_list, name='riding_list'),
    path('riding/<int:riding_id>/', views.riding_detail, name='riding_detail'),
    path('cabinet/', views.cabinet_list, name='cabinet_list'),
    path('cabinet/manage/', views.manage_cabinet, name='manage_cabinet'),
    path('cabinet/add-position/', views.add_cabinet_position, name='add_cabinet_position'),
    path('cabinet/position/<int:position_id>/edit/', views.edit_cabinet_position, name='edit_cabinet_position'),
    path('cabinet/position/<int:position_id>/remove/', views.remove_cabinet_position, name='remove_cabinet_position'),
    path('cabinet/<int:cabinet_id>/', views.cabinet_detail, name='cabinet_detail'),
    path('cabinet/portfolio/<str:portfolio>/', views.cabinet_position_history, name='portfolio_history'),
    path('thread/<int:thread_id>/', views.thread_detail, name='thread_detail'),
    path('category/<int:category_id>/new/', views.create_thread, name='create_thread'),
    path('user/<int:userid>/', views.user_profile, name='user_profile'),
]
