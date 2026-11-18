from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.contrib.admin import helpers
from django.template.response import TemplateResponse

from .models import (
    CandidateResult, Election, ElectionRegionSeats, NationalPoll, PartyModifier,
    RegionalListSeat, RegionalPoll, RidingElectionResult,
)
from .services import project_riding_result
from . import polling


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
    list_display = ['name', 'election_type', 'election_date', 'phase_display', 'is_completed', 'total_seats', 'voter_turnout']
    list_filter = ['election_type', 'is_completed', 'election_date']
    search_fields = ['name', 'description']
    date_hierarchy = 'election_date'
    inlines = [RidingElectionResultInline]
    readonly_fields = ['phase_display']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'election_type', 'election_date', 'description', 'is_completed', 'phase_display')
        }),
        ('Timeline', {
            'fields': ('writ_date', 'nomination_deadline', 'campaign_start_date', 'results_certified_date'),
            'classes': ('collapse',),
        }),
        ('By-Election Only', {
            'fields': ('riding',),
            'classes': ('collapse',),
        }),
        ('Statistics', {
            'fields': ('total_seats', 'total_votes_cast', 'total_registered_voters', 'voter_turnout'),
            'classes': ('collapse',),
        }),
        ('Polling Simulation', {
            'fields': ('uses_list_seats',),
            'classes': ('collapse',),
        }),
    )

    actions = [
        'calculate_election_totals',
        'run_compute_party_modifiers',
        'run_national_polling_action',
        'run_regional_polling_action',
        'run_apply_polling_to_ridings',
        'run_allocate_list_seats',
    ]

    def calculate_election_totals(self, request, queryset):
        for election in queryset:
            election.calculate_totals()
        self.message_user(request, f"Calculated totals for {queryset.count()} election(s)")
    calculate_election_totals.short_description = "Calculate election totals"

    def phase_display(self, obj):
        return obj.get_phase_display()
    phase_display.short_description = 'Phase'

    def run_compute_party_modifiers(self, request, queryset):
        for election in queryset:
            try:
                rows = polling.compute_party_modifiers(election)
                self.message_user(request, f"{election}: computed modifiers for {len(rows)} party/ies.")
            except ValueError as exc:
                self.message_user(request, f"{election}: {exc}", level='error')
    run_compute_party_modifiers.short_description = "1. Compute party modifiers"

    def run_national_polling_action(self, request, queryset):
        for election in queryset:
            try:
                polls = polling.run_national_polling(election)
                self.message_user(request, f"{election}: ran national polling for {len(polls)} party/ies.")
            except ValueError as exc:
                self.message_user(request, f"{election}: {exc}", level='error')
    run_national_polling_action.short_description = "2. Run national polling"

    def run_regional_polling_action(self, request, queryset):
        for election in queryset:
            try:
                polls = polling.run_regional_polling(election)
                self.message_user(request, f"{election}: wrote {len(polls)} regional poll row(s).")
            except ValueError as exc:
                self.message_user(request, f"{election}: {exc}", level='error')
    run_regional_polling_action.short_description = "3. Run regional polling"

    def run_apply_polling_to_ridings(self, request, queryset):
        for election in queryset:
            try:
                result = polling.apply_polling_to_ridings(election)
                self.message_user(
                    request,
                    f"{election}: updated {result['updated']} riding(s), skipped {result['skipped']}."
                )
            except ValueError as exc:
                self.message_user(request, f"{election}: {exc}", level='error')
    run_apply_polling_to_ridings.short_description = "4. Apply polling to ridings"

    def run_allocate_list_seats(self, request, queryset):
        for election in queryset:
            try:
                result = polling.allocate_list_seats(election)
                if isinstance(result, dict) and result.get('skipped'):
                    self.message_user(request, f"{election}: skipped — {result['reason']}", level='warning')
                else:
                    self.message_user(request, f"{election}: allocated list seats ({len(result)} row(s)).")
            except ValueError as exc:
                self.message_user(request, f"{election}: {exc}", level='error')
    run_allocate_list_seats.short_description = "5. Allocate list seats"


