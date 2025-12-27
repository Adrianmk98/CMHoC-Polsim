from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import (
    Party, PartyMembership, PartyRole, LeadershipElection,
    LeadershipCandidate, LeadershipVote, ConfidenceVote,
    ConfidenceBallot, JoinRequest
)
from .forms import (
    PartyForm, LeadershipElectionForm, ConfidenceVoteForm,
    LeadershipCandidateForm, JoinRequestForm
)


def party_list(request):
    """List all active parties"""
    parties = Party.objects.filter(is_active=True).prefetch_related('members')
    
    context = {
        'parties': parties,
    }
    return render(request, 'party_list.html', context)


def party_detail(request, pk):
    """View party details"""
    party = get_object_or_404(Party, pk=pk)
    
    # Get members
    members = party.get_members()
    
    # Get leadership
    leadership = party.get_leadership()
    
    # Get active elections/votes
    active_election = LeadershipElection.objects.filter(
        party=party,
        is_active=True,
        closes_at__gt=timezone.now()
    ).first()
    
    active_confidence = ConfidenceVote.objects.filter(
        party=party,
        is_active=True,
        closes_at__gt=timezone.now()
    ).first()
    
    # Check user membership
    is_member = False
    user_membership = None
    can_manage = False
    
    if request.user.is_authenticated:
        user_membership = PartyMembership.objects.filter(
            user=request.user,
            party=party,
            is_active=True
        ).first()
        is_member = user_membership is not None
        can_manage = party.can_user_manage(request.user)
    
    # Check pending join request
    pending_request = None
    if request.user.is_authenticated and not is_member:
        pending_request = JoinRequest.objects.filter(
            user=request.user,
            party=party,
            status='PENDING'
        ).first()
    
    context = {
        'party': party,
        'members': members,
        'leadership': leadership,
        'active_election': active_election,
        'active_confidence': active_confidence,
        'is_member': is_member,
        'can_manage': can_manage,
        'pending_request': pending_request,
    }
    return render(request, 'party_detail.html', context)


@login_required
def create_party(request):
    """Create a new party"""
    if request.method == 'POST':
        form = PartyForm(request.POST)
        if form.is_valid():
            party = form.save(commit=False)
            party.save()
            
            # Create founding membership
            membership = PartyMembership.objects.create(
                user=request.user,
                party=party,
                is_founding_member=True,
                is_active=True
            )
            
            # Create founding leadership election
            election = LeadershipElection.objects.create(
                party=party,
                title=f"Founding Leadership Election - {party.name}",
                trigger='FOUNDING',
                closes_at=timezone.now() + timedelta(days=7)
            )
            
            # Add founder as candidate
            LeadershipCandidate.objects.create(
                election=election,
                user=request.user,
                platform="Founding member"
            )
            
            messages.success(request, f'Party "{party.name}" created! A founding leadership election has been started.')
            return redirect('parties:detail', pk=party.pk)
    else:
        form = PartyForm()
    
    context = {
        'form': form,
    }
    return render(request, 'create.html', context)


@login_required
def join_party(request, pk):
    """Request to join a party"""
    party = get_object_or_404(Party, pk=pk)
    
    # Check if already a member
    if PartyMembership.objects.filter(user=request.user, party=party, is_active=True).exists():
        messages.error(request, 'You are already a member of this party.')
        return redirect('parties:detail', pk=pk)
    
    # Check if already has pending request
    if JoinRequest.objects.filter(user=request.user, party=party, status='PENDING').exists():
        messages.error(request, 'You already have a pending join request.')
        return redirect('parties:detail', pk=pk)
    
    if request.method == 'POST':
        form = JoinRequestForm(request.POST)
        if form.is_valid():
            join_request = form.save(commit=False)
            join_request.user = request.user
            join_request.party = party
            join_request.save()
            
            messages.success(request, f'Join request sent to {party.name}. You will be notified when reviewed.')
            return redirect('parties:detail', pk=pk)
    else:
        form = JoinRequestForm()
    
    context = {
        'party': party,
        'form': form,
    }
    return render(request, 'join.html', context)


