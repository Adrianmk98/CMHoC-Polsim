from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta


class Party(models.Model):
    """Political party model"""
    
    IDEOLOGY_CHOICES = [
        ('LEFT', 'Left Wing'),
        ('CENTER_LEFT', 'Center-Left'),
        ('CENTER', 'Centrist'),
        ('CENTER_RIGHT', 'Center-Right'),
        ('RIGHT', 'Right Wing'),
        ('OTHER', 'Other'),
    ]
    
    # Basic info
    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    color = models.CharField(max_length=7, default='#808080', help_text='Hex color code (e.g., #FF0000)')
    logo = models.TextField(blank=True, help_text='Base64 encoded logo image')
    
    # Political info
    ideology = models.CharField(max_length=20, choices=IDEOLOGY_CHOICES, default='CENTER')
    platform = models.TextField(blank=True, help_text='Party platform and policies')
    
    # Leadership
    leader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='led_party')
    press_secretary = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='press_secretary_for')
    
    # Metadata
    founded_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Stats
    member_count = models.IntegerField(default=0)
    
    class Meta:
        verbose_name_plural = 'Parties'
        ordering = ['-member_count', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.abbreviation})"
    
    def get_absolute_url(self):
        return reverse('parties:detail', kwargs={'pk': self.pk})
    
    def update_member_count(self):
        """Update cached member count"""
        self.member_count = self.members.count()
        self.save(update_fields=['member_count'])
    
    def get_members(self):
        """Get all party members"""
        return PartyMembership.objects.filter(party=self, is_active=True).select_related('user')
    
    def get_leadership(self):
        """Get all leadership roles"""
        return PartyRole.objects.filter(party=self, is_active=True).select_related('user')
    
    def can_user_manage(self, user):
        """Check if user can manage party settings"""
        if not user.is_authenticated:
            return False
        if user == self.leader:
            return True
        return PartyRole.objects.filter(
            party=self,
            user=user,
            role__in=['DEPUTY', 'EXECUTIVE'],
            is_active=True
        ).exists()
    
    def has_active_leadership_election(self):
        """Check if there's an active leadership election"""
        return LeadershipElection.objects.filter(
            party=self,
            is_active=True,
            closes_at__gt=timezone.now()
        ).exists()
    
    def has_active_confidence_vote(self):
        """Check if there's an active vote of no confidence"""
        return ConfidenceVote.objects.filter(
            party=self,
            is_active=True,
            closes_at__gt=timezone.now()
        ).exists()


