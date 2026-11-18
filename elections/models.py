from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from forum.models import Riding, UserProfile, PoliticalParty, Province, PositionHistory


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

    # Campaign timeline (all optional - an election with none set still works)
    nomination_deadline = models.DateField(null=True, blank=True)
    writ_date = models.DateField(null=True, blank=True)
    campaign_start_date = models.DateField(null=True, blank=True)
    results_certified_date = models.DateField(null=True, blank=True)

    # For by-elections only - which riding
    riding = models.ForeignKey(Riding, on_delete=models.SET_NULL, null=True, blank=True, related_name='byelections')

    # Polling simulation pipeline (see elections/polling.py)
    uses_list_seats = models.BooleanField(
        default=False,
        help_text="Whether this election awards proportional regional list seats on top of riding seats."
    )

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

    PHASE_PRE_WRIT = 'PRE_WRIT'
    PHASE_NOMINATIONS = 'NOMINATIONS'
    PHASE_CAMPAIGN = 'CAMPAIGN'
    PHASE_VOTING = 'VOTING'
    PHASE_CLOSED = 'CLOSED'

    PHASE_LABELS = {
        PHASE_PRE_WRIT: 'Pre-Writ',
        PHASE_NOMINATIONS: 'Nominations Open',
        PHASE_CAMPAIGN: 'Campaign Period',
        PHASE_VOTING: 'Voting Day',
        PHASE_CLOSED: 'Closed',
    }

    @property
    def phase(self):
        """Where this election currently sits in its lifecycle, based on its timeline dates."""
        today = timezone.now().date()

        if self.is_completed or (self.results_certified_date and today >= self.results_certified_date):
            return self.PHASE_CLOSED
        if today >= self.election_date:
            return self.PHASE_VOTING if today == self.election_date else self.PHASE_CLOSED
        if self.campaign_start_date and today >= self.campaign_start_date:
            return self.PHASE_CAMPAIGN
        if self.writ_date and today >= self.writ_date:
            return self.PHASE_NOMINATIONS
        return self.PHASE_PRE_WRIT

    def get_phase_display(self):
        return self.PHASE_LABELS[self.phase]

    def is_nomination_open(self):
        return self.phase == self.PHASE_NOMINATIONS

    def is_campaign_active(self):
        return self.phase == self.PHASE_CAMPAIGN

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

    def total_seats_with_list(self):
        """Seat totals per party, riding (FPTP) seats plus list seats if this election uses them."""
        totals = self.calculate_seat_totals()
        if not self.uses_list_seats:
            return totals

        by_party_name = {row['party_name']: row for row in totals}
        for list_seat in self.list_seats.select_related('party'):
            if list_seat.seats_won <= 0:
                continue
            party_name = list_seat.party.get_name_display() if list_seat.party else "Independent"
            row = by_party_name.get(party_name)
            if row is None:
                row = {
                    'party': list_seat.party,
                    'party_name': party_name,
                    'party_color': list_seat.party.color if list_seat.party else '#808080',
                    'seats': 0,
                    'votes': 0,
                }
                by_party_name[party_name] = row
                totals.append(row)
            row['seats'] += list_seat.seats_won

        totals.sort(key=lambda row: row['seats'], reverse=True)
        return totals
    
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
        
        # Set winning party from winner (winner.party is the real joinable party;
        # winning_party is the fixed real-world party enum, linked via Party.political_party)
        if self.winner and not self.winning_party and self.winner.party:
            self.winning_party = self.winner.party.political_party
        
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

    def set_winner(self, user_profile, party=None):
        """Declare user_profile as this riding's winner: sets winner/winning_party, and
        swaps the riding's MP PositionHistory over to them. Shared by manual entry
        (moderator bulk_add_results) and the score-driven polling pipeline.

        party: the PoliticalParty they won under, if already known (e.g. from their
        CandidateResult). Falls back to their party membership's linked real party."""
        self.winner = user_profile
        if party is not None:
            self.winning_party = party
        else:
            self.winning_party = user_profile.party.political_party if user_profile.party else None

        PositionHistory.objects.filter(
            position_type='MP',
            riding_obj=self.riding,
            end_date__isnull=True,
        ).exclude(user_profile=user_profile).update(end_date=self.election.election_date)

        PositionHistory.objects.get_or_create(
            position_type='MP',
            riding_obj=self.riding,
            user_profile=user_profile,
            end_date=None,
            defaults={
                'position_title': f'Member of Parliament for {self.riding.name}',
                'start_date': self.election.election_date,
            }
        )
        self.save()


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