@login_required
def leave_party(request, pk):
    """Leave a party"""
    party = get_object_or_404(Party, pk=pk)
    
    membership = get_object_or_404(PartyMembership, user=request.user, party=party, is_active=True)
    
    if request.method == 'POST':
        # Check if user is leader
        if party.leader == request.user:
            messages.error(request, 'You cannot leave while you are party leader. Resign from leadership first.')
            return redirect('parties:detail', pk=pk)
        
        membership.leave_party()
        messages.success(request, f'You have left {party.name}.')
        return redirect('parties:party_list')
    
    context = {
        'party': party,
    }
    return render(request, 'leave_confirm.html', context)


@login_required
def manage_join_requests(request, pk):
    """Manage join requests (leaders only)"""
    party = get_object_or_404(Party, pk=pk)
    
    if not party.can_user_manage(request.user):
        messages.error(request, 'Only party leadership can manage join requests.')
        return redirect('parties:detail', pk=pk)
    
    pending_requests = JoinRequest.objects.filter(
        party=party,
        status='PENDING'
    ).select_related('user')
    
    context = {
        'party': party,
        'pending_requests': pending_requests,
    }
    return render(request, 'join_requests.html', context)


@login_required
def approve_join_request(request, pk):
    """Approve a join request"""
    join_request = get_object_or_404(JoinRequest, pk=pk)
    
    if not join_request.party.can_user_manage(request.user):
        messages.error(request, 'Only party leadership can approve requests.')
        return redirect('parties:detail', pk=join_request.party.pk)
    
    join_request.approve(request.user)
    messages.success(request, f'{join_request.user.username} has been added to the party.')
    
    return redirect('parties:manage_requests', pk=join_request.party.pk)


@login_required
def reject_join_request(request, pk):
    """Reject a join request"""
    join_request = get_object_or_404(JoinRequest, pk=pk)
    
    if not join_request.party.can_user_manage(request.user):
        messages.error(request, 'Only party leadership can reject requests.')
        return redirect('parties:detail', pk=join_request.party.pk)
    
    join_request.reject(request.user)
    messages.success(request, f'{join_request.user.username}\'s request has been rejected.')
    
    return redirect('parties:manage_requests', pk=join_request.party.pk)


# ============================================================================
# LEADERSHIP ELECTIONS
# ============================================================================

def leadership_election_detail(request, pk):
    """View leadership election details"""
    election = get_object_or_404(LeadershipElection, pk=pk)
    
    candidates = election.get_candidates()
    
    # Add vote counts
    for candidate in candidates:
        candidate.vote_count = candidate.get_vote_count()
    
    # Check if user can vote
    can_vote = False
    if request.user.is_authenticated:
        can_vote = election.can_vote(request.user)
    
    context = {
        'election': election,
        'candidates': candidates,
        'can_vote': can_vote,
    }
    return render(request, 'election_detail.html', context)


@login_required
def nominate_for_leadership(request, election_id):
    """Nominate yourself for leadership"""
    election = get_object_or_404(LeadershipElection, pk=election_id)
    
    # Check if user is party member
    if not PartyMembership.objects.filter(user=request.user, party=election.party, is_active=True).exists():
        messages.error(request, 'You must be a party member to run for leadership.')
        return redirect('parties:election_detail', pk=election_id)
    
    # Check if already nominated
    if LeadershipCandidate.objects.filter(election=election, user=request.user).exists():
        messages.error(request, 'You are already nominated.')
        return redirect('parties:election_detail', pk=election_id)
    
    if request.method == 'POST':
        form = LeadershipCandidateForm(request.POST)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.election = election
            candidate.user = request.user
            candidate.save()
            
            messages.success(request, 'You have been nominated for party leadership!')
            return redirect('parties:election_detail', pk=election_id)
    else:
        form = LeadershipCandidateForm()
    
    context = {
        'election': election,
        'form': form,
    }
    return render(request, 'nominate.html', context)


@login_required
def vote_in_election(request, election_id, candidate_id):
    """Cast vote in leadership election"""
    election = get_object_or_404(LeadershipElection, pk=election_id)
    candidate = get_object_or_404(LeadershipCandidate, pk=candidate_id, election=election)
    
    if not election.can_vote(request.user):
        messages.error(request, 'You cannot vote in this election.')
        return redirect('parties:election_detail', pk=election_id)
    
    # Cast vote
    LeadershipVote.objects.create(
        election=election,
        candidate=candidate,
        voter=request.user
    )
    
    messages.success(request, f'Vote cast for {candidate.user.username}!')
    return redirect('parties:election_detail', pk=election_id)


