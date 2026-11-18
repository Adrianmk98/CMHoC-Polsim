from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Prefetch
from django.utils import timezone
from .permissions import (
    can_manage_elections, can_manage_cabinet, can_manage_bills, can_manage_scores,
    can_manage_parties, can_manage_users, get_moderator_permissions,
)
from .audit import log_action, diff_fields
from elections.models import Election, RidingElectionResult, CandidateResult
from elections import polling
from forum.models import Riding, UserProfile, PoliticalParty, Cabinet, CabinetPosition, PositionHistory
from voting.models import Bill, Vote, Ballot
from parties.models import Party, PartyMembership, PartyRole, JoinRequest
from npcs.models import NPCProfile
from npcs.forms import NPCAdminForm


@login_required
def moderator_dashboard(request):
    """Main moderator dashboard"""
    perms = get_moderator_permissions(request.user)
    
    if not perms['is_moderator']:
        messages.error(request, "You don't have permission to access moderator tools.")
        return redirect('index')
    
    # Get statistics based on permissions
    context = {
        'permissions': perms,
    }
    
    # Election stats
    if perms['can_manage_elections']:
        context['total_elections'] = Election.objects.count()
        context['completed_elections'] = Election.objects.filter(is_completed=True).count()
        context['pending_elections'] = Election.objects.filter(is_completed=False).count()
        context['recent_elections'] = Election.objects.all()[:5]
    
    # Cabinet stats
    if perms['can_manage_cabinet']:
        context['total_cabinets'] = Cabinet.objects.count()
        context['current_cabinet'] = Cabinet.objects.filter(is_current=True).first()
    
    # Bill stats
    if perms['can_manage_bills']:
        context['total_bills'] = Bill.objects.count()
        context['active_votes'] = Vote.objects.filter(is_active=True).count()

    # Party stats
    if perms['can_manage_parties']:
        context['total_parties'] = Party.objects.count()
        context['pending_join_requests'] = JoinRequest.objects.filter(status='PENDING').count()

    # User/position stats
    if perms['can_manage_users']:
        context['total_users'] = UserProfile.objects.count()
        context['current_positions'] = PositionHistory.objects.filter(end_date__isnull=True).count()

    return render(request, 'dashboard.html', context)


@login_required
def debug_permissions(request):
    """Debug view to check permissions"""
    debug_info = {
        'user': request.user,
        'is_authenticated': request.user.is_authenticated,
        'is_staff': request.user.is_staff,
        'username': request.user.username,
    }
    
    try:
        profile = request.user.moderator_profile
        debug_info['has_profile'] = True
        debug_info['profile_id'] = profile.id
        debug_info['is_moderator'] = profile.is_moderator
        debug_info['can_manage_elections'] = profile.can_manage_elections
        debug_info['can_manage_cabinet'] = profile.can_manage_cabinet
        debug_info['can_manage_bills'] = profile.can_manage_bills
        debug_info['can_manage_users'] = profile.can_manage_users
        debug_info['can_manage_scores'] = profile.can_manage_scores
        debug_info['can_manage_parties'] = profile.can_manage_parties
    except Exception as e:
        debug_info['has_profile'] = False
        debug_info['profile_error'] = str(e)
    
    debug_info['permissions'] = get_moderator_permissions(request.user)
    
    return render(request, 'debug.html', {'debug_info': debug_info})


# ============================================================================
# ELECTION MANAGEMENT
# ============================================================================

@login_required
def election_dashboard(request):
    """Election-specific moderator dashboard"""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')
    
    elections = Election.objects.all().order_by('-election_date')
    
    context = {
        'elections': elections,
        'total_elections': elections.count(),
        'completed_elections': elections.filter(is_completed=True).count(),
        'pending_elections': elections.filter(is_completed=False).count(),
    }
    return render(request, 'elections/dashboard.html', context)


