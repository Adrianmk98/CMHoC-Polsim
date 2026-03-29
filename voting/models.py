from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Bill(models.Model):
    """Legislative bills for voting"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('FIRST_READING', 'First Reading'),
        ('SECOND_READING', 'Second Reading'),
        ('COMMITTEE', 'In Committee'),
        ('THIRD_READING', 'Third Reading'),
        ('ROYAL_ASSENT', 'Royal Assent'),
        ('FAILED', 'Failed'),
    ]
    
    CHAMBER_CHOICES = [
        ('COMMONS', 'House of Commons'),
        ('SENATE', 'Senate'),
    ]
    
    bill_number = models.CharField(max_length=20, unique=True)  # e.g., C-123, S-45
    title = models.CharField(max_length=300)
    short_title = models.CharField(max_length=150, blank=True)
    sponsor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sponsored_bills')
    chamber = models.CharField(max_length=10, choices=CHAMBER_CHOICES, default='COMMONS')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    summary = models.TextField()
    full_text = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.bill_number}: {self.title}"
    
    def current_vote(self):
        """Get the active vote for this bill"""
        return self.votes.filter(is_active=True).first()
    
    def vote_count(self):
        """Count total votes cast"""
        current = self.current_vote()
        if current:
            return current.ballot_set.count()
        return 0


class Vote(models.Model):
    """Voting session on a bill"""
    VOTE_TYPE_CHOICES = [
        ('FIRST', 'First Reading Vote'),
        ('SECOND', 'Second Reading Vote'),
        ('THIRD', 'Third Reading Vote'),
        ('AMENDMENT', 'Amendment Vote'),
        ('COMMITTEE', 'Committee Vote'),
    ]
    
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='votes')
    vote_type = models.CharField(max_length=20, choices=VOTE_TYPE_CHOICES)
    description = models.TextField()
    
    opened_at = models.DateTimeField(default=timezone.now)
    closes_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-opened_at']
    
    def __str__(self):
        return f"{self.vote_type} - {self.bill.bill_number}"
    
    def is_open(self):
        """Check if vote is still open"""
        return self.is_active and timezone.now() < self.closes_at
    
    def yea_count(self):
        return self.ballot_set.filter(vote='YEA').count()
    
    def nay_count(self):
        return self.ballot_set.filter(vote='NAY').count()
    
    def abstain_count(self):
        return self.ballot_set.filter(vote='ABSTAIN').count()
    
    def total_votes(self):
        return self.ballot_set.count()
    
    def result(self):
        """Determine vote result"""
        if self.is_open():
            return "In Progress"
        yea = self.yea_count()
        nay = self.nay_count()
        if yea > nay:
            return "PASSED"
        elif nay > yea:
            return "FAILED"
        else:
            return "TIED"


class Ballot(models.Model):
    """Individual vote cast by a user"""
    VOTE_CHOICES = [
        ('YEA', 'Yea'),
        ('NAY', 'Nay'),
        ('ABSTAIN', 'Abstain'),
    ]
    
    vote_session = models.ForeignKey(Vote, on_delete=models.CASCADE)
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)
    cast_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['vote_session', 'voter']
        ordering = ['-cast_at']
    
    def __str__(self):
        return f"{self.voter.username} - {self.vote} on {self.vote_session.bill.bill_number}"


class PlayerHistory(models.Model):
    """Track player's legislative history and activities"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='history')
    
    # Voting record
    total_votes = models.IntegerField(default=0)
    yea_votes = models.IntegerField(default=0)
    nay_votes = models.IntegerField(default=0)
    abstain_votes = models.IntegerField(default=0)
    
    # Bill sponsorship
    bills_sponsored = models.IntegerField(default=0)
    bills_passed = models.IntegerField(default=0)
    bills_failed = models.IntegerField(default=0)
    
    # Activity metrics
    threads_created = models.IntegerField(default=0)
    posts_made = models.IntegerField(default=0)
    
    # Participation rate
    participation_rate = models.FloatField(default=0.0)  # % of votes participated in
    
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"History: {self.user.username}"
    
    def update_stats(self):
        """Recalculate all statistics"""
        from forum.models import Thread, Post
        
        # Voting stats
        ballots = Ballot.objects.filter(voter=self.user)
        self.total_votes = ballots.count()
        self.yea_votes = ballots.filter(vote='YEA').count()
        self.nay_votes = ballots.filter(vote='NAY').count()
        self.abstain_votes = ballots.filter(vote='ABSTAIN').count()
        
        # Bill stats
        bills = Bill.objects.filter(sponsor=self.user)
        self.bills_sponsored = bills.count()
        self.bills_passed = bills.filter(status='ROYAL_ASSENT').count()
        self.bills_failed = bills.filter(status='FAILED').count()
        
        # Forum activity
        self.threads_created = Thread.objects.filter(author=self.user).count()
        self.posts_made = Post.objects.filter(author=self.user).count()
        
        # Participation rate
        total_votes_available = Vote.objects.filter(is_active=False).count()
        if total_votes_available > 0:
            self.participation_rate = (self.total_votes / total_votes_available) * 100

        self.save()


class BillDebatePost(models.Model):
    """A debate post attached to a specific reading stage of a bill."""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='debate_posts')
    reading_stage = models.CharField(max_length=20, choices=Bill.STATUS_CHOICES)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='debate_posts')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} on {self.bill.bill_number} ({self.reading_stage})"