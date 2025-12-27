from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('notifications', views.notification_list, name='notification_list'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_as_read'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
    path('<int:notification_id>/delete/', views.delete_notification, name='delete_notification'),
    path('preferences/', views.notification_preferences, name='notification_preferences'),
    path('api/unread-count/', views.unread_count, name='unread_count'),
]