class PartyMembership(models.Model):
    """Party membership for users"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='party_memberships')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='members')
    
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Membership status
    is_founding_member = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'party']
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.party.abbreviation}"
    
    def leave_party(self):
        """Leave the party"""
        self.is_active = False
        self.left_at = timezone.now()
        self.save()
        
        # Remove any roles
        PartyRole.objects.filter(user=self.user, party=self.party).update(is_active=False)
        
        # Update member count
        self.party.update_member_count()


class PartyRole(models.Model):
    """Leadership and officer roles within party"""
    
    ROLE_CHOICES = [
        ('LEADER', 'Party Leader'),
        ('DEPUTY', 'Deputy Leader'),
        ('PRESS', 'Press Secretary'),
        ('WHIP', 'Party Whip'),
        ('TREASURER', 'Treasurer'),
        ('EXECUTIVE', 'Executive Member'),
        ('ORGANIZER', 'Organizer'),
    ]
    
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='roles')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='party_roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    appointed_at = models.DateTimeField(auto_now_add=True)
    appointed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='appointed_roles')
    removed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['party', 'user', 'role']
        ordering = ['-appointed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()} of {self.party.abbreviation}"
    
    def can_create_press(self):
        """Check if role allows creating press releases"""
        return self.role in ['LEADER', 'DEPUTY', 'PRESS']


class LeadershipElection(models.Model):
    """Elections for party leadership"""
    
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='leadership_elections')
    
    # Election info
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    opens_at = models.DateTimeField(default=timezone.now)
    closes_at = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    
    # Results
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_leadership_elections')
    total_votes = models.IntegerField(default=0)
    
    # Trigger (why this election was called)
    TRIGGER_CHOICES = [
        ('FOUNDING', 'Founding Election'),
        ('RESIGNATION', 'Leader Resignation'),
        ('NO_CONFIDENCE', 'Vote of No Confidence'),
        ('SCHEDULED', 'Scheduled Election'),
        ('VACANCY', 'Leadership Vacancy'),
    ]
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='SCHEDULED')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.party.abbreviation} Leadership Election - {self.created_at.date()}"
    
    def get_absolute_url(self):
        return reverse('parties:election_detail', kwargs={'pk': self.pk})
    
    def is_open(self):
        """Check if election is currently open for voting"""
        now = timezone.now()
        return self.is_active and self.opens_at <= now <= self.closes_at
    
    def can_vote(self, user):
        """Check if user can vote in this election"""
        if not self.is_open():
            return False
        
        # Must be party member
        membership = PartyMembership.objects.filter(
            user=user,
            party=self.party,
            is_active=True
        ).first()
        
        if not membership:
            return False
        
        # Check if already voted
        return not LeadershipVote.objects.filter(
            election=self,
            voter=user
        ).exists()
    
    def get_candidates(self):
        """Get all candidates"""
        return self.candidates.all().select_related('user')
    
    def calculate_results(self):
        """Calculate election results"""
        candidates = self.candidates.annotate(
            vote_count=models.Count('votes')
        ).order_by('-vote_count')
        
        if candidates.exists():
            winner = candidates.first()
            self.winner = winner.user
            self.total_votes = LeadershipVote.objects.filter(election=self).count()
            self.is_completed = True
            self.is_active = False
            self.save()
            
            # Update party leader
            self.party.leader = winner.user
            self.party.save()
            
            # Create/update leader role
            PartyRole.objects.update_or_create(
                party=self.party,
                user=winner.user,
                role='LEADER',
                defaults={'is_active': True}
            )


class LeadershipCandidate(models.Model):
    """Candidates in leadership election"""
    
    election = models.ForeignKey(LeadershipElection, on_delete=models.CASCADE, related_name='candidates')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leadership_candidacies')
    
    # Campaign info
    platform = models.TextField(blank=True, help_text='Campaign platform')
    nominated_at = models.DateTimeField(auto_now_add=True)
    
    # Nomination (optional - can be self-nomination)
    nominated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leadership_nominations')
    
    # Status
    is_approved = models.BooleanField(default=True)
    withdrawn = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['election', 'user']
        ordering = ['-nominated_at']
    
    def __str__(self):
        return f"{self.user.username} for {self.election.party.abbreviation} Leader"
    
    def get_vote_count(self):
        """Get number of votes received"""
        return self.votes.count()


class LeadershipVote(models.Model):
    """Individual vote in leadership election"""
    
    election = models.ForeignKey(LeadershipElection, on_delete=models.CASCADE, related_name='votes')
    candidate = models.ForeignKey(LeadershipCandidate, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leadership_votes')
    
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['election', 'voter']
        ordering = ['-voted_at']
    
    def __str__(self):
        return f"{self.voter.username} voted in {self.election}"


class ConfidenceVote(models.Model):
    """Vote of no confidence in party leader"""
    
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='confidence_votes')
    target_leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='confidence_votes_against')
    
    # Vote info
    title = models.CharField(max_length=200, default='Vote of No Confidence')
    reason = models.TextField(help_text='Reason for calling this vote')
    
    # Initiator
    initiated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='initiated_confidence_votes')
    initiated_at = models.DateTimeField(auto_now_add=True)
    
    # Timing
    opens_at = models.DateTimeField(default=timezone.now)
    closes_at = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    
    # Results
    votes_no_confidence = models.IntegerField(default=0)
    votes_confidence = models.IntegerField(default=0)
    result = models.CharField(max_length=20, blank=True)  # 'PASSED' or 'FAILED'
    
    # Minimum percentage needed to pass (default 50%)
    threshold_percentage = models.IntegerField(default=50)
    
    class Meta:
        ordering = ['-initiated_at']
    
    def __str__(self):
        return f"No Confidence Vote - {self.party.abbreviation} - {self.initiated_at.date()}"
    
    def get_absolute_url(self):
        return reverse('parties:confidence_vote_detail', kwargs={'pk': self.pk})
    
    def is_open(self):
        """Check if vote is currently open"""
        now = timezone.now()
        return self.is_active and self.opens_at <= now <= self.closes_at
    
    def can_vote(self, user):
        """Check if user can vote"""
        if not self.is_open():
            return False
        
        # Must be party member
        membership = PartyMembership.objects.filter(
            user=user,
            party=self.party,
            is_active=True
        ).first()
        
        if not membership:
            return False
        
        # Check if already voted
        return not ConfidenceBallot.objects.filter(
            confidence_vote=self,
            voter=user
        ).exists()
    
    def calculate_results(self):
        """Calculate vote results"""
        ballots = self.ballots.all()
        
        self.votes_no_confidence = ballots.filter(vote='NO_CONFIDENCE').count()
        self.votes_confidence = ballots.filter(vote='CONFIDENCE').count()
        
        total_votes = self.votes_no_confidence + self.votes_confidence
        
        if total_votes > 0:
            percentage = (self.votes_no_confidence / total_votes) * 100
            
            if percentage >= self.threshold_percentage:
                self.result = 'PASSED'
                self.is_completed = True
                self.is_active = False
                
                # Remove leader
                self.party.leader = None
                self.party.save()
                
                # Deactivate leader role
                PartyRole.objects.filter(
                    party=self.party,
                    role='LEADER',
                    user=self.target_leader
                ).update(is_active=False)
                
                # Trigger leadership election
                LeadershipElection.objects.create(
                    party=self.party,
                    title=f"Leadership Election Following No Confidence Vote",
                    trigger='NO_CONFIDENCE',
                    closes_at=timezone.now() + timedelta(days=7)
                )
            else:
                self.result = 'FAILED'
                self.is_completed = True
                self.is_active = False
        
        self.save()


class ConfidenceBallot(models.Model):
    """Individual ballot in confidence vote"""
    
    VOTE_CHOICES = [
        ('CONFIDENCE', 'Confidence'),
        ('NO_CONFIDENCE', 'No Confidence'),
    ]
    
    confidence_vote = models.ForeignKey(ConfidenceVote, on_delete=models.CASCADE, related_name='ballots')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='confidence_ballots')
    vote = models.CharField(max_length=20, choices=VOTE_CHOICES)
    
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['confidence_vote', 'voter']
        ordering = ['-voted_at']
    
    def __str__(self):
        return f"{self.voter.username} - {self.get_vote_display()}"


class JoinRequest(models.Model):
    """Request to join a party"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='party_join_requests')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='join_requests')
    
    message = models.TextField(blank=True, help_text='Why do you want to join this party?')
    
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'party']
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.user.username} → {self.party.abbreviation} ({self.status})"
    
    def approve(self, reviewer):
        """Approve the join request"""
        self.status = 'APPROVED'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()
        
        # Create membership
        PartyMembership.objects.create(
            user=self.user,
            party=self.party,
            is_active=True
        )
        
        # Update member count
        self.party.update_member_count()
    
    def reject(self, reviewer):
        """Reject the join request"""
        self.status = 'REJECTED'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()