from django.urls import path

from . import views

app_name = 'npcs'

urlpatterns = [
    path('<int:pk>/edit/', views.edit_npc, name='edit'),
]