@login_required
def close_election(request, pk):
    """Close and calculate election results (admin/leader only)"""
    election = get_object_or_404(LeadershipElection, pk=pk)
    
    if not (request.user.is_staff or election.party.can_user_manage(request.user)):
        messages.error(request, 'Only party leadership can close elections.')
        return redirect('parties:election_detail', pk=pk)
    
    election.calculate_results()
    messages.success(request, f'Election closed. {election.winner.username} is the new party leader!')
    
    return redirect('parties:detail', pk=election.party.pk)


# ============================================================================
# CONFIDENCE VOTES
# ============================================================================

@login_required
def initiate_confidence_vote(request, pk):
    """Initiate a vote of no confidence"""
    party = get_object_or_404(Party, pk=pk)
    
    # Check if user is party member
    if not PartyMembership.objects.filter(user=request.user, party=party, is_active=True).exists():
        messages.error(request, 'You must be a party member to initiate a confidence vote.')
        return redirect('parties:detail', pk=pk)
    
    # Check if party has a leader
    if not party.leader:
        messages.error(request, 'This party has no leader.')
        return redirect('parties:detail', pk=pk)
    
    # Check if there's already an active confidence vote
    if party.has_active_confidence_vote():
        messages.error(request, 'There is already an active confidence vote.')
        return redirect('parties:detail', pk=pk)
    
    if request.method == 'POST':
        form = ConfidenceVoteForm(request.POST)
        if form.is_valid():
            confidence_vote = form.save(commit=False)
            confidence_vote.party = party
            confidence_vote.target_leader = party.leader
            confidence_vote.initiated_by = request.user
            confidence_vote.closes_at = timezone.now() + timedelta(days=3)
            confidence_vote.save()
            
            messages.success(request, 'Vote of no confidence has been initiated.')
            return redirect('parties:confidence_vote_detail', pk=confidence_vote.pk)
    else:
        form = ConfidenceVoteForm()
    
    context = {
        'party': party,
        'form': form,
    }
    return render(request, 'confidence_vote_create.html', context)


def confidence_vote_detail(request, pk):
    """View confidence vote details"""
    confidence_vote = get_object_or_404(ConfidenceVote, pk=pk)
    
    # Check if user can vote
    can_vote = False
    if request.user.is_authenticated:
        can_vote = confidence_vote.can_vote(request.user)
    
    context = {
        'confidence_vote': confidence_vote,
        'can_vote': can_vote,
    }
    return render(request, 'confidence_vote_detail.html', context)


@login_required
def cast_confidence_vote(request, pk, vote):
    """Cast vote in confidence vote"""
    confidence_vote = get_object_or_404(ConfidenceVote, pk=pk)
    
    if not confidence_vote.can_vote(request.user):
        messages.error(request, 'You cannot vote in this confidence vote.')
        return redirect('parties:confidence_vote_detail', pk=pk)
    
    if vote not in ['CONFIDENCE', 'NO_CONFIDENCE']:
        messages.error(request, 'Invalid vote.')
        return redirect('parties:confidence_vote_detail', pk=pk)
    
    # Cast vote
    ConfidenceBallot.objects.create(
        confidence_vote=confidence_vote,
        voter=request.user,
        vote=vote
    )
    
    messages.success(request, 'Your vote has been recorded!')
    return redirect('parties:confidence_vote_detail', pk=pk)


@login_required
def close_confidence_vote(request, pk):
    """Close and calculate confidence vote results"""
    confidence_vote = get_object_or_404(ConfidenceVote, pk=pk)
    
    if not (request.user.is_staff or confidence_vote.party.can_user_manage(request.user)):
        messages.error(request, 'Only party leadership can close confidence votes.')
        return redirect('parties:confidence_vote_detail', pk=pk)
    
    confidence_vote.calculate_results()
    
    if confidence_vote.result == 'PASSED':
        messages.warning(request, f'No confidence vote passed. Leadership election has been triggered.')
    else:
        messages.success(request, f'No confidence vote failed. {confidence_vote.target_leader.username} remains party leader.')
    
    return redirect('parties:detail', pk=confidence_vote.party.pk)