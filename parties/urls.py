from django.urls import path
from . import views

app_name = 'parties'

urlpatterns = [
    # Party CRUD
    path('', views.party_list, name='party_list'),
    path('create/', views.create_party, name='create'),
    path('<int:pk>/', views.party_detail, name='detail'),
    
    # Membership
    path('<int:pk>/join/', views.join_party, name='join'),
    path('<int:pk>/leave/', views.leave_party, name='leave'),
    path('<int:pk>/requests/', views.manage_join_requests, name='manage_requests'),
    path('request/<int:pk>/approve/', views.approve_join_request, name='approve_request'),
    path('request/<int:pk>/reject/', views.reject_join_request, name='reject_request'),
    
    # Leadership Elections
    path('election/<int:pk>/', views.leadership_election_detail, name='election_detail'),
    path('election/<int:election_id>/nominate/', views.nominate_for_leadership, name='nominate'),
    path('election/<int:election_id>/vote/<int:candidate_id>/', views.vote_in_election, name='vote'),
    path('election/<int:pk>/close/', views.close_election, name='close_election'),
    
    # Confidence Votes
    path('<int:pk>/confidence/', views.initiate_confidence_vote, name='initiate_confidence'),
    path('confidence/<int:pk>/', views.confidence_vote_detail, name='confidence_vote_detail'),
    path('confidence/<int:pk>/vote/<str:vote>/', views.cast_confidence_vote, name='cast_confidence_vote'),
    path('confidence/<int:pk>/close/', views.close_confidence_vote, name='close_confidence_vote'),
]