class PartyModifier(models.Model):
    """Per-party, per-election inputs to the national polling calculation.

    `personal_mods_total` is auto-filled by polling.compute_party_modifiers() from the scores
    app. The rest are mod-entered, same as the source spreadsheet's Platform/Press/Attack
    Press/Gov-OO-C&S/Modifier Transfer columns.
    """
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='party_modifiers')
    party = models.ForeignKey(PoliticalParty, on_delete=models.CASCADE, related_name='party_modifiers')

    personal_mods_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    platform_score = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    press_score = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    attack_press_score = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    gov_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    modifier_transfer = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text="Net modifier transferred in (positive) or out (negative), e.g. coalition arrangements."
    )

    class Meta:
        unique_together = ['election', 'party']
        ordering = ['-personal_mods_total']

    def __str__(self):
        return f"{self.party.get_name_display()} modifier - {self.election.name}"

    @property
    def total_modifier(self):
        return (
            self.personal_mods_total + self.platform_score + self.press_score +
            self.attack_press_score + self.gov_bonus + self.modifier_transfer
        )


class NationalPoll(models.Model):
    """One party's national polling result for an election, including the random 'fuzz' step."""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='national_polls')
    party = models.ForeignKey(PoliticalParty, on_delete=models.CASCADE, related_name='national_polls')

    true_polling_pct = models.DecimalField(max_digits=8, decimal_places=6)
    random_number = models.DecimalField(max_digits=8, decimal_places=6)
    max_variance = models.DecimalField(max_digits=8, decimal_places=6)
    actual_variance = models.DecimalField(max_digits=8, decimal_places=6)
    fuzzed_pct = models.DecimalField(max_digits=8, decimal_places=6)
    corrected_pct = models.DecimalField(max_digits=8, decimal_places=6)

    class Meta:
        unique_together = ['election', 'party']
        ordering = ['-corrected_pct']

    def __str__(self):
        return f"{self.party.get_name_display()} - {self.corrected_pct * 100:.1f}% ({self.election.name})"


class RegionalPoll(models.Model):
    """A party's polling % within one region, for one election."""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='regional_polls')
    party = models.ForeignKey(PoliticalParty, on_delete=models.CASCADE, related_name='regional_polls')
    region = models.CharField(max_length=20, choices=Province.REGION_CHOICES)

    regional_pct = models.DecimalField(max_digits=8, decimal_places=6)

    class Meta:
        unique_together = ['election', 'party', 'region']
        ordering = ['region', '-regional_pct']

    def __str__(self):
        return f"{self.party.get_name_display()} - {self.get_region_display()} ({self.election.name})"


class ElectionRegionSeats(models.Model):
    """How many proportional list seats a region awards for an election. Only meaningful when
    election.uses_list_seats is True."""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='region_seat_configs')
    region = models.CharField(max_length=20, choices=Province.REGION_CHOICES)
    list_seats = models.IntegerField(default=0)

    class Meta:
        unique_together = ['election', 'region']
        ordering = ['region']

    def __str__(self):
        return f"{self.get_region_display()} - {self.list_seats} list seats ({self.election.name})"


class RegionalListSeat(models.Model):
    """A party's proportional list seats won in one region, from polling.allocate_list_seats()."""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='list_seats')
    party = models.ForeignKey(PoliticalParty, on_delete=models.CASCADE, related_name='list_seats')
    region = models.CharField(max_length=20, choices=Province.REGION_CHOICES)

    list_votes = models.IntegerField(default=0)
    seats_won = models.IntegerField(default=0)

    class Meta:
        unique_together = ['election', 'party', 'region']
        ordering = ['region', '-seats_won']

    def __str__(self):
        return f"{self.party.get_name_display()} - {self.seats_won} list seat(s) in {self.get_region_display()}"