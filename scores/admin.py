from django.contrib import admin
from .models import ParliamentSession, PlayerLT, ScoreEntry


@admin.register(ParliamentSession)
class ParliamentSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_active']
    list_filter = ['is_active']


@admin.register(PlayerLT)
class PlayerLTAdmin(admin.ModelAdmin):
    list_display = ['user', 'session', 'lt_score', 'is_active_persona']
    list_filter = ['session', 'is_active_persona']
    search_fields = ['user__username']


@admin.register(ScoreEntry)
class ScoreEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'session', 'score_type', 'score', 'description', 'created_by', 'created_at']
    list_filter = ['session', 'score_type']
    search_fields = ['user__username', 'description']
