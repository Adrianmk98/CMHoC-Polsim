from django.urls import path
from . import views

app_name = 'voting'

urlpatterns = [
    path('bills/', views.bill_list, name='bill_list'),
    path('bill/<int:bill_id>/', views.bill_detail, name='bill_detail'),
    path('bill/create/', views.create_bill, name='create_bill'),
    path('vote/<int:vote_id>/cast/', views.cast_vote, name='cast_vote'),
    path('vote/<int:vote_id>/results/', views.vote_results, name='vote_results'),
    path('bill/<int:bill_id>/create-vote/', views.create_vote, name='create_vote'),
    path('bill/<int:bill_id>/debate/', views.add_debate_post, name='add_debate_post'),
]