from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum
from .permissions import can_manage_elections, can_manage_cabinet, can_manage_bills, can_manage_scores, get_moderator_permissions
from elections.models import Election, RidingElectionResult, CandidateResult
from forum.models import Riding, UserProfile, PoliticalParty, Cabinet, CabinetPosition, PositionHistory
from voting.models import Bill, Vote


@login_required
def moderator_dashboard(request):
    """Main moderator dashboard"""
    perms = get_moderator_permissions(request.user)
    
    if not perms['is_moderator']:
        messages.error(request, "You don't have permission to access moderator tools.")
        return redirect('forum_index')
    
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
        profile = request.user.profile
        debug_info['has_profile'] = True
        debug_info['profile_id'] = profile.id
        debug_info['is_moderator'] = profile.is_moderator
        debug_info['can_manage_elections'] = profile.can_manage_elections
        debug_info['can_manage_cabinet'] = profile.can_manage_cabinet
        debug_info['can_manage_bills'] = profile.can_manage_bills
        debug_info['can_manage_users'] = profile.can_manage_users
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
        
        messages.success(request, f"Election '{name}' created! Now add results.")
        return redirect('moderator:add_results', election_id=election.id)
    
    ridings = Riding.objects.all().order_by('name')
    
    context = {
        'ridings': ridings,
    }
    return render(request, 'elections/create.html', context)


@login_required
def add_results(request, election_id):
    """Add/edit results for an election"""
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
    ).select_related('riding', 'winner', 'winning_party')
    
    # Create lookup for existing results
    results_by_riding = {r.riding.id: r for r in existing_results}
    
    context = {
        'election': election,
        'ridings': ridings,
        'results_by_riding': results_by_riding,
        'parties': PoliticalParty.objects.all(),
        'users': UserProfile.objects.all().select_related('user', 'party').order_by('user__username'),
    }
    return render(request, 'elections/add_results.html', context)


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
                        'winner': winner,
                        'winning_party': winner.party if winner else None,
                        'total_votes_cast': result_data.get('total_votes', 0),
                        'is_acclaimed': result_data.get('is_acclaimed', False),
                    }
                )

                if winner:
                    # End any current MP position for this riding
                    PositionHistory.objects.filter(
                        position_type='MP',
                        riding_obj=riding,
                        end_date__isnull=True,
                    ).exclude(user_profile=winner).update(end_date=election.election_date)
                    # Create new MP position if not already current
                    PositionHistory.objects.get_or_create(
                        position_type='MP',
                        riding_obj=riding,
                        user_profile=winner,
                        end_date=None,
                        defaults={
                            'position_title': f'Member of Parliament for {riding.name}',
                            'start_date': election.election_date,
                        }
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

    cabinets = Cabinet.objects.all().order_by('-start_date').prefetch_related(
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
            Cabinet.objects.create(
                name=name,
                prime_minister=pm.user if pm else None,
                government_party=party,
                start_date=start_date,
                is_current=is_current,
                description=description,
            )
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
            CabinetPosition.objects.create(
                cabinet=cabinet,
                user_profile=profile,
                position_type=position_type,
                portfolio=portfolio,
                title=title,
                order=order,
                start_date=start_date,
                notes=notes,
            )
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
        profile_id = request.POST.get('user_profile')
        position.position_type = request.POST.get('position_type', position.position_type)
        position.portfolio = request.POST.get('portfolio', position.portfolio).strip()
        position.title = request.POST.get('title', position.title).strip()
        position.order = int(request.POST.get('order', position.order) or 0)
        position.notes = request.POST.get('notes', '').strip()

        if profile_id:
            position.user_profile = get_object_or_404(UserProfile, pk=profile_id)

        position.save()
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
    
    bills = Bill.objects.all().order_by('-created_at')
    active_votes = Vote.objects.filter(is_active=True)
    
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
    all_users = User.objects.filter(is_active=True).order_by('username')
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

    ScoreEntry.objects.create(
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
    entry.delete()
    messages.success(request, "Score entry deleted.")
    return redirect(f"{request.path.rsplit('/delete/', 1)[0].rsplit('/', 2)[0]}/player/{user_id}/?session={session_id}")