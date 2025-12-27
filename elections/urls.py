from django.urls import path
from . import views

app_name = 'elections'

urlpatterns = [
    path('', views.election_list, name='election_list'),
    path('<int:election_id>/', views.election_detail, name='election_detail'),
    path('result/<int:result_id>/', views.riding_result_detail, name='riding_result_detail'),
    path('riding/<int:riding_id>/history/', views.riding_election_history, name='riding_history'),
    path('compare/', views.compare_elections, name='compare_elections'),
    path('party/<int:party_id>/history/', views.party_election_history, name='party_history'),
]