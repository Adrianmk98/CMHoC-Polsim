from django.urls import path
from . import views

app_name = 'press'

urlpatterns = [
    # Public views
    path('', views.press_list, name='list'),
    path('create/', views.press_create, name='create'),
    path('my-releases/', views.my_press_releases, name='my_releases'),
    path('party/<int:party_id>/', views.press_by_party, name='by_party'),
    path('author/<str:username>/', views.press_by_author, name='by_author'),
    
    # Image upload (AJAX)
    path('upload-image/', views.upload_image, name='upload_image'),
    
    # Press release CRUD
    path('<int:pk>/', views.press_detail, name='detail'),
    path('<int:pk>/edit/', views.press_edit, name='edit'),
    path('<int:pk>/delete/', views.press_delete, name='delete'),
]