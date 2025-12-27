from django.contrib import admin
from .models import Election, RidingElectionResult, CandidateResult


class CandidateResultInline(admin.TabularInline):
    model = CandidateResult
    extra = 1
    fields = ['candidate', 'party', 'votes', 'vote_percentage', 'is_winner', 'is_incumbent']
    autocomplete_fields = ['candidate']


class RidingElectionResultInline(admin.TabularInline):
    model = RidingElectionResult
    extra = 0
    fields = ['riding', 'winner', 'winning_party', 'total_votes_cast', 'is_acclaimed']
    autocomplete_fields = ['riding', 'winner']
    readonly_fields = ['turnout_percentage']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('riding', 'winner', 'winning_party')


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'election_type', 'election_date', 'is_completed', 'total_seats', 'voter_turnout']
    list_filter = ['election_type', 'is_completed', 'election_date']
    search_fields = ['name', 'description']
    date_hierarchy = 'election_date'
    inlines = [RidingElectionResultInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'election_type', 'election_date', 'description', 'is_completed')
        }),
        ('By-Election Only', {
            'fields': ('riding',),
            'classes': ('collapse',),
        }),
        ('Statistics', {
            'fields': ('total_seats', 'total_votes_cast', 'total_registered_voters', 'voter_turnout'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['calculate_election_totals']
    
    def calculate_election_totals(self, request, queryset):
        for election in queryset:
            election.calculate_totals()
        self.message_user(request, f"Calculated totals for {queryset.count()} election(s)")
    calculate_election_totals.short_description = "Calculate election totals"


@admin.register(RidingElectionResult)
class RidingElectionResultAdmin(admin.ModelAdmin):
    list_display = ['riding', 'election', 'winner', 'winning_party', 'total_votes_cast', 'turnout_percentage']
    list_filter = ['election', 'winning_party', 'is_acclaimed']
    search_fields = ['riding__name', 'winner__user__username']
    autocomplete_fields = ['riding', 'winner', 'winning_party', 'previous_winner', 'previous_party']
    inlines = [CandidateResultInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('election', 'riding')
        }),
        ('Results', {
            'fields': ('winner', 'winning_party', 'is_acclaimed')
        }),
        ('Vote Totals', {
            'fields': ('total_votes_cast', 'total_registered_voters', 'turnout_percentage')
        }),
        ('Historical Comparison', {
            'fields': ('previous_winner', 'previous_party'),
            'classes': ('collapse',),
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('riding', 'election', 'winner', 'winning_party')


@admin.register(CandidateResult)
class CandidateResultAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'party', 'riding_result', 'votes', 'vote_percentage', 'is_winner']
    list_filter = ['party', 'is_winner', 'is_incumbent']
    search_fields = ['candidate__user__username', 'riding_result__riding__name']
    autocomplete_fields = ['candidate']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('candidate__user', 'party', 'riding_result__riding', 'riding_result__election')