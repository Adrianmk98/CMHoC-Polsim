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
    path('cabinet/create/', views.mod_create_cabinet, name='mod_create_cabinet'),
    path('cabinet/<int:cabinet_id>/edit/', views.mod_edit_cabinet, name='mod_edit_cabinet'),
    path('cabinet/<int:cabinet_id>/add-position/', views.mod_add_position, name='mod_add_position'),
    path('cabinet/position/<int:position_id>/edit/', views.mod_edit_position, name='mod_edit_position'),
    path('cabinet/position/<int:position_id>/remove/', views.mod_remove_position, name='mod_remove_position'),

    # Bill management
    path('bills/', views.bill_dashboard, name='bill_dashboard'),

    # Score management (moderator-only polling calculator)
    path('scores/', views.scores_dashboard, name='scores_dashboard'),
    path('scores/session/create/', views.session_create, name='session_create'),
    path('scores/player/<int:user_id>/', views.player_scores, name='player_scores'),
    path('scores/player/<int:user_id>/lt/', views.update_lt, name='update_lt'),
    path('scores/player/<int:user_id>/add/', views.add_score_entry, name='add_score_entry'),
    path('scores/entry/<int:entry_id>/delete/', views.delete_score_entry, name='delete_score_entry'),
]