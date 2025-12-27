from django.contrib import admin
from .models import PoliticalParty, UserProfile, ForumCategory, Thread, Post, Flair, PositionHistory, PartyHistory, Riding, Cabinet, CabinetPosition


@admin.register(Riding)
class RidingAdmin(admin.ModelAdmin):
    list_display = ['name', 'province', 'population', 'is_active', 'current_mp']
    list_filter = ['province', 'is_active']
    search_fields = ['name', 'province']  # Required for autocomplete
    ordering = ['province', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'province', 'is_active')
        }),
        ('Details', {
            'fields': ('population', 'description')
        }),
    )
    
    def current_mp(self, obj):
        mp = obj.current_mp()
        if mp:
            return f"{mp.username}"
        return "-"
    current_mp.short_description = 'Current MP'


@admin.register(Flair)
class FlairAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'category']
    list_filter = ['category']
    search_fields = ['name']


@admin.register(PoliticalParty)
class PoliticalPartyAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    search_fields = ['name']


class PositionHistoryInline(admin.TabularInline):
    model = PositionHistory
    extra = 1
    fields = ['position_type', 'position_title', 'riding_obj', 'start_date', 'end_date', 'notes']
    autocomplete_fields = ['riding_obj']


class PartyHistoryInline(admin.TabularInline):
    model = PartyHistory
    extra = 1
    fields = ['party', 'start_date', 'end_date', 'reason', 'notes']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'party', 'get_riding', 'role']
    list_filter = ['party']
    search_fields = ['user__username', 'riding__name', 'role']
    inlines = [PositionHistoryInline, PartyHistoryInline]
    autocomplete_fields = ['riding']
    
    def get_riding(self, obj):
        return obj.get_riding_display() or "-"
    get_riding.short_description = 'Riding'


@admin.register(PositionHistory)
class PositionHistoryAdmin(admin.ModelAdmin):
    list_display = ['user_profile', 'position_title', 'position_type', 'get_riding', 'start_date', 'end_date', 'is_current']
    list_filter = ['position_type', 'start_date']
    search_fields = ['user_profile__user__username', 'position_title', 'riding_obj__name']
    date_hierarchy = 'start_date'
    autocomplete_fields = ['riding_obj']
    
    def get_riding(self, obj):
        return obj.get_riding_display() or "-"
    get_riding.short_description = 'Riding'
    
    def is_current(self, obj):
        return obj.is_current()
    is_current.boolean = True
    is_current.short_description = 'Current Position'


@admin.register(PartyHistory)
class PartyHistoryAdmin(admin.ModelAdmin):
    list_display = ['user_profile', 'party', 'start_date', 'end_date', 'reason', 'is_current']
    list_filter = ['party', 'start_date']
    search_fields = ['user_profile__user__username', 'reason']
    date_hierarchy = 'start_date'
    
    def is_current(self, obj):
        return obj.is_current()
    is_current.boolean = True
    is_current.short_description = 'Current Party'


class CabinetPositionInline(admin.TabularInline):
    model = CabinetPosition
    extra = 1
    fields = ['position_type', 'portfolio', 'title', 'user_profile', 'order', 'start_date', 'end_date']
    autocomplete_fields = ['user_profile']


@admin.register(Cabinet)
class CabinetAdmin(admin.ModelAdmin):
    list_display = ['name', 'prime_minister', 'government_party', 'start_date', 'end_date', 'is_current', 'member_count']
    list_filter = ['is_current', 'government_party', 'start_date']
    search_fields = ['name', 'prime_minister__username']
    date_hierarchy = 'start_date'
    inlines = [CabinetPositionInline]
    
    def member_count(self, obj):
        return obj.member_count()
    member_count.short_description = 'Members'


@admin.register(CabinetPosition)
class CabinetPositionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user_profile', 'cabinet', 'portfolio', 'position_type', 'start_date', 'end_date', 'is_current']
    list_filter = ['position_type', 'cabinet', 'start_date']
    search_fields = ['title', 'portfolio', 'user_profile__user__username']
    date_hierarchy = 'start_date'
    autocomplete_fields = ['user_profile']
    
    def is_current(self, obj):
        return obj.is_current()
    is_current.boolean = True
    is_current.short_description = 'Current'


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'created_at']
    list_editable = ['order']
    ordering = ['order']


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'flair', 'author', 'created_at', 'is_pinned', 'is_locked', 'views']
    list_filter = ['category', 'flair', 'is_pinned', 'is_locked', 'created_at']
    search_fields = ['title', 'author__username']
    date_hierarchy = 'created_at'


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['thread', 'author', 'created_at', 'is_edited']
    list_filter = ['created_at', 'is_edited']
    search_fields = ['content', 'author__username', 'thread__title']
    date_hierarchy = 'created_at'