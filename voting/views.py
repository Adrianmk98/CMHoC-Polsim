from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Bill, Vote, Ballot, PlayerHistory, BillDebatePost
from .forms import BillForm, VoteForm, BallotForm


def _active_score_session():
    try:
        from scores.models import ParliamentSession
        return ParliamentSession.objects.filter(is_active=True).first()
    except Exception:
        return None


def bill_list(request):
    """List all bills"""
    status_filter = request.GET.get('status', '')
    chamber_filter = request.GET.get('chamber', '')
    
    bills = Bill.objects.all().select_related('sponsor', 'sponsor__profile')
    
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
    from moderator.permissions import can_manage_bills, is_sitting_member

    bill = get_object_or_404(Bill.objects.select_related('sponsor', 'sponsor__profile__party'), pk=bill_id)
    current_vote = bill.current_vote()

    can_second_bill = (
        bill.status == 'DRAFT'
        and not bill.seconder
        and request.user.is_authenticated
        and request.user != bill.sponsor
        and is_sitting_member(request.user, bill.chamber)
    )

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
        'active_score_session': _active_score_session(),
        'debate_posts': bill.debate_posts.all().select_related('author', 'author__profile__party'),
        'active_stages': Bill.STATUS_CHOICES,
        'can_edit_bill': request.user == bill.sponsor or can_manage_bills(request.user),
        'can_second_bill': can_second_bill,
    }
    return render(request, 'bill_detail.html', context)


@login_required
def add_debate_post(request, bill_id):
    """Post a debate comment on the current reading stage of a bill."""
    bill = get_object_or_404(Bill, pk=bill_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content and bill.status not in ('ROYAL_ASSENT', 'FAILED', 'DRAFT'):
            BillDebatePost.objects.create(
                bill=bill,
                reading_stage=bill.status,
                author=request.user,
                content=content,
            )
            messages.success(request, 'Your debate post was submitted.')
        elif not content:
            messages.error(request, 'Post cannot be empty.')
        else:
            messages.error(request, 'Debate is not open at this stage.')
    return redirect('voting:bill_detail', bill_id=bill.id)


@login_required
def cast_vote(request, vote_id):
    """Cast a vote on an open vote session"""
    from moderator.permissions import can_manage_bills, is_sitting_member

    vote_session = get_object_or_404(Vote, pk=vote_id)

    if not vote_session.is_open():
        messages.error(request, 'This vote is closed.')
        return redirect('voting:bill_detail', bill_id=vote_session.bill.id)

    if not (is_sitting_member(request.user, vote_session.bill.chamber) or can_manage_bills(request.user)):
        chamber_label = 'Senators' if vote_session.bill.chamber == 'SENATE' else 'MPs'
        messages.error(request, f'Only sitting {chamber_label} can vote on this bill.')
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
    vote_session = get_object_or_404(Vote.objects.select_related('created_by', 'created_by__profile'), pk=vote_id)
    ballots = vote_session.ballot_set.all().select_related('voter', 'voter__profile', 'voter__profile__party')
    
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
    """Create a new bill. Anyone can author a bill, but it starts life as a
    Draft unless the author is a sitting member (or moderator) who can push
    it straight to a reading."""
    from moderator.permissions import can_manage_bills, is_sitting_member

    if request.method == 'POST':
        form = BillForm(request.POST, request.FILES)
        if form.is_valid():
            bill = form.save(commit=False)
            bill.sponsor = request.user
            if bill.status != 'DRAFT' and not (can_manage_bills(request.user) or is_sitting_member(request.user, bill.chamber)):
                bill.status = 'DRAFT'
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
def second_bill(request, bill_id):
    """Let a sitting member mark themselves as a bill's seconder while it's
    still in Draft (or withdraw their own seconding)."""
    from moderator.permissions import is_sitting_member

    bill = get_object_or_404(Bill, pk=bill_id)

    if request.method != 'POST':
        return redirect('voting:bill_detail', bill_id=bill.id)

    if bill.status != 'DRAFT':
        messages.error(request, 'A bill can only be seconded while it is in Draft.')
        return redirect('voting:bill_detail', bill_id=bill.id)

    if bill.seconder_id == request.user.id:
        bill.seconder = None
        bill.save(update_fields=['seconder'])
        messages.success(request, 'You withdrew your seconding of this bill.')
        return redirect('voting:bill_detail', bill_id=bill.id)

    if bill.seconder_id:
        messages.error(request, 'This bill already has a seconder.')
        return redirect('voting:bill_detail', bill_id=bill.id)

    if request.user == bill.sponsor:
        messages.error(request, "You can't second your own bill.")
        return redirect('voting:bill_detail', bill_id=bill.id)

    if not is_sitting_member(request.user, bill.chamber):
        chamber_label = 'Senator' if bill.chamber == 'SENATE' else 'MP'
        messages.error(request, f'Only a sitting {chamber_label} can second this bill.')
        return redirect('voting:bill_detail', bill_id=bill.id)

    bill.seconder = request.user
    bill.save(update_fields=['seconder'])
    messages.success(request, 'You are now seconding this bill.')
    return redirect('voting:bill_detail', bill_id=bill.id)


@login_required
def edit_bill(request, bill_id):
    """Edit a bill - sponsor or a moderator with bill-management rights only.
    Anyone can author/edit the text, but only a sitting member of the chamber
    (or a moderator) can move the bill to a new stage."""
    from moderator.permissions import can_manage_bills, is_sitting_member

    bill = get_object_or_404(Bill, pk=bill_id)
    if not (request.user == bill.sponsor or can_manage_bills(request.user)):
        messages.error(request, "You don't have permission to edit this bill.")
        return redirect('voting:bill_detail', bill_id=bill.id)

    can_advance_stage = can_manage_bills(request.user) or is_sitting_member(request.user, bill.chamber)
    original_status = bill.status

    if request.method == 'POST':
        form = BillForm(request.POST, request.FILES, instance=bill)
        if form.is_valid():
            if bill.status != original_status and not can_advance_stage:
                bill.status = original_status
                messages.error(request, 'Only a sitting member of this chamber can move a bill to a new stage.')
                return render(request, 'edit_bill.html', {'form': form, 'bill': bill})
            form.save()
            messages.success(request, f'Bill {bill.bill_number} updated successfully!')
            return redirect('voting:bill_detail', bill_id=bill.id)
    else:
        form = BillForm(instance=bill)

    context = {'form': form, 'bill': bill}
    return render(request, 'edit_bill.html', context)


@login_required
def create_vote(request, bill_id):
    """Create a vote session for a bill (admin/speaker only)"""
    from moderator.permissions import can_manage_bills, is_speaker

    bill = get_object_or_404(Bill, pk=bill_id)

    if not (can_manage_bills(request.user) or is_speaker(request.user)):
        messages.error(request, 'Only the Speaker or a bill moderator can open a vote session.')
        return redirect('voting:bill_detail', bill_id=bill.id)

    if not bill.seconder:
        messages.error(request, 'This bill needs a seconder before a vote can be opened.')
        return redirect('voting:bill_detail', bill_id=bill.id)

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