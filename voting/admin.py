from django.contrib import admin
from .models import Bill, Vote, Ballot, PlayerHistory


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['bill_number', 'title', 'sponsor', 'chamber', 'status', 'created_at']
    list_filter = ['chamber', 'status', 'created_at']
    search_fields = ['bill_number', 'title', 'sponsor__username']
    date_hierarchy = 'created_at'


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['bill', 'vote_type', 'opened_at', 'closes_at', 'is_active', 'result']
    list_filter = ['vote_type', 'is_active', 'opened_at']
    search_fields = ['bill__bill_number', 'bill__title']
    date_hierarchy = 'opened_at'


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    list_display = ['voter', 'vote_session', 'vote', 'cast_at']
    list_filter = ['vote', 'cast_at']
    search_fields = ['voter__username', 'vote_session__bill__bill_number']
    date_hierarchy = 'cast_at'


@admin.register(PlayerHistory)
class PlayerHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_votes', 'bills_sponsored', 'participation_rate', 'last_updated']
    search_fields = ['user__username']
    readonly_fields = ['last_updated']