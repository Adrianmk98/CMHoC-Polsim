from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum
from .permissions import can_manage_elections, can_manage_cabinet, can_manage_bills, get_moderator_permissions
from elections.models import Election, RidingElectionResult, CandidateResult
from forum.models import Riding, UserProfile, PoliticalParty, Cabinet, CabinetPosition
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
    
    ridings = Riding.objects.all().order_by('province', 'name')
    
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
        ridings = Riding.objects.all().order_by('province', 'name')
    
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
    
    cabinets = Cabinet.objects.all().order_by('-start_date')
    current_cabinet = Cabinet.objects.filter(is_current=True).first()
    
    context = {
        'cabinets': cabinets,
        'current_cabinet': current_cabinet,
    }
    return render(request, 'cabinet/dashboard.html', context)


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