from django.shortcuts import render, get_object_or_404
from django.db.models import Sum, Count
from .models import Election, RidingElectionResult, CandidateResult


def election_list(request):
    """List all elections"""
    elections = Election.objects.all()
    
    # Separate federal and by-elections
    federal_elections = elections.filter(election_type='FEDERAL')
    by_elections = elections.filter(election_type='BY_ELECTION')
    
    context = {
        'federal_elections': federal_elections,
        'by_elections': by_elections,
    }
    return render(request, 'election_list.html', context)


def election_detail(request, election_id):
    """Detailed view of an election with all results"""
    election = get_object_or_404(Election, pk=election_id)
    
    # Get all riding results
    riding_results = election.riding_results.all().select_related(
        'riding', 'winner', 'winner__party', 'winning_party'
    ).prefetch_related('riding__provinces').order_by('riding__name')
    
    # Get seat totals by party
    seat_totals = election.calculate_seat_totals()
    
    # Group results by province
    results_by_province = {}
    for result in riding_results:
        province = str(result.riding.provinces.first()) if result.riding.provinces.exists() else 'Unknown'
        if province not in results_by_province:
            results_by_province[province] = []
        results_by_province[province].append(result)
    
    # Calculate statistics
    total_votes = sum(r.total_votes_cast for r in riding_results)
    completed_ridings = riding_results.filter(winner__isnull=False).count()
    total_ridings = riding_results.count()
    
    context = {
        'election': election,
        'riding_results': riding_results,
        'results_by_province': results_by_province,
        'seat_totals': seat_totals,
        'total_votes': total_votes,
        'completed_ridings': completed_ridings,
        'total_ridings': total_ridings,
    }
    return render(request, 'election_detail.html', context)


def riding_result_detail(request, result_id):
    """Detailed results for a specific riding in an election"""
    riding_result = get_object_or_404(RidingElectionResult, pk=result_id)
    
    # Get all candidates
    candidates = riding_result.candidate_results.all().select_related('candidate__user', 'party')
    
    # Get historical results for this riding
    historical_results = RidingElectionResult.objects.filter(
        riding=riding_result.riding
    ).exclude(pk=result_id).select_related('election', 'winner', 'winning_party').order_by('-election__election_date')
    
    context = {
        'riding_result': riding_result,
        'candidates': candidates,
        'historical_results': historical_results,
    }
    return render(request, 'riding_result_detail.html', context)


def riding_election_history(request, riding_id):
    """Complete election history for a specific riding"""
    from forum.models import Riding
    
    riding = get_object_or_404(Riding, pk=riding_id)
    
    # Get all election results for this riding
    results = RidingElectionResult.objects.filter(
        riding=riding
    ).select_related('election', 'winner', 'winner__party', 'winning_party').order_by('-election__election_date')
    
    # Get party history (who won when)
    party_timeline = []
    for result in results:
        if result.winner:
            party_timeline.append({
                'election': result.election,
                'winner': result.winner,
                'party': result.winning_party,
                'votes': result.total_votes_cast,
                'turnout': result.turnout_percentage,
            })
    
    context = {
        'riding': riding,
        'results': results,
        'party_timeline': party_timeline,
    }
    return render(request, 'riding_history.html', context)


def compare_elections(request):
    """Compare two or more elections"""
    election_ids = request.GET.getlist('elections')
    
    if not election_ids:
        # Show selection page
        all_elections = Election.objects.filter(election_type='FEDERAL', is_completed=True)
        context = {'all_elections': all_elections}
        return render(request, 'compare_select.html', context)
    
    # Get selected elections
    elections = Election.objects.filter(id__in=election_ids).order_by('election_date')
    
    if elections.count() < 2:
        context = {'error': 'Please select at least 2 elections to compare'}
        return render(request, 'compare_select.html', context)
    
    # Build comparison data
    comparison_data = {}
    
    for election in elections:
        seat_totals = election.calculate_seat_totals()
        comparison_data[election.id] = {
            'election': election,
            'seat_totals': seat_totals,
        }
    
    context = {
        'elections': elections,
        'comparison_data': comparison_data,
    }
    return render(request, 'compare_elections.html', context)


def party_election_history(request, party_id):
    """Show a party's performance across all elections"""
    from forum.models import PoliticalParty
    
    party = get_object_or_404(PoliticalParty, pk=party_id)
    
    # Get all elections where party won seats
    elections_data = []
    
    for election in Election.objects.filter(election_type='FEDERAL', is_completed=True).order_by('-election_date'):
        seats_won = election.riding_results.filter(winning_party=party).count()
        total_votes = sum(
            cr.votes for cr in CandidateResult.objects.filter(
                riding_result__election=election,
                party=party
            )
        )
        
        if seats_won > 0 or total_votes > 0:
            elections_data.append({
                'election': election,
                'seats': seats_won,
                'votes': total_votes,
            })
    
    context = {
        'party': party,
        'elections_data': elections_data,
    }
    return render(request, 'party_history.html', context)