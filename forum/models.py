from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q


class Province(models.Model):
    PROVINCE_CHOICES = [
        ('AB', 'Alberta'),
        ('BC', 'British Columbia'),
        ('MB', 'Manitoba'),
        ('NB', 'New Brunswick'),
        ('NL', 'Newfoundland and Labrador'),
        ('NT', 'Northwest Territories'),
        ('NS', 'Nova Scotia'),
        ('NU', 'Nunavut'),
        ('ON', 'Ontario'),
        ('PE', 'Prince Edward Island'),
        ('QC', 'Quebec'),
        ('SK', 'Saskatchewan'),
        ('YT', 'Yukon'),
    ]
    
    code = models.CharField(max_length=2, choices=PROVINCE_CHOICES, unique=True)
    
    def __str__(self):
        return self.get_code_display()


class Riding(models.Model):
    name = models.CharField(max_length=200, unique=True)
    provinces = models.ManyToManyField(Province, related_name='ridings', blank=True)
    population = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        province_list = ', '.join(str(p) for p in self.provinces.all())
        return f"{self.name} ({province_list})"

    def current_mp(self):
        from django.contrib.auth.models import User
        try:
            position = PositionHistory.objects.filter(
                position_type='MP',
                riding_obj=self,
                end_date__isnull=True
            ).first()
            return position.user_profile.user if position else None
        except:
            return None


class Flair(models.Model):
    """Thread flairs for categorization"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#6c757d')  # Hex color
    description = models.CharField(max_length=200, blank=True)
    category = models.ForeignKey('ForumCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='flairs')
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PoliticalParty(models.Model):
    """Canadian political parties"""
    PARTY_CHOICES = [
        ('LIB', 'Liberal Party of Canada'),
        ('CON', 'Conservative Party of Canada'),
        ('NDP', 'New Democratic Party'),
        ('BQ', 'Bloc Québécois'),
        ('GRN', 'Green Party of Canada'),
        ('PPC', 'People\'s Party of Canada'),
        ('IND', 'Independent'),
    ]
    
    name = models.CharField(max_length=100, choices=PARTY_CHOICES, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#000000')  # Hex color code
    
    class Meta:
        verbose_name_plural = "Political Parties"
    
    def __str__(self):
        return self.get_name_display()


class UserProfile(models.Model):
    """Extended user profile for political simulation"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    party = models.ForeignKey(PoliticalParty, on_delete=models.SET_NULL, null=True, blank=True)
    riding = models.ForeignKey(Riding, on_delete=models.SET_NULL, null=True, blank=True, related_name='representatives')
    riding_name = models.CharField(max_length=200, blank=True)  # Deprecated: kept for backwards compatibility
    role = models.CharField(max_length=100, blank=True)  # e.g., MP, Senator, Minister
    bio = models.TextField(blank=True)
    joined_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def get_riding_display(self):
        """Get riding name from Riding object or fallback to riding_name"""
        if self.riding:
            return self.riding.name
        return self.riding_name
    
    def current_position(self):
        """Get the user's current political position"""
        return self.position_history.filter(end_date__isnull=True).first()
    
    def past_positions(self):
        """Get all past positions"""
        return self.position_history.filter(end_date__isnull=False).order_by('-end_date')
    
    def all_positions(self):
        """Get all positions ordered by date"""
        return self.position_history.all().order_by('-start_date')


class PositionHistory(models.Model):
    """Track changes in political positions and roles"""
    POSITION_TYPES = [
        ('MP', 'Member of Parliament'),
        ('SENATOR', 'Senator'),
        ('PM', 'Prime Minister'),
        ('DEPUTY_PM', 'Deputy Prime Minister'),
        ('MINISTER', 'Cabinet Minister'),
        ('PARL_SEC', 'Parliamentary Secretary'),
        ('LEADER', 'Party Leader'),
        ('DEPUTY_LEADER', 'Deputy Party Leader'),
        ('HOUSE_LEADER', 'House Leader'),
        ('WHIP', 'Party Whip'),
        ('CRITIC', 'Opposition Critic'),
        ('SPEAKER', 'Speaker of the House'),
        ('DEPUTY_SPEAKER', 'Deputy Speaker'),
        ('COMMITTEE_CHAIR', 'Committee Chair'),
        ('COMMITTEE_MEMBER', 'Committee Member'),
    ]
    
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='position_history')
    position_type = models.CharField(max_length=50, choices=POSITION_TYPES)
    position_title = models.CharField(max_length=200)  # e.g., "Minister of Finance"
    riding_obj = models.ForeignKey(Riding, on_delete=models.SET_NULL, null=True, blank=True, related_name='position_holders')
    riding = models.CharField(max_length=200, blank=True)  # Deprecated: kept for backwards compatibility
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # Null means current position
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = "Position Histories"
    
    def __str__(self):
        status = "Current" if not self.end_date else "Former"
        return f"{status}: {self.user_profile.user.username} - {self.position_title}"
    
    def get_riding_display(self):
        """Get riding name from Riding object or fallback to riding field"""
        if self.riding_obj:
            return self.riding_obj.name
        return self.riding
    
    def is_current(self):
        return self.end_date is None
    
    def duration(self):
        """Calculate how long the position was held"""
        from django.utils import timezone
        end = self.end_date if self.end_date else timezone.now().date()
        delta = end - self.start_date
        
        years = delta.days // 365
        months = (delta.days % 365) // 30
        
        if years > 0:
            return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
        elif months > 0:
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"


