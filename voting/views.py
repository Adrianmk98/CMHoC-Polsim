from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Bill, Vote, Ballot, PlayerHistory
from .forms import BillForm, VoteForm, BallotForm


def bill_list(request):
    """List all bills"""
    status_filter = request.GET.get('status', '')
    chamber_filter = request.GET.get('chamber', '')
    
    bills = Bill.objects.all()
    
    if status_filter:
        bills = bills.filter(status=status_filter)
    if chamber_filter:
        bills = bills.filter(chamber=chamber_filter)
    
    paginator = Paginator(bills, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'chamber_filter': chamber_filter,
        'status_choices': Bill.STATUS_CHOICES,
        'chamber_choices': Bill.CHAMBER_CHOICES,
    }
    return render(request, 'bill_list.html', context)


def bill_detail(request, bill_id):
    """View bill details and vote"""
    bill = get_object_or_404(Bill, pk=bill_id)
    current_vote = bill.current_vote()
    
    user_ballot = None
    if request.user.is_authenticated and current_vote:
        user_ballot = Ballot.objects.filter(
            vote_session=current_vote,
            voter=request.user
        ).first()
    
    context = {
        'bill': bill,
        'current_vote': current_vote,
        'user_ballot': user_ballot,
        'all_votes': bill.votes.all()[:5],
    }
    return render(request, 'bill_detail.html', context)


@login_required
def cast_vote(request, vote_id):
    """Cast a vote on an open vote session"""
    vote_session = get_object_or_404(Vote, pk=vote_id)
    
    if not vote_session.is_open():
        messages.error(request, 'This vote is closed.')
        return redirect('voting:bill_detail', bill_id=vote_session.bill.id)
    
    # Check if already voted
    existing = Ballot.objects.filter(
        vote_session=vote_session,
        voter=request.user
    ).first()
    
    if request.method == 'POST':
        form = BallotForm(request.POST, instance=existing)
        if form.is_valid():
            ballot = form.save(commit=False)
            ballot.vote_session = vote_session
            ballot.voter = request.user
            ballot.save()
            
            # Update player history
            history, created = PlayerHistory.objects.get_or_create(user=request.user)
            history.update_stats()
            
            messages.success(request, f'Your vote ({ballot.vote}) has been recorded!')
            return redirect('voting:bill_detail', bill_id=vote_session.bill.id)
    else:
        form = BallotForm(instance=existing)
    
    context = {
        'vote_session': vote_session,
        'form': form,
        'existing': existing,
    }
    return render(request, 'cast_vote.html', context)


def vote_results(request, vote_id):
    """View vote results"""
    vote_session = get_object_or_404(Vote, pk=vote_id)
    ballots = vote_session.ballot_set.all()
    
    # Group by vote choice
    yea_votes = ballots.filter(vote='YEA')
    nay_votes = ballots.filter(vote='NAY')
    abstain_votes = ballots.filter(vote='ABSTAIN')
    
    context = {
        'vote_session': vote_session,
        'yea_votes': yea_votes,
        'nay_votes': nay_votes,
        'abstain_votes': abstain_votes,
    }
    return render(request, 'vote_results.html', context)


@login_required
def create_bill(request):
    """Create a new bill"""
    if request.method == 'POST':
        form = BillForm(request.POST)
        if form.is_valid():
            bill = form.save(commit=False)
            bill.sponsor = request.user
            bill.save()
            
            # Update player history
            history, created = PlayerHistory.objects.get_or_create(user=request.user)
            history.update_stats()
            
            messages.success(request, f'Bill {bill.bill_number} created successfully!')
            return redirect('voting:bill_detail', bill_id=bill.id)
    else:
        form = BillForm()
    
    context = {'form': form}
    return render(request, 'create_bill.html', context)


@login_required
def create_vote(request, bill_id):
    """Create a vote session for a bill (admin/speaker only)"""
    bill = get_object_or_404(Bill, pk=bill_id)
    
    if request.method == 'POST':
        form = VoteForm(request.POST)
        if form.is_valid():
            vote = form.save(commit=False)
            vote.bill = bill
            vote.created_by = request.user
            vote.save()
            
            messages.success(request, 'Vote session opened!')
            return redirect('voting:bill_detail', bill_id=bill.id)
    else:
        form = VoteForm()
    
    context = {
        'form': form,
        'bill': bill,
    }
    return render(request, 'create_vote.html', context)