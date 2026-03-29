from django.db import models
from django.contrib.auth.models import User
from forum.models import Riding, UserProfile, PoliticalParty


class Election(models.Model):
    """Federal elections or by-elections"""
    ELECTION_TYPES = [
        ('FEDERAL', 'Federal Election'),
        ('BY_ELECTION', 'By-Election'),
    ]
    
    name = models.CharField(max_length=200)  # e.g., "2024 Federal Election", "Toronto Centre By-Election 2024"
    election_type = models.CharField(max_length=20, choices=ELECTION_TYPES)
    election_date = models.DateField()
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    
    # For by-elections only - which riding
    riding = models.ForeignKey(Riding, on_delete=models.SET_NULL, null=True, blank=True, related_name='byelections')
    
    # Summary statistics (auto-calculated or manually set)
    total_seats = models.IntegerField(default=0)
    total_votes_cast = models.IntegerField(default=0)
    total_registered_voters = models.IntegerField(null=True, blank=True)
    voter_turnout = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Percentage
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-election_date']
    
    def __str__(self):
        return f"{self.name} ({self.election_date.year})"
    
    def is_federal(self):
        return self.election_type == 'FEDERAL'
    
    def is_by_election(self):
        return self.election_type == 'BY_ELECTION'
    
    def get_results(self):
        """Get all riding results for this election"""
        return self.riding_results.all().select_related('riding', 'winner', 'winner__party')
    
    def calculate_seat_totals(self):
        """Calculate seats won by each party"""
        from django.db.models import Count, Q
        
        # Get seat counts by party
        seat_data = {}
        
        for result in self.riding_results.filter(winner__isnull=False):
            party = result.winning_party
            party_name = party.get_name_display() if party else "Independent"
            party_color = party.color if party else "#808080"
            
            if party_name not in seat_data:
                seat_data[party_name] = {
                    'party': party,
                    'party_name': party_name,
                    'party_color': party_color,
                    'seats': 0,
                    'votes': 0,
                }
            
            seat_data[party_name]['seats'] += 1
            seat_data[party_name]['votes'] += result.total_votes_cast
        
        # Sort by seats
        sorted_data = sorted(seat_data.values(), key=lambda x: x['seats'], reverse=True)
        
        return sorted_data
    
    def get_winning_party(self):
        """Get party with most seats"""
        totals = self.calculate_seat_totals()
        if totals:
            return totals[0]
        return None
    
    def calculate_totals(self):
        """Calculate and update election totals"""
        results = self.riding_results.all()
        
        self.total_seats = results.filter(winner__isnull=False).count()
        self.total_votes_cast = sum(r.total_votes_cast for r in results)
        
        if self.total_registered_voters and self.total_votes_cast:
            self.voter_turnout = (self.total_votes_cast / self.total_registered_voters) * 100
        
        self.save()


class RidingElectionResult(models.Model):
    """Results for a specific riding in an election"""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='riding_results')
    riding = models.ForeignKey(Riding, on_delete=models.CASCADE, related_name='election_results')
    
    # Winner
    winner = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='elections_won')
    winning_party = models.ForeignKey(PoliticalParty, on_delete=models.SET_NULL, null=True, blank=True, related_name='ridings_won')
    
    # Vote counts
    total_votes_cast = models.IntegerField(default=0)
    total_registered_voters = models.IntegerField(null=True, blank=True)
    turnout_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Metadata
    is_acclaimed = models.BooleanField(default=False)  # Won without opposition
    notes = models.TextField(blank=True)
    
    # Previous winner (for comparison)
    previous_winner = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_elections')
    previous_party = models.ForeignKey(PoliticalParty, on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_ridings')
    
    class Meta:
        ordering = ['riding__name']
        unique_together = ['election', 'riding']
    
    def __str__(self):
        winner_name = self.winner.user.username if self.winner else "No winner yet"
        return f"{self.riding.name} - {self.election.name}: {winner_name}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate turnout
        if self.total_registered_voters and self.total_votes_cast:
            self.turnout_percentage = (self.total_votes_cast / self.total_registered_voters) * 100
        
        # Set winning party from winner
        if self.winner and not self.winning_party:
            self.winning_party = self.winner.party
        
        super().save(*args, **kwargs)
    
    def get_margin_of_victory(self):
        """Calculate margin between first and second place"""
        candidates = self.candidate_results.order_by('-votes')
        if candidates.count() >= 2:
            first = candidates[0].votes
            second = candidates[1].votes
            return first - second
        return None
    
    def get_winning_percentage(self):
        """Get winner's vote percentage"""
        if self.winner and self.total_votes_cast > 0:
            winner_result = self.candidate_results.filter(candidate=self.winner).first()
            if winner_result:
                return (winner_result.votes / self.total_votes_cast) * 100
        return None
    
    def is_party_hold(self):
        """Check if same party won as previous election"""
        if self.winning_party and self.previous_party:
            return self.winning_party == self.previous_party
        return None
    
    def is_party_gain(self):
        """Check if this is a gain for the winning party"""
        if self.winning_party and self.previous_party:
            return self.winning_party != self.previous_party
        return None


class CandidateResult(models.Model):
    """Individual candidate results in a riding election"""
    riding_result = models.ForeignKey(RidingElectionResult, on_delete=models.CASCADE, related_name='candidate_results')
    candidate = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='election_candidacies')
    party = models.ForeignKey(PoliticalParty, on_delete=models.SET_NULL, null=True, blank=True)
    
    votes = models.IntegerField(default=0)
    vote_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_winner = models.BooleanField(default=False)
    
    # Additional info
    is_incumbent = models.BooleanField(default=False)  # Was the sitting MP
    votes_previous = models.IntegerField(null=True, blank=True)  # Votes in previous election in this riding
    
    class Meta:
        ordering = ['-votes']
        unique_together = ['riding_result', 'candidate']
    
    def __str__(self):
        party_name = self.party.get_name_display() if self.party else "Independent"
        return f"{self.candidate.user.username} ({party_name}) - {self.votes} votes"
    
    def save(self, *args, **kwargs):
        # Auto-calculate vote percentage
        if self.riding_result.total_votes_cast > 0:
            self.vote_percentage = (self.votes / self.riding_result.total_votes_cast) * 100
        
        super().save(*args, **kwargs)
    
    def vote_swing(self):
        """Calculate swing from previous election"""
        if self.votes_previous:
            return self.votes - self.votes_previous
        return None
    
    def percentage_change(self):
        """Calculate percentage point change from previous election"""
        if self.votes_previous and self.riding_result.total_votes_cast > 0:
            old_percentage = (self.votes_previous / self.riding_result.total_votes_cast) * 100
            return self.vote_percentage - old_percentage if self.vote_percentage else None
        return None