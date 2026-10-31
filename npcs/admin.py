from django.contrib import admin

from .models import NPCProfile


@admin.register(NPCProfile)
class NPCProfileAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'is_active', 'reply_chance', 'cooldown_minutes', 'last_posted_at')
    list_filter = ('is_active',)
    search_fields = ('user_profile__user__username', 'persona')