@login_required
def create_election(request):
    """Create new election"""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to create elections.")
        return redirect('moderator:dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        election_type = request.POST.get('election_type')
        election_date = request.POST.get('election_date')
        description = request.POST.get('description', '')
        
        election = Election.objects.create(
            name=name,
            election_type=election_type,
            election_date=election_date,
            description=description,
            is_completed=False
        )
        
        # For by-elections, set the riding
        if election_type == 'BY_ELECTION':
            riding_id = request.POST.get('riding')
            if riding_id:
                election.riding = Riding.objects.get(pk=riding_id)
                election.save()

        # Pre-create a blank result row per riding so the candidate/polling wizard has
        # something to attach CandidateResult/projections to.
        if election.election_type == 'BY_ELECTION' and election.riding:
            target_ridings = [election.riding]
        else:
            target_ridings = Riding.objects.all()
        for riding in target_ridings:
            RidingElectionResult.objects.get_or_create(election=election, riding=riding)

        log_action(request.user, 'create', election, view_name='create_election')
        messages.success(request, f"Election '{name}' created! Now declare candidates and run polling.")
        return redirect('moderator:add_results', election_id=election.id)
    
    ridings = Riding.objects.all().order_by('name')
    
    context = {
        'ridings': ridings,
    }
    return render(request, 'elections/create.html', context)


@login_required
def add_results(request, election_id):
    """Score-driven results wizard: declare candidates, run the polling pipeline stage by
    stage, then review/confirm the auto-declared winners."""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')

    election = get_object_or_404(Election, pk=election_id)

    # Get ridings to add results for
    if election.election_type == 'BY_ELECTION' and election.riding:
        ridings = [election.riding]
    else:
        ridings = Riding.objects.all().order_by('name')

    # Get existing results
    existing_results = RidingElectionResult.objects.filter(
        election=election
    ).select_related('riding', 'winner', 'winning_party').prefetch_related('candidate_results')

    # Create lookup for existing results
    results_by_riding = {r.riding.id: r for r in existing_results}
    candidate_counts_by_riding = {
        r.riding.id: r.candidate_results.count() for r in existing_results
    }
    ridings_with_candidates = sum(1 for count in candidate_counts_by_riding.values() if count > 0)

    has_modifiers = election.party_modifiers.exists()
    has_national_poll = election.national_polls.exists()
    has_regional_poll = election.regional_polls.exists()
    has_applied_polling = any(
        candidate_counts_by_riding.get(riding_id, 0) > 0 and result.winner_id
        for riding_id, result in results_by_riding.items()
    )

    context = {
        'election': election,
        'ridings': ridings,
        'results_by_riding': results_by_riding,
        'candidate_counts_by_riding': candidate_counts_by_riding,
        'ridings_with_candidates': ridings_with_candidates,
        'parties': PoliticalParty.objects.all(),
        'users': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
        'has_modifiers': has_modifiers,
        'has_national_poll': has_national_poll,
        'has_regional_poll': has_regional_poll,
        'has_applied_polling': has_applied_polling,
        'party_modifiers': election.party_modifiers.select_related('party').order_by('-personal_mods_total') if has_modifiers else None,
        'national_polls': election.national_polls.select_related('party').order_by('-corrected_pct') if has_national_poll else None,
        'regional_polls': election.regional_polls.select_related('party').order_by('region', '-regional_pct') if has_regional_poll else None,
        'region_seats': election.region_seat_configs.all() if election.uses_list_seats else None,
        'list_seats': election.list_seats.select_related('party').order_by('region', '-seats_won') if election.uses_list_seats else None,
    }
    return render(request, 'elections/add_results.html', context)


@login_required
def run_compute_modifiers(request, election_id):
    """Pipeline stage 1: sum each party's active members' scores into a PartyModifier."""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')

    election = get_object_or_404(Election, pk=election_id)
    if request.method == 'POST':
        try:
            rows = polling.compute_party_modifiers(election)
            messages.success(request, f"Computed party modifiers for {len(rows)} party/ies.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('moderator:add_results', election_id=election.id)


@login_required
def run_national_poll(request, election_id):
    """Pipeline stage 2: normalize modifiers into a national polling % with random fuzz."""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')

    election = get_object_or_404(Election, pk=election_id)
    if request.method == 'POST':
        kwargs = {}
        margin_of_error = request.POST.get('margin_of_error', '').strip()
        volatility_multiplier = request.POST.get('volatility_multiplier', '').strip()
        if margin_of_error:
            kwargs['margin_of_error'] = Decimal(margin_of_error)
        if volatility_multiplier:
            kwargs['volatility_multiplier'] = Decimal(volatility_multiplier)
        try:
            polls = polling.run_national_polling(election, **kwargs)
            messages.success(request, f"Ran national polling for {len(polls)} party/ies.")
        except (ValueError, InvalidOperation) as exc:
            messages.error(request, str(exc))
    return redirect('moderator:add_results', election_id=election.id)


@login_required
def run_regional_poll(request, election_id):
    """Pipeline stage 3: spread the national poll across regions, with optional mod swings."""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')

    election = get_object_or_404(Election, pk=election_id)
    if request.method == 'POST':
        regional_swing = {}
        for key, raw in request.POST.items():
            if not key.startswith('swing_'):
                continue
            raw = raw.strip()
            if not raw:
                continue
            _, party_id, region = key.split('_', 2)
            try:
                regional_swing[(int(party_id), region)] = Decimal(raw)
            except InvalidOperation:
                continue
        try:
            polls = polling.run_regional_polling(election, regional_swing=regional_swing or None)
            messages.success(request, f"Wrote {len(polls)} regional poll row(s).")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('moderator:add_results', election_id=election.id)


@login_required
def run_apply_to_ridings(request, election_id):
    """Pipeline stage 4: project each riding's vote totals and auto-declare winners."""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')

    election = get_object_or_404(Election, pk=election_id)
    if request.method == 'POST':
        try:
            result = polling.apply_polling_to_ridings(election)
            messages.success(
                request,
                f"Applied polling to {result['updated']} riding(s), skipped {result['skipped']} "
                f"(no baseline data or no declared candidates)."
            )
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('moderator:add_results', election_id=election.id)


@login_required
def run_allocate_seats(request, election_id):
    """Pipeline stage 5 (optional): D'Hondt-allocate proportional regional list seats."""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')

    election = get_object_or_404(Election, pk=election_id)
    if request.method == 'POST':
        try:
            result = polling.allocate_list_seats(election)
            if isinstance(result, dict) and result.get('skipped'):
                messages.warning(request, f"Skipped — {result['reason']}")
            else:
                messages.success(request, f"Allocated list seats ({len(result)} row(s)).")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('moderator:add_results', election_id=election.id)


@login_required
def bulk_add_results(request, election_id):
    """Bulk add multiple riding results at once (AJAX)"""
    if not can_manage_elections(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    election = get_object_or_404(Election, pk=election_id)
    
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            
            created_count = 0
            updated_count = 0
            
            for result_data in data.get('results', []):
                riding = Riding.objects.get(pk=result_data['riding_id'])
                winner = UserProfile.objects.get(pk=result_data['winner_id']) if result_data.get('winner_id') else None

                result, created = RidingElectionResult.objects.update_or_create(
                    election=election,
                    riding=riding,
                    defaults={
                        'total_votes_cast': result_data.get('total_votes', 0),
                        'is_acclaimed': result_data.get('is_acclaimed', False),
                    }
                )

                if winner:
                    result.set_winner(winner)

                log_action(
                    request.user, 'create' if created else 'update', result,
                    view_name='bulk_add_results',
                    changes={'winner': str(winner) if winner else None, 'total_votes': result_data.get('total_votes', 0)},
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            return JsonResponse({
                'success': True,
                'created': created_count,
                'updated': updated_count
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST required'}, status=400)


@login_required
def add_candidates(request, result_id):
    """Add candidates to a riding result"""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')
    
    riding_result = get_object_or_404(RidingElectionResult, pk=result_id)
    
    if request.method == 'POST':
        candidate_id = request.POST.get('candidate_id')
        party_id = request.POST.get('party_id')
        votes = request.POST.get('votes', 0)
        is_incumbent = request.POST.get('is_incumbent') == 'on'
        
        candidate = UserProfile.objects.get(pk=candidate_id)
        party = PoliticalParty.objects.get(pk=party_id) if party_id else None
        
        candidate_result, created = CandidateResult.objects.update_or_create(
            riding_result=riding_result,
            candidate=candidate,
            defaults={
                'party': party,
                'votes': int(votes),
                'is_incumbent': is_incumbent,
                'is_winner': (candidate == riding_result.winner)
            }
        )
        
        # Recalculate total votes
        total = riding_result.candidate_results.aggregate(Sum('votes'))['votes__sum'] or 0
        riding_result.total_votes_cast = total
        riding_result.save()

        log_action(
            request.user, 'create' if created else 'update', candidate_result,
            view_name='add_candidates',
            changes={'candidate': candidate.user.username, 'party': str(party) if party else None, 'votes': int(votes)},
        )
        messages.success(request, f"Added {candidate.user.username} to results.")
        return redirect('moderator:add_candidates', result_id=result_id)
    
    # Get existing candidates
    existing_candidates = riding_result.candidate_results.all().select_related('candidate__user', 'party')
    
    # Get available candidates (all users)
    all_candidates = UserProfile.objects.all().select_related('user', 'party').order_by('user__username')
    
    context = {
        'riding_result': riding_result,
        'existing_candidates': existing_candidates,
        'all_candidates': all_candidates,
        'parties': PoliticalParty.objects.all(),
    }
    return render(request, 'elections/add_candidates.html', context)


@login_required
def complete_election(request, election_id):
    """Mark election as completed"""
    if not can_manage_elections(request.user):
        messages.error(request, "You don't have permission to manage elections.")
        return redirect('moderator:dashboard')
    
    election = get_object_or_404(Election, pk=election_id)
    
    if request.method == 'POST':
        election.is_completed = True
        election.calculate_totals()
        election.save()

        log_action(request.user, 'update', election, view_name='complete_election', changes={'is_completed': [False, True]})
        messages.success(request, f"Election '{election.name}' marked as completed!")
        return redirect('elections:election_detail', election_id=election.id)
    
    # Show confirmation page
    results_count = election.riding_results.count()
    results_with_winners = election.riding_results.filter(winner__isnull=False).count()
    
    context = {
        'election': election,
        'results_count': results_count,
        'results_with_winners': results_with_winners,
    }
    return render(request, 'elections/complete.html', context)


# ============================================================================
# CABINET MANAGEMENT
# ============================================================================

@login_required
def cabinet_dashboard(request):
    """Cabinet-specific moderator dashboard"""
    if not can_manage_cabinet(request.user):
        messages.error(request, "You don't have permission to manage cabinets.")
        return redirect('moderator:dashboard')

    cabinets = Cabinet.objects.all().order_by('-start_date').select_related(
        'prime_minister', 'prime_minister__profile'
    ).prefetch_related(
        'positions__user_profile__user', 'positions__user_profile__party'
    )
    current_cabinet = Cabinet.objects.filter(is_current=True).first()

    context = {
        'cabinets': cabinets,
        'current_cabinet': current_cabinet,
    }
    return render(request, 'cabinet/dashboard.html', context)


@login_required
def mod_create_cabinet(request):
    """Create a new cabinet."""
    if not can_manage_cabinet(request.user):
        messages.error(request, "You don't have permission to manage cabinets.")
        return redirect('moderator:dashboard')

    from django.contrib.auth.models import User

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        pm_id = request.POST.get('prime_minister')
        party_id = request.POST.get('government_party')
        start_date = request.POST.get('start_date')
        is_current = request.POST.get('is_current') == '1'
        description = request.POST.get('description', '').strip()

        if not name or not start_date:
            messages.error(request, "Name and start date are required.")
        else:
            pm = UserProfile.objects.filter(pk=pm_id).first() if pm_id else None
            party = PoliticalParty.objects.filter(pk=party_id).first() if party_id else None
            cabinet = Cabinet.objects.create(
                name=name,
                prime_minister=pm.user if pm else None,
                government_party=party,
                start_date=start_date,
                is_current=is_current,
                description=description,
            )
            log_action(request.user, 'create', cabinet, view_name='mod_create_cabinet')
            messages.success(request, f"Cabinet '{name}' created.")
            return redirect('moderator:cabinet_dashboard')

    context = {
        'all_profiles': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
        'parties': PoliticalParty.objects.all(),
    }
    return render(request, 'cabinet/create_cabinet.html', context)


@login_required
def mod_edit_cabinet(request, cabinet_id):
    """Edit cabinet metadata."""
    if not can_manage_cabinet(request.user):
        messages.error(request, "You don't have permission to manage cabinets.")
        return redirect('moderator:dashboard')

    cabinet = get_object_or_404(Cabinet, pk=cabinet_id)

    if request.method == 'POST':
        before = {f: str(getattr(cabinet, f)) for f in ['name', 'prime_minister_id', 'government_party_id', 'start_date', 'end_date', 'is_current', 'description']}

        cabinet.name = request.POST.get('name', cabinet.name).strip()
        pm_id = request.POST.get('prime_minister')
        party_id = request.POST.get('government_party')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None
        cabinet.is_current = request.POST.get('is_current') == '1'
        cabinet.description = request.POST.get('description', '').strip()

        if start_date:
            cabinet.start_date = start_date
        cabinet.end_date = end_date

        pm = UserProfile.objects.filter(pk=pm_id).first() if pm_id else None
        cabinet.prime_minister = pm.user if pm else None
        cabinet.government_party = PoliticalParty.objects.filter(pk=party_id).first() if party_id else None

        cabinet.save()
        changes = diff_fields(cabinet, ['name', 'prime_minister_id', 'government_party_id', 'start_date', 'end_date', 'is_current', 'description'], before)
        log_action(request.user, 'update', cabinet, changes=changes, view_name='mod_edit_cabinet')
        messages.success(request, f"Cabinet '{cabinet.name}' updated.")
        return redirect('moderator:cabinet_dashboard')

    context = {
        'cabinet': cabinet,
        'all_profiles': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
        'parties': PoliticalParty.objects.all(),
    }
    return render(request, 'cabinet/edit_cabinet.html', context)


@login_required
def mod_add_position(request, cabinet_id):
    """Add a position to any cabinet."""
    if not can_manage_cabinet(request.user):
        messages.error(request, "You don't have permission to manage cabinets.")
        return redirect('moderator:dashboard')

    cabinet = get_object_or_404(Cabinet, pk=cabinet_id)

    if request.method == 'POST':
        profile_id = request.POST.get('user_profile')
        position_type = request.POST.get('position_type')
        portfolio = request.POST.get('portfolio', '').strip()
        title = request.POST.get('title', '').strip()
        order = int(request.POST.get('order', 0) or 0)
        start_date = request.POST.get('start_date')
        notes = request.POST.get('notes', '').strip()

        if not profile_id or not position_type or not portfolio or not title or not start_date:
            messages.error(request, "All fields except notes are required.")
        else:
            profile = get_object_or_404(UserProfile, pk=profile_id)
            position = CabinetPosition.objects.create(
                cabinet=cabinet,
                user_profile=profile,
                position_type=position_type,
                portfolio=portfolio,
                title=title,
                order=order,
                start_date=start_date,
                notes=notes,
            )
            log_action(request.user, 'create', position, view_name='mod_add_position')
            messages.success(request, f"Added {title} to {cabinet.name}.")
            return redirect('moderator:cabinet_dashboard')

    context = {
        'cabinet': cabinet,
        'all_profiles': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
        'position_types': CabinetPosition.POSITION_TYPES,
    }
    return render(request, 'cabinet/add_position.html', context)


@login_required
def mod_edit_position(request, position_id):
    """Edit a cabinet position."""
    if not can_manage_cabinet(request.user):
        messages.error(request, "You don't have permission to manage cabinets.")
        return redirect('moderator:dashboard')

    position = get_object_or_404(CabinetPosition, pk=position_id)

    if request.method == 'POST':
        before = {f: str(getattr(position, f)) for f in ['position_type', 'portfolio', 'title', 'order', 'notes', 'user_profile_id']}

        profile_id = request.POST.get('user_profile')
        position.position_type = request.POST.get('position_type', position.position_type)
        position.portfolio = request.POST.get('portfolio', position.portfolio).strip()
        position.title = request.POST.get('title', position.title).strip()
        position.order = int(request.POST.get('order', position.order) or 0)
        position.notes = request.POST.get('notes', '').strip()

        if profile_id:
            position.user_profile = get_object_or_404(UserProfile, pk=profile_id)

        position.save()
        changes = diff_fields(position, ['position_type', 'portfolio', 'title', 'order', 'notes', 'user_profile_id'], before)
        log_action(request.user, 'update', position, changes=changes, view_name='mod_edit_position')
        messages.success(request, f"Updated {position.title}.")
        return redirect('moderator:cabinet_dashboard')

    context = {
        'position': position,
        'cabinet': position.cabinet,
        'all_profiles': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
        'position_types': CabinetPosition.POSITION_TYPES,
    }
    return render(request, 'cabinet/edit_position.html', context)


@login_required
def mod_remove_position(request, position_id):
    """End a cabinet position (set end_date)."""
    if not can_manage_cabinet(request.user):
        messages.error(request, "You don't have permission to manage cabinets.")
        return redirect('moderator:dashboard')

    position = get_object_or_404(CabinetPosition, pk=position_id)

    if request.method == 'POST':
        from django.utils import timezone
        end_date = request.POST.get('end_date') or timezone.now().date()
        position.end_date = end_date
        position.save()
        log_action(request.user, 'end', position, changes={'end_date': [None, str(end_date)]}, view_name='mod_remove_position')
        messages.success(request, f"Ended {position.title}.")
        return redirect('moderator:cabinet_dashboard')

    context = {
        'position': position,
        'cabinet': position.cabinet,
    }
    return render(request, 'cabinet/remove_position.html', context)


# ============================================================================
# BILL MANAGEMENT
# ============================================================================

@login_required
def bill_dashboard(request):
    """Bill-specific moderator dashboard"""
    if not can_manage_bills(request.user):
        messages.error(request, "You don't have permission to manage bills.")
        return redirect('moderator:dashboard')
    
    bills = Bill.objects.all().select_related('sponsor', 'sponsor__profile').order_by('-created_at')
    active_votes = Vote.objects.filter(is_active=True).select_related('bill').prefetch_related('ballot_set__voter')
    
    context = {
        'bills': bills,
        'active_votes': active_votes,
    }
    return render(request, 'bills/dashboard.html', context)


# ============================================================================
# SCORE MANAGEMENT
# ============================================================================

@login_required
def scores_dashboard(request):
    """Polling calculator — moderator-only scores dashboard."""
    if not can_manage_scores(request.user):
        messages.error(request, "You don't have permission to manage scores.")
        return redirect('moderator:dashboard')

    from scores.models import ParliamentSession, get_player_totals
    from django.contrib.auth.models import User

    sessions = ParliamentSession.objects.all()
    session_id = request.GET.get('session')

    active_session = None
    if session_id:
        active_session = ParliamentSession.objects.filter(pk=session_id).first()
    if not active_session:
        active_session = ParliamentSession.objects.filter(is_active=True).first()

    from scores.models import ScoreEntry
    all_users = User.objects.filter(is_active=True).select_related('profile').order_by('username')
    players = []
    if active_session:
        for user in all_users:
            totals = get_player_totals(active_session, user)
            players.append({'user': user, **totals})
        players.sort(key=lambda p: p['active_modifier'], reverse=True)

    context = {
        'sessions': sessions,
        'active_session': active_session,
        'players': players,
        'all_users': all_users,
        'score_types': ScoreEntry.SCORE_TYPES,
    }
    return render(request, 'scores/dashboard.html', context)


@login_required
def session_create(request):
    """Create a new parliament session."""
    if not can_manage_scores(request.user):
        messages.error(request, "You don't have permission to manage scores.")
        return redirect('moderator:dashboard')

    from scores.models import ParliamentSession, PlayerLT, get_player_totals
    from django.contrib.auth.models import User
    from decimal import Decimal

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        start_date = request.POST.get('start_date')
        carry_forward = request.POST.get('carry_forward') == '1'
        carry_halved = request.POST.get('carry_halved') == '1'

        if not name or not start_date:
            messages.error(request, "Name and start date are required.")
            return redirect('moderator:session_create')

        session = ParliamentSession.objects.create(
            name=name,
            start_date=start_date,
            is_active=True,
        )

        if carry_forward:
            prev = ParliamentSession.objects.exclude(pk=session.pk).order_by('-start_date').first()
            if prev:
                for user in User.objects.filter(is_active=True):
                    totals = get_player_totals(prev, user)
                    pm = totals['personal_modifier']
                    if pm > 0:
                        lt = (pm / Decimal('2')).quantize(Decimal('0.01')) if carry_halved else pm
                        PlayerLT.objects.get_or_create(
                            session=session, user=user,
                            defaults={'lt_score': lt, 'is_active_persona': totals['is_active_persona']},
                        )

        messages.success(request, f"Session '{name}' created.")
        return redirect('moderator:scores_dashboard')

    return render(request, 'scores/session_create.html', {})


@login_required
def player_scores(request, user_id):
    """View/edit all score entries for a player in the active session."""
    if not can_manage_scores(request.user):
        messages.error(request, "You don't have permission to manage scores.")
        return redirect('moderator:dashboard')

    from scores.models import ParliamentSession, PlayerLT, ScoreEntry, get_player_totals, POSITION_BONUSES
    from django.contrib.auth.models import User

    target_user = get_object_or_404(User, pk=user_id)
    sessions = ParliamentSession.objects.all()
    session_id = request.GET.get('session')
    active_session = (
        ParliamentSession.objects.filter(pk=session_id).first()
        if session_id else
        ParliamentSession.objects.filter(is_active=True).first()
    )

    lt_obj = None
    entries = []
    totals = {}
    if active_session:
        lt_obj, _ = PlayerLT.objects.get_or_create(
            session=active_session, user=target_user,
            defaults={'lt_score': 0, 'is_active_persona': True},
        )
        entries = ScoreEntry.objects.filter(session=active_session, user=target_user).select_related('created_by')
        totals = get_player_totals(active_session, target_user)

    context = {
        'target_user': target_user,
        'sessions': sessions,
        'active_session': active_session,
        'lt_obj': lt_obj,
        'entries': entries,
        'totals': totals,
        'score_types': ScoreEntry.SCORE_TYPES,
    }
    return render(request, 'scores/player_scores.html', context)


@login_required
def update_lt(request, user_id):
    """Update a player's LT score and active persona flag."""
    if not can_manage_scores(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    from scores.models import ParliamentSession, PlayerLT
    from django.contrib.auth.models import User
    from decimal import Decimal, InvalidOperation

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    target_user = get_object_or_404(User, pk=user_id)
    session_id = request.POST.get('session_id')
    active_session = get_object_or_404(ParliamentSession, pk=session_id)

    try:
        lt_score = Decimal(request.POST.get('lt_score', '0'))
    except InvalidOperation:
        return JsonResponse({'error': 'Invalid score'}, status=400)

    is_active = request.POST.get('is_active_persona') == '1'
    notes = request.POST.get('notes', '')

    lt_obj, _ = PlayerLT.objects.update_or_create(
        session=active_session, user=target_user,
        defaults={'lt_score': lt_score, 'is_active_persona': is_active, 'notes': notes},
    )
    log_action(
        request.user, 'update', lt_obj, view_name='update_lt',
        changes={'lt_score': str(lt_score), 'is_active_persona': is_active, 'target_user': target_user.username},
    )
    messages.success(request, "LT score updated.")
    return redirect(f"{request.build_absolute_uri('/')[:-1]}{request.POST.get('next', '/')}")


@login_required
def add_score_entry(request, user_id):
    """Add a score entry for a player."""
    if not can_manage_scores(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    from scores.models import ParliamentSession, ScoreEntry
    from django.contrib.auth.models import User
    from decimal import Decimal, InvalidOperation

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    target_user = get_object_or_404(User, pk=user_id)
    session_id = request.POST.get('session_id')
    active_session = get_object_or_404(ParliamentSession, pk=session_id)

    try:
        score = Decimal(request.POST.get('score', '0'))
    except InvalidOperation:
        messages.error(request, "Invalid score value.")
        return redirect(request.POST.get('next', '/'))

    score_type = request.POST.get('score_type')
    if score_type not in dict(ScoreEntry.SCORE_TYPES):
        messages.error(request, "Invalid score type.")
        return redirect(request.POST.get('next', '/'))

    entry = ScoreEntry.objects.create(
        session=active_session,
        user=target_user,
        score_type=score_type,
        score=score,
        description=request.POST.get('description', ''),
        bill_id=request.POST.get('bill_id') or None,
        press_release_id=request.POST.get('press_release_id') or None,
        thread_id=request.POST.get('thread_id') or None,
        created_by=request.user,
    )
    log_action(
        request.user, 'create', entry, view_name='add_score_entry',
        changes={'target_user': target_user.username, 'score': str(score), 'score_type': score_type},
    )
    messages.success(request, f"Score of {score} ({score_type}) added for {target_user.username}.")
    return redirect(request.POST.get('next', '/'))


@login_required
def delete_score_entry(request, entry_id):
    """Delete a score entry."""
    if not can_manage_scores(request.user):
        messages.error(request, "Permission denied.")
        return redirect('moderator:dashboard')

    from scores.models import ScoreEntry

    entry = get_object_or_404(ScoreEntry, pk=entry_id)
    user_id = entry.user_id
    session_id = entry.session_id
    log_action(
        request.user, 'delete', entry, view_name='delete_score_entry',
        changes={'target_user_id': user_id, 'score': str(entry.score), 'score_type': entry.score_type},
    )
    entry.delete()
    messages.success(request, "Score entry deleted.")
    return redirect(f"{request.path.rsplit('/delete/', 1)[0].rsplit('/', 2)[0]}/player/{user_id}/?session={session_id}")


@login_required
def grading_queue(request):
    """Moderator view of content that still needs a score, plus AI suggestions awaiting review."""
    if not can_manage_scores(request.user):
        messages.error(request, "You don't have permission to manage scores.")
        return redirect('moderator:dashboard')

    from scores.models import ParliamentSession, ScoreEntry
    from voting.models import Bill, BillDebatePost
    from press.models import PressRelease

    sessions = ParliamentSession.objects.all()
    session_id = request.GET.get('session')
    active_session = (
        ParliamentSession.objects.filter(pk=session_id).first()
        if session_id else
        ParliamentSession.objects.filter(is_active=True).first()
    )

    scored_debate_ids = set(
        ScoreEntry.objects.filter(score_type='DEBATE', debate_post_id__isnull=False)
        .values_list('debate_post_id', flat=True)
    )
    scored_press_ids = set(
        ScoreEntry.objects.filter(score_type='PRESS', press_release_id__isnull=False)
        .values_list('press_release_id', flat=True)
    )
    scored_bill_ids = set(
        ScoreEntry.objects.filter(score_type='LEGISLATION', bill_id__isnull=False)
        .values_list('bill_id', flat=True)
    )

    ungraded_debate_posts = (
        BillDebatePost.objects.select_related('bill', 'author')
        .exclude(id__in=scored_debate_ids)
        .order_by('-created_at')[:50]
    )
    ungraded_press_releases = (
        PressRelease.objects.filter(is_published=True).select_related('author')
        .exclude(id__in=scored_press_ids)
        .order_by('-published_at')[:50]
    )
    ungraded_bills = (
        Bill.objects.exclude(status='DRAFT').select_related('sponsor')
        .exclude(id__in=scored_bill_ids)
        .order_by('-created_at')[:50]
    )

    pending_entries = []
    if active_session:
        pending_entries = list(
            ScoreEntry.objects.filter(session=active_session, status='PENDING')
            .select_related('user').order_by('-created_at')
        )

    context = {
        'sessions': sessions,
        'active_session': active_session,
        'ungraded_debate_posts': ungraded_debate_posts,
        'ungraded_press_releases': ungraded_press_releases,
        'ungraded_bills': ungraded_bills,
        'pending_entries': pending_entries,
    }
    return render(request, 'scores/queue.html', context)


@login_required
def ai_suggest_score(request):
    """Have the AI suggest a score for one ungraded content item, saved as a PENDING entry for review."""
    if not can_manage_scores(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    from decimal import Decimal
    from scores.models import ParliamentSession, ScoreEntry
    from scores import ai_grading

    session_id = request.POST.get('session_id')
    active_session = get_object_or_404(ParliamentSession, pk=session_id)
    content_type = request.POST.get('content_type')
    object_id = request.POST.get('object_id')
    next_url = request.POST.get('next', 'moderator:dashboard')

    if content_type == 'debate':
        from voting.models import BillDebatePost
        obj = get_object_or_404(BillDebatePost, pk=object_id)
        suggestion = ai_grading.suggest_debate_score(obj)
        link_field, link_value, target_user = 'debate_post_id', obj.id, obj.author
        description = f"AI suggestion: debate post on {obj.bill.bill_number}"
    elif content_type == 'press':
        from press.models import PressRelease
        obj = get_object_or_404(PressRelease, pk=object_id)
        suggestion = ai_grading.suggest_press_score(obj)
        link_field, link_value, target_user = 'press_release_id', obj.id, obj.author
        description = f"AI suggestion: press release \"{obj.title}\""
    elif content_type == 'legislation':
        from voting.models import Bill
        obj = get_object_or_404(Bill, pk=object_id)
        suggestion = ai_grading.suggest_legislation_score(obj)
        link_field, link_value, target_user = 'bill_id', obj.id, obj.sponsor
        description = f"AI suggestion: bill {obj.bill_number}"
    else:
        messages.error(request, "Unknown content type.")
        return redirect(next_url)

    if not target_user:
        messages.error(request, "This item has no author/sponsor to score.")
        return redirect(next_url)

    if suggestion is None:
        messages.error(request, "AI grading is unavailable right now (LLM backend didn't respond). Try again later.")
        return redirect(next_url)

    score_type_by_content = {'debate': 'DEBATE', 'press': 'PRESS', 'legislation': 'LEGISLATION'}
    ScoreEntry.objects.update_or_create(
        session=active_session,
        score_type=score_type_by_content[content_type],
        **{link_field: link_value},
        defaults={
            'user': target_user,
            'score': Decimal(str(suggestion['score'])),
            'description': description,
            'status': 'PENDING',
            'is_ai_generated': True,
            'ai_rationale': suggestion['rationale'],
            'created_by': request.user,
        },
    )
    messages.success(request, f"AI suggested a score of {suggestion['score']} for {target_user.username}. Review it below.")
    return redirect(next_url)


@login_required
def approve_score_entry(request, entry_id):
    """Approve a pending (usually AI-suggested) score entry, optionally overriding the score first."""
    if not can_manage_scores(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    from decimal import Decimal, InvalidOperation
    from scores.models import ScoreEntry

    entry = get_object_or_404(ScoreEntry, pk=entry_id)

    try:
        entry.score = Decimal(request.POST.get('score', str(entry.score)))
    except InvalidOperation:
        messages.error(request, "Invalid score value.")
        return redirect(request.POST.get('next', '/'))

    entry.description = request.POST.get('description', entry.description)
    entry.status = 'APPROVED'
    entry.save()
    log_action(request.user, 'approve', entry, view_name='approve_score_entry', changes={'score': str(entry.score)})
    messages.success(request, f"Score approved for {entry.user.username}.")
    return redirect(request.POST.get('next', '/'))

# ============================================================================
# PARTY MANAGEMENT
# ============================================================================

@login_required
def party_dashboard(request):
    """Party-specific moderator dashboard: members, roles, join requests"""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage parties.")
        return redirect('moderator:dashboard')

    parties = Party.objects.all().select_related('leader', 'leader__profile').prefetch_related(
        Prefetch(
            'members',
            queryset=PartyMembership.objects.filter(is_active=True).select_related('user', 'user__profile').order_by('user__username'),
            to_attr='active_members',
        ),
        Prefetch(
            'roles',
            queryset=PartyRole.objects.filter(is_active=True).select_related('user'),
            to_attr='active_roles',
        ),
        Prefetch(
            'join_requests',
            queryset=JoinRequest.objects.filter(status='PENDING').select_related('user', 'user__profile').order_by('requested_at'),
            to_attr='pending_requests',
        ),
    ).order_by('name')

    members_with_party = PartyMembership.objects.filter(is_active=True).values_list('user_id', flat=True)
    unaffiliated_users = User.objects.exclude(id__in=members_with_party).order_by('username')

    context = {
        'parties': parties,
        'unaffiliated_users': unaffiliated_users,
        'role_choices': PartyRole.ROLE_CHOICES,
    }
    return render(request, 'parties/dashboard.html', context)


@login_required
def mod_add_member(request, party_id):
    """Directly add a user to a party, bypassing the join-request flow"""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage parties.")
        return redirect('moderator:dashboard')

    party = get_object_or_404(Party, pk=party_id)

    if request.method == 'POST':
        user = get_object_or_404(User, pk=request.POST.get('user_id'))

        if PartyMembership.objects.filter(user=user, is_active=True).exclude(party=party).exists():
            messages.error(request, f'{user.username} is already a member of another party. Remove them from it first.')
        else:
            membership, _ = PartyMembership.objects.update_or_create(
                user=user, party=party,
                defaults={'is_active': True, 'left_at': None},
            )
            party.update_member_count()
            log_action(request.user, 'create', membership, view_name='mod_add_member', changes={'user': user.username, 'party': party.name})
            messages.success(request, f'{user.username} has been added to {party.name}.')

    return redirect('moderator:party_dashboard')


@login_required
def mod_remove_member(request, membership_id):
    """Remove a member from a party"""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage parties.")
        return redirect('moderator:dashboard')

    membership = get_object_or_404(PartyMembership, pk=membership_id, is_active=True)

    if request.method == 'POST':
        party = membership.party
        user = membership.user
        membership.leave_party()

        if party.leader_id == user.id:
            party.leader = None
            party.save(update_fields=['leader'])

        log_action(request.user, 'delete', membership, view_name='mod_remove_member', changes={'user': user.username, 'party': party.name})
        messages.success(request, f'{user.username} has been removed from {party.name}.')

    return redirect('moderator:party_dashboard')


@login_required
def mod_assign_role(request, party_id):
    """Assign (or reassign) a leadership/officer role within a party"""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage parties.")
        return redirect('moderator:dashboard')

    party = get_object_or_404(Party, pk=party_id)

    if request.method == 'POST':
        user = get_object_or_404(User, pk=request.POST.get('user_id'))
        role = request.POST.get('role')

        if role not in dict(PartyRole.ROLE_CHOICES):
            messages.error(request, 'Invalid role.')
            return redirect('moderator:party_dashboard')

        if not PartyMembership.objects.filter(user=user, party=party, is_active=True).exists():
            messages.error(request, f'{user.username} must be an active member of {party.name} first.')
            return redirect('moderator:party_dashboard')

        party_role, _ = PartyRole.objects.update_or_create(
            party=party, user=user, role=role,
            defaults={'is_active': True, 'appointed_by': request.user, 'removed_at': None},
        )

        if role == 'LEADER':
            party.leader = user
            party.save(update_fields=['leader'])

        log_action(request.user, 'create', party_role, view_name='mod_assign_role', changes={'user': user.username, 'party': party.name, 'role': role})
        messages.success(request, f'{user.username} is now {dict(PartyRole.ROLE_CHOICES)[role]} of {party.name}.')

    return redirect('moderator:party_dashboard')


@login_required
def mod_remove_role(request, role_id):
    """Remove a leadership/officer role from a party member"""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage parties.")
        return redirect('moderator:dashboard')

    role = get_object_or_404(PartyRole, pk=role_id, is_active=True)

    if request.method == 'POST':
        role.is_active = False
        role.removed_at = timezone.now()
        role.save()

        if role.role == 'LEADER' and role.party.leader_id == role.user_id:
            role.party.leader = None
            role.party.save(update_fields=['leader'])

        log_action(request.user, 'end', role, view_name='mod_remove_role', changes={'user': role.user.username, 'party': role.party.name, 'role': role.role})
        messages.success(request, f'Removed {role.get_role_display()} role from {role.user.username}.')

    return redirect('moderator:party_dashboard')


@login_required
def mod_approve_join_request(request, request_id):
    """Approve a pending party join request on behalf of the party leadership"""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage parties.")
        return redirect('moderator:dashboard')

    join_request = get_object_or_404(JoinRequest, pk=request_id, status='PENDING')

    if request.method == 'POST':
        try:
            join_request.approve(request.user)
            log_action(request.user, 'approve', join_request, view_name='mod_approve_join_request', changes={'user': join_request.user.username, 'party': join_request.party.name})
            messages.success(request, f'{join_request.user.username} has been added to {join_request.party.name}.')
        except ValueError as e:
            messages.error(request, str(e))

    return redirect('moderator:party_dashboard')


@login_required
def mod_reject_join_request(request, request_id):
    """Reject a pending party join request on behalf of the party leadership"""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage parties.")
        return redirect('moderator:dashboard')

    join_request = get_object_or_404(JoinRequest, pk=request_id, status='PENDING')

    if request.method == 'POST':
        join_request.reject(request.user)
        log_action(request.user, 'reject', join_request, view_name='mod_reject_join_request', changes={'user': join_request.user.username, 'party': join_request.party.name})
        messages.success(request, f"{join_request.user.username}'s request to join {join_request.party.name} has been rejected.")

    return redirect('moderator:party_dashboard')


# ============================================================================
# NPC MANAGEMENT
# ============================================================================

@login_required
def npc_dashboard(request):
    """List all NPCs for full admin editing."""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage NPCs.")
        return redirect('moderator:dashboard')

    npcs = NPCProfile.objects.all().select_related('user_profile__user', 'party')

    context = {
        'npcs': npcs,
    }
    return render(request, 'npcs/dashboard.html', context)


@login_required
def mod_edit_npc(request, pk):
    """Full admin editing of any NPC's persona and behavior tuning."""
    if not can_manage_parties(request.user):
        messages.error(request, "You don't have permission to manage NPCs.")
        return redirect('moderator:dashboard')

    npc = get_object_or_404(NPCProfile, pk=pk)

    if request.method == 'POST':
        form = NPCAdminForm(request.POST, instance=npc)
        if form.is_valid():
            npc_instance = form.save(commit=False)
            if 'persona' in form.changed_data:
                npc_instance.persona_manually_edited = True
            npc_instance.save()
            log_action(request.user, 'update', npc_instance, view_name='mod_edit_npc', changes={f: str(form.cleaned_data[f]) for f in form.changed_data})
            messages.success(request, 'NPC updated successfully!')
            return redirect('moderator:npc_dashboard')
    else:
        form = NPCAdminForm(instance=npc)

    context = {
        'form': form,
        'npc': npc,
    }
    return render(request, 'npcs/edit.html', context)


# ============================================================================
# POSITION HISTORY MANAGEMENT (Speaker, Whip, House Leader, Critic, Committee
# roles, and fixing MP/Senator/etc. records) - previously only editable via
# raw Django admin.
# ============================================================================

@login_required
def position_dashboard(request):
    """List current and past PositionHistory records, filterable by type/user."""
    if not can_manage_users(request.user):
        messages.error(request, "You don't have permission to manage positions.")
        return redirect('moderator:dashboard')

    positions = PositionHistory.objects.all().select_related(
        'user_profile__user', 'user_profile__party', 'riding_obj'
    ).order_by('-start_date')

    position_type = request.GET.get('position_type', '')
    if position_type:
        positions = positions.filter(position_type=position_type)

    show_past = request.GET.get('show_past') == '1'
    if not show_past:
        positions = positions.filter(end_date__isnull=True)

    context = {
        'positions': positions,
        'position_types': PositionHistory.POSITION_TYPES,
        'selected_type': position_type,
        'show_past': show_past,
    }
    return render(request, 'positions/dashboard.html', context)


@login_required
def mod_add_position_history(request):
    """Create a PositionHistory record: appoint a Speaker, Whip, House Leader, Critic,
    committee role, or fix a missing/incorrect MP/Senator/etc. record."""
    if not can_manage_users(request.user):
        messages.error(request, "You don't have permission to manage positions.")
        return redirect('moderator:dashboard')

    if request.method == 'POST':
        profile_id = request.POST.get('user_profile')
        position_type = request.POST.get('position_type')
        position_title = request.POST.get('position_title', '').strip()
        riding_id = request.POST.get('riding_obj')
        start_date = request.POST.get('start_date')
        notes = request.POST.get('notes', '').strip()

        if not profile_id or not position_type or not position_title or not start_date:
            messages.error(request, "Member, position type, title, and start date are required.")
        else:
            profile = get_object_or_404(UserProfile, pk=profile_id)
            riding_obj = Riding.objects.filter(pk=riding_id).first() if riding_id else None
            position = PositionHistory.objects.create(
                user_profile=profile,
                position_type=position_type,
                position_title=position_title,
                riding_obj=riding_obj,
                start_date=start_date,
                notes=notes,
            )
            log_action(request.user, 'create', position, view_name='mod_add_position_history')
            messages.success(request, f"Added {position_title} for {profile.user.username}.")
            return redirect('moderator:position_dashboard')

    context = {
        'all_profiles': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
        'position_types': PositionHistory.POSITION_TYPES,
        'ridings': Riding.objects.all().order_by('name'),
    }
    return render(request, 'positions/add.html', context)


@login_required
def mod_edit_position_history(request, position_id):
    """Edit any field of a PositionHistory record."""
    if not can_manage_users(request.user):
        messages.error(request, "You don't have permission to manage positions.")
        return redirect('moderator:dashboard')

    position = get_object_or_404(PositionHistory, pk=position_id)

    if request.method == 'POST':
        before = {f: str(getattr(position, f)) for f in ['position_type', 'position_title', 'riding_obj_id', 'start_date', 'end_date', 'notes', 'user_profile_id']}

        profile_id = request.POST.get('user_profile')
        if profile_id:
            position.user_profile = get_object_or_404(UserProfile, pk=profile_id)
        position.position_type = request.POST.get('position_type', position.position_type)
        position.position_title = request.POST.get('position_title', position.position_title).strip()
        riding_id = request.POST.get('riding_obj')
        position.riding_obj = Riding.objects.filter(pk=riding_id).first() if riding_id else None
        start_date = request.POST.get('start_date')
        if start_date:
            position.start_date = start_date
        position.end_date = request.POST.get('end_date') or None
        position.notes = request.POST.get('notes', '').strip()

        position.save()
        changes = diff_fields(position, ['position_type', 'position_title', 'riding_obj_id', 'start_date', 'end_date', 'notes', 'user_profile_id'], before)
        log_action(request.user, 'update', position, changes=changes, view_name='mod_edit_position_history')
        messages.success(request, f"Updated {position.position_title}.")
        return redirect('moderator:position_dashboard')

    context = {
        'position': position,
        'all_profiles': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
        'position_types': PositionHistory.POSITION_TYPES,
        'ridings': Riding.objects.all().order_by('name'),
    }
    return render(request, 'positions/edit.html', context)


@login_required
def mod_end_position_history(request, position_id):
    """End a position (set end_date) without deleting the historical record."""
    if not can_manage_users(request.user):
        messages.error(request, "You don't have permission to manage positions.")
        return redirect('moderator:dashboard')

    position = get_object_or_404(PositionHistory, pk=position_id)

    if request.method == 'POST':
        end_date = request.POST.get('end_date') or timezone.now().date()
        position.end_date = end_date
        position.save()
        log_action(request.user, 'end', position, changes={'end_date': [None, str(end_date)]}, view_name='mod_end_position_history')
        messages.success(request, f"Ended {position.position_title} for {position.user_profile.user.username}.")
        return redirect('moderator:position_dashboard')

    context = {'position': position}
    return render(request, 'positions/end.html', context)


# ============================================================================
# USER MANAGEMENT (wires up the previously-unused can_manage_users permission)
# ============================================================================

@login_required
def user_dashboard(request):
    """List users for mod editing of their profile (party, riding, role, bio)."""
    if not can_manage_users(request.user):
        messages.error(request, "You don't have permission to manage users.")
        return redirect('moderator:dashboard')

    profiles = UserProfile.objects.all().select_related('user', 'party', 'riding').order_by('user__username')

    search = request.GET.get('q', '').strip()
    if search:
        profiles = profiles.filter(user__username__icontains=search)

    context = {
        'profiles': profiles,
        'search': search,
    }
    return render(request, 'users/dashboard.html', context)


@login_required
def mod_edit_user_profile(request, profile_id):
    """Edit a user's party, riding, role, and bio. Does NOT expose moderator
    permission flags - those stay staff-only, via Django admin."""
    if not can_manage_users(request.user):
        messages.error(request, "You don't have permission to manage users.")
        return redirect('moderator:dashboard')

    profile = get_object_or_404(UserProfile, pk=profile_id)

    if request.method == 'POST':
        before = {f: str(getattr(profile, f)) for f in ['party_id', 'riding_id', 'role', 'bio']}

        party_id = request.POST.get('party')
        riding_id = request.POST.get('riding')
        profile.party = PoliticalParty.objects.filter(pk=party_id).first() if party_id else None
        profile.riding = Riding.objects.filter(pk=riding_id).first() if riding_id else None
        profile.role = request.POST.get('role', profile.role).strip()
        profile.bio = request.POST.get('bio', profile.bio).strip()

        profile.save()
        changes = diff_fields(profile, ['party_id', 'riding_id', 'role', 'bio'], before)
        log_action(request.user, 'update', profile, changes=changes, view_name='mod_edit_user_profile')
        messages.success(request, f"Updated {profile.user.username}'s profile.")
        return redirect('moderator:user_dashboard')

    context = {
        'profile': profile,
        'parties': PoliticalParty.objects.all(),
        'ridings': Riding.objects.all().order_by('name'),
    }
    return render(request, 'users/edit.html', context)


# ============================================================================
# BILL/VOTE FIXES (mod-only correction tools, gated on can_manage_bills)
# ============================================================================

@login_required
def mod_force_close_vote(request, vote_id):
    """Force-close a stuck active vote without waiting for closes_at."""
    if not can_manage_bills(request.user):
        messages.error(request, "You don't have permission to manage bills.")
        return redirect('moderator:dashboard')

    vote = get_object_or_404(Vote, pk=vote_id)

    if request.method == 'POST':
        vote.is_active = False
        vote.closes_at = timezone.now()
        vote.save()
        log_action(request.user, 'update', vote, changes={'is_active': [True, False]}, view_name='mod_force_close_vote')
        messages.success(request, f"Force-closed vote on {vote.bill.bill_number}. Result: {vote.result()}.")

    return redirect('moderator:bill_dashboard')


@login_required
def mod_delete_ballot(request, ballot_id):
    """Remove a single bad/duplicate ballot from a vote."""
    if not can_manage_bills(request.user):
        messages.error(request, "You don't have permission to manage bills.")
        return redirect('moderator:dashboard')

    ballot = get_object_or_404(Ballot, pk=ballot_id)

    if request.method == 'POST':
        vote_id = ballot.vote_session_id
        log_action(
            request.user, 'delete', ballot, view_name='mod_delete_ballot',
            changes={'voter': ballot.voter.username, 'vote': ballot.vote},
        )
        ballot.delete()
        messages.success(request, "Ballot removed.")
        return redirect('voting:vote_results', vote_id)

    return redirect('moderator:bill_dashboard')


# ============================================================================
# AUDIT LOG
# ============================================================================

@login_required
def audit_log(request):
    """Read-only log of every change made through the moderator tools."""
    if not (request.user.is_staff or can_manage_users(request.user)):
        messages.error(request, "You don't have permission to view the audit log.")
        return redirect('moderator:dashboard')

    from django.core.paginator import Paginator
    from .models import AuditLog as AuditLogModel

    entries = AuditLogModel.objects.select_related('actor').all()

    actor = request.GET.get('actor', '').strip()
    if actor:
        entries = entries.filter(actor__username__icontains=actor)

    action = request.GET.get('action', '').strip()
    if action:
        entries = entries.filter(action=action)

    target_type = request.GET.get('target_type', '').strip()
    if target_type:
        entries = entries.filter(target_type__icontains=target_type)

    paginator = Paginator(entries, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'actor': actor,
        'action': action,
        'target_type': target_type,
        'action_choices': AuditLogModel.ACTION_CHOICES,
    }
    return render(request, 'audit/dashboard.html', context)