class PartyHistory(models.Model):
    """Track changes in party affiliation"""
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='party_history')
    party = models.ForeignKey(PoliticalParty, on_delete=models.SET_NULL, null=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # Null means current affiliation
    reason = models.CharField(max_length=200, blank=True)  # e.g., "Crossed the floor", "Election"
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = "Party Histories"
    
    def __str__(self):
        status = "Current" if not self.end_date else "Former"
        party_name = self.party.get_name_display() if self.party else "Independent"
        return f"{status}: {self.user_profile.user.username} - {party_name}"
    
    def is_current(self):
        return self.end_date is None
    
    def duration(self):
        """Calculate how long the affiliation lasted"""
        from django.utils import timezone
        end = self.end_date if self.end_date else timezone.now().date()
        delta = end - self.start_date
        
        years = delta.days // 365
        months = (delta.days % 365) // 30
        
        if years > 0:
            return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
        elif months > 0:
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"


class Cabinet(models.Model):
    """Represents a cabinet formation"""
    name = models.CharField(max_length=200)  # e.g., "33rd Canadian Ministry"
    prime_minister = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cabinets_led')
    government_party = models.ForeignKey(PoliticalParty, on_delete=models.SET_NULL, null=True, related_name='cabinets')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # Null means current cabinet
    description = models.TextField(blank=True)
    is_current = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        status = "Current" if self.is_current else "Former"
        return f"{status}: {self.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one current cabinet
        if self.is_current:
            Cabinet.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)
    
    def duration(self):
        """Calculate how long this cabinet has lasted"""
        from django.utils import timezone
        end = self.end_date if self.end_date else timezone.now().date()
        delta = end - self.start_date
        
        years = delta.days // 365
        months = (delta.days % 365) // 30
        
        if years > 0:
            return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
        elif months > 0:
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"
    
    def member_count(self):
        """Count current cabinet members"""
        return self.positions.filter(end_date__isnull=True).count()


class CabinetPosition(models.Model):
    """Individual cabinet position (Minister, Secretary, etc.)"""
    POSITION_TYPES = [
        ('PM', 'Prime Minister'),
        ('DEPUTY_PM', 'Deputy Prime Minister'),
        ('MINISTER', 'Minister'),
        ('MINISTER_STATE', 'Minister of State'),
        ('PARL_SEC', 'Parliamentary Secretary'),
    ]
    
    cabinet = models.ForeignKey(Cabinet, on_delete=models.CASCADE, related_name='positions')
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='cabinet_positions')
    position_type = models.CharField(max_length=50, choices=POSITION_TYPES)
    portfolio = models.CharField(max_length=200)  # e.g., "Finance", "Foreign Affairs"
    title = models.CharField(max_length=300)  # Full title: e.g., "Minister of Finance"
    order = models.IntegerField(default=0)  # For sorting (PM=1, Deputy PM=2, etc.)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['cabinet', 'order', 'portfolio']
    
    def __str__(self):
        return f"{self.title} - {self.user_profile.user.username}"
    
    def is_current(self):
        return self.end_date is None and self.cabinet.is_current
    
    def duration(self):
        """Calculate tenure length"""
        from django.utils import timezone
        end = self.end_date if self.end_date else timezone.now().date()
        delta = end - self.start_date
        
        years = delta.days // 365
        months = (delta.days % 365) // 30
        
        if years > 0:
            return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
        elif months > 0:
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"


class ForumCategory(models.Model):
    """Main forum categories"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Forum Categories"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def thread_count(self):
        return self.threads.count()
    
    def post_count(self):
        return sum(thread.posts.count() for thread in self.threads.all())


class Thread(models.Model):
    """Discussion threads"""
    category = models.ForeignKey(ForumCategory, on_delete=models.CASCADE, related_name='threads')
    title = models.CharField(max_length=300)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='threads')
    flair = models.ForeignKey(Flair, on_delete=models.SET_NULL, null=True, blank=True, related_name='threads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    views = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-is_pinned', '-updated_at']
    
    def __str__(self):
        return self.title
    
    def post_count(self):
        return self.posts.count()
    
    def last_post(self):
        return self.posts.order_by('-created_at').first()
    
    @classmethod
    def search(cls, query):
        """Search threads by title and content"""
        return cls.objects.filter(
            Q(title__icontains=query) |
            Q(posts__content__icontains=query)
        ).distinct()


class Post(models.Model):
    """Individual posts within threads"""
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Post by {self.author.username} in {self.thread.title}"
    
    @classmethod
    def search(cls, query):
        """Search posts by content"""
        return cls.objects.filter(content__icontains=query)