from django.contrib import admin
from .models import (
    Party, PartyMembership, PartyRole, LeadershipElection,
    LeadershipCandidate, LeadershipVote, ConfidenceVote,
    ConfidenceBallot, JoinRequest
)


class PartyMembershipInline(admin.TabularInline):
    model = PartyMembership
    extra = 0
    fields = ['user', 'joined_at', 'is_active', 'is_founding_member']
    readonly_fields = ['joined_at']


class PartyRoleInline(admin.TabularInline):
    model = PartyRole
    extra = 0
    fields = ['user', 'role', 'appointed_at', 'is_active']
    readonly_fields = ['appointed_at']


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'ideology', 'leader', 'member_count', 'is_active']
    list_filter = ['ideology', 'is_active', 'founded_date']
    search_fields = ['name', 'abbreviation']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'abbreviation', 'color', 'logo')
        }),
        ('Political Info', {
            'fields': ('ideology', 'platform')
        }),
        ('Leadership', {
            'fields': ('leader', 'press_secretary')
        }),
        ('Status', {
            'fields': ('founded_date', 'is_active', 'member_count')
        }),
    )
    
    readonly_fields = ['member_count']
    inlines = [PartyMembershipInline, PartyRoleInline]


@admin.register(PartyMembership)
class PartyMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'party', 'joined_at', 'is_active', 'is_founding_member']
    list_filter = ['is_active', 'is_founding_member', 'party']
    search_fields = ['user__username', 'party__name']
    date_hierarchy = 'joined_at'


@admin.register(PartyRole)
class PartyRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'party', 'role', 'appointed_at', 'is_active']
    list_filter = ['role', 'is_active', 'party']
    search_fields = ['user__username', 'party__name']
    date_hierarchy = 'appointed_at'


class LeadershipCandidateInline(admin.TabularInline):
    model = LeadershipCandidate
    extra = 0
    fields = ['user', 'platform', 'nominated_at', 'is_approved', 'withdrawn']
    readonly_fields = ['nominated_at']


@admin.register(LeadershipElection)
class LeadershipElectionAdmin(admin.ModelAdmin):
    list_display = ['party', 'trigger', 'opens_at', 'closes_at', 'is_active', 'winner']
    list_filter = ['trigger', 'is_active', 'is_completed', 'party']
    search_fields = ['party__name', 'title']
    date_hierarchy = 'created_at'
    
    inlines = [LeadershipCandidateInline]


@admin.register(LeadershipCandidate)
class LeadershipCandidateAdmin(admin.ModelAdmin):
    list_display = ['user', 'election', 'nominated_at', 'is_approved', 'withdrawn']
    list_filter = ['is_approved', 'withdrawn', 'election__party']
    search_fields = ['user__username', 'election__party__name']


@admin.register(LeadershipVote)
class LeadershipVoteAdmin(admin.ModelAdmin):
    list_display = ['voter', 'candidate', 'election', 'voted_at']
    list_filter = ['election__party', 'voted_at']
    search_fields = ['voter__username', 'candidate__user__username']


@admin.register(ConfidenceVote)
class ConfidenceVoteAdmin(admin.ModelAdmin):
    list_display = ['party', 'target_leader', 'initiated_by', 'initiated_at', 'is_active', 'result']
    list_filter = ['is_active', 'is_completed', 'result', 'party']
    search_fields = ['party__name', 'target_leader__username']
    date_hierarchy = 'initiated_at'


@admin.register(ConfidenceBallot)
class ConfidenceBallotAdmin(admin.ModelAdmin):
    list_display = ['voter', 'confidence_vote', 'vote', 'voted_at']
    list_filter = ['vote', 'voted_at']
    search_fields = ['voter__username']


@admin.register(JoinRequest)
class JoinRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'party', 'status', 'requested_at', 'reviewed_by']
    list_filter = ['status', 'party']
    search_fields = ['user__username', 'party__name']
    date_hierarchy = 'requested_at'
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        for join_request in queryset.filter(status='PENDING'):
            join_request.approve(request.user)
        self.message_user(request, f'{queryset.count()} requests approved.')
    approve_requests.short_description = 'Approve selected requests'
    
    def reject_requests(self, request, queryset):
        for join_request in queryset.filter(status='PENDING'):
            join_request.reject(request.user)
        self.message_user(request, f'{queryset.count()} requests rejected.')
    reject_requests.short_description = 'Reject selected requests'