@admin.register(RidingElectionResult)
class RidingElectionResultAdmin(admin.ModelAdmin):
    list_display = ['riding', 'election', 'winner', 'winning_party', 'total_votes_cast', 'turnout_percentage']
    list_filter = ['election', 'winning_party', 'is_acclaimed']
    search_fields = ['riding__name', 'winner__user__username']
    autocomplete_fields = ['riding', 'winner', 'winning_party', 'previous_winner', 'previous_party']
    inlines = [CandidateResultInline]
    actions = ['prefill_projected_results']

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

    def prefill_projected_results(self, request, queryset):
        from forum.models import PoliticalParty

        if 'apply' in request.POST:
            parties = list(PoliticalParty.objects.all())
            swing_by_party = {}
            for party in parties:
                raw = request.POST.get(f'swing_{party.id}', '0').strip() or '0'
                try:
                    swing_by_party[party.id] = Decimal(raw)
                except InvalidOperation:
                    swing_by_party[party.id] = Decimal('0')

            filled, skipped = 0, 0
            for riding_result in queryset:
                projections = project_riding_result(
                    riding_result.riding, swing_by_party=swing_by_party,
                    exclude_election=riding_result.election,
                )
                existing_candidates = list(riding_result.candidate_results.select_related('party'))
                if not projections or not existing_candidates:
                    skipped += 1
                    continue

                projection_by_party = {proj.party.id: proj for proj in projections}
                updated_any = False
                for candidate_result in existing_candidates:
                    proj = projection_by_party.get(candidate_result.party_id)
                    if proj is None:
                        continue
                    candidate_result.votes = proj.projected_votes
                    candidate_result.save()
                    updated_any = True
                if updated_any:
                    filled += 1
                else:
                    skipped += 1

            if filled:
                self.message_user(
                    request,
                    f"Pre-filled projected vote counts for {filled} riding result(s)'s declared candidates. "
                    f"Review votes and winner before finalizing."
                )
            if skipped:
                self.message_user(
                    request,
                    f"Skipped {skipped} riding result(s): no baseline data, or no declared candidates to "
                    f"assign projected votes to (add candidates first).",
                    level='warning',
                )
            return None

        parties = list(PoliticalParty.objects.all())
        return TemplateResponse(request, 'admin/elections/ridingelectionresult/swing_form.html', {
            'riding_results': queryset,
            'parties': parties,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        })
    prefill_projected_results.short_description = "Pre-fill projected results from swing %"


@admin.register(CandidateResult)
class CandidateResultAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'party', 'riding_result', 'votes', 'vote_percentage', 'is_winner']
    list_filter = ['party', 'is_winner', 'is_incumbent']
    search_fields = ['candidate__user__username', 'riding_result__riding__name']
    autocomplete_fields = ['candidate']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('candidate__user', 'party', 'riding_result__riding', 'riding_result__election')


@admin.register(PartyModifier)
class PartyModifierAdmin(admin.ModelAdmin):
    list_display = ['election', 'party', 'personal_mods_total', 'platform_score', 'press_score',
                     'attack_press_score', 'gov_bonus', 'modifier_transfer', 'total_modifier']
    list_filter = ['election', 'party']
    readonly_fields = ['personal_mods_total']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('election', 'party')


@admin.register(NationalPoll)
class NationalPollAdmin(admin.ModelAdmin):
    list_display = ['election', 'party', 'true_polling_pct', 'random_number', 'fuzzed_pct', 'corrected_pct']
    list_filter = ['election', 'party']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('election', 'party')


@admin.register(RegionalPoll)
class RegionalPollAdmin(admin.ModelAdmin):
    list_display = ['election', 'party', 'region', 'regional_pct']
    list_filter = ['election', 'region', 'party']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('election', 'party')


@admin.register(ElectionRegionSeats)
class ElectionRegionSeatsAdmin(admin.ModelAdmin):
    list_display = ['election', 'region', 'list_seats']
    list_filter = ['election', 'region']


@admin.register(RegionalListSeat)
class RegionalListSeatAdmin(admin.ModelAdmin):
    list_display = ['election', 'party', 'region', 'list_votes', 'seats_won']
    list_filter = ['election', 'region', 'party']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('election', 'party')