from django.urls import path
from . import views

app_name = 'moderator'

urlpatterns = [
    # Main dashboard
    path('', views.moderator_dashboard, name='dashboard'),
    
    # Debug
    path('debug/', views.debug_permissions, name='debug'),
    
    # Election management
    path('elections/', views.election_dashboard, name='election_dashboard'),
    path('elections/create/', views.create_election, name='create_election'),
    path('elections/<int:election_id>/results/', views.add_results, name='add_results'),
    path('elections/<int:election_id>/bulk-add/', views.bulk_add_results, name='bulk_add_results'),
    path('elections/result/<int:result_id>/candidates/', views.add_candidates, name='add_candidates'),
    path('elections/<int:election_id>/complete/', views.complete_election, name='complete_election'),
    
    # Cabinet management
    path('cabinet/', views.cabinet_dashboard, name='cabinet_dashboard'),
    
    # Bill management
    path('bills/', views.bill_dashboard, name='bill_dashboard'),
]