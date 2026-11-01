from django.contrib import admin
from .models import Chirp


@admin.register(Chirp)
class ChirpAdmin(admin.ModelAdmin):
    list_display = ('author', 'content', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('author__username', 'content')
