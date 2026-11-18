from django.contrib import admin
from .models import ModeratorProfile, AuditLog


@admin.register(ModeratorProfile)
class ModeratorProfileAdmin(admin.ModelAdmin):
    """Granting/editing moderator permissions is staff-only by virtue of living here -
    there is no equivalent page in the moderator-facing tools."""
    list_display = [
        'user', 'is_moderator', 'can_manage_elections', 'can_manage_cabinet',
        'can_manage_bills', 'can_manage_users', 'can_manage_scores', 'can_manage_parties',
        'granted_by', 'granted_at',
    ]
    list_filter = ['is_moderator', 'can_manage_elections', 'can_manage_cabinet', 'can_manage_bills']
    search_fields = ['user__username']
    autocomplete_fields = ['user', 'granted_by']
    readonly_fields = ['granted_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        if not obj.granted_by_id:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: audit entries are written by the moderator tools, never by hand."""
    list_display = ['timestamp', 'actor', 'action', 'target_type', 'target_id', 'target_repr', 'view_name']
    list_filter = ['action', 'target_type']
    search_fields = ['actor__username', 'target_type', 'target_repr', 'view_name']
    date_hierarchy = 'timestamp'
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
