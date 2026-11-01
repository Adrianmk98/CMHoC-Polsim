from django.urls import path
from . import views

app_name = 'chirps'

urlpatterns = [
    path('', views.chirp_feed, name='feed'),
    path('user/<str:username>/', views.chirps_by_user, name='by_user'),
    path('<int:pk>/delete/', views.chirp_delete, name='delete'),
]
