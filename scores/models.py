from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


POSITION_BONUSES = {
    'PM': 30,
    'DEPUTY_PM': 25,
    'SPEAKER': 15,
    'DEPUTY_SPEAKER': 10,
    'MINISTER': 20,
    'PARL_SEC': 10,
    'LEADER': 10,
    'DEPUTY_LEADER': 5,
    'HOUSE_LEADER': 5,
    'WHIP': 5,
    'CRITIC': 5,
    'COMMITTEE_CHAIR': 5,
    'COMMITTEE_MEMBER': 0,
    'MP': 0,
    'SENATOR': 0,
}


class ParliamentSession(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Only one session can be active at a time
        if self.is_active:
            ParliamentSession.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class PlayerLT(models.Model):
    """Legacy carry-over score and active persona flag per player per session."""
    session = models.ForeignKey(ParliamentSession, on_delete=models.CASCADE, related_name='player_lts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lt_scores')
    lt_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    is_active_persona = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [['session', 'user']]
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.username} — {self.session.name} (LT: {self.lt_score})"


class ScoreEntry(models.Model):
    """A single moderator-assigned score for a player activity."""
    SCORE_TYPES = [
        ('DEBATE', 'Debate'),
        ('PRESS', 'Press'),
        ('LEGISLATION', 'Legislation'),
        ('CAMPAIGN', 'Campaign'),
    ]

    session = models.ForeignKey(ParliamentSession, on_delete=models.CASCADE, related_name='score_entries')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='score_entries')
    score_type = models.CharField(max_length=20, choices=SCORE_TYPES)
    score = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.CharField(max_length=300, blank=True)

    # Optional links to specific content
    bill_id = models.IntegerField(null=True, blank=True)
    press_release_id = models.IntegerField(null=True, blank=True)
    thread_id = models.IntegerField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='score_entries_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} +{self.score} {self.score_type} ({self.session.name})"


def get_position_bonus(user):
    """Return the total position bonus for a user based on current PositionHistory."""
    from forum.models import PositionHistory
    positions = PositionHistory.objects.filter(
        user_profile__user=user,
        end_date__isnull=True,
    )
    return Decimal(str(sum(POSITION_BONUSES.get(p.position_type, 0) for p in positions)))


def get_player_totals(session, user):
    """Return a dict of score totals for a user in a session."""
    from django.db.models import Sum

    entries = ScoreEntry.objects.filter(session=session, user=user)
    totals = {
        'debate': entries.filter(score_type='DEBATE').aggregate(s=Sum('score'))['s'] or Decimal('0'),
        'press': entries.filter(score_type='PRESS').aggregate(s=Sum('score'))['s'] or Decimal('0'),
        'legislation': entries.filter(score_type='LEGISLATION').aggregate(s=Sum('score'))['s'] or Decimal('0'),
        'campaign': entries.filter(score_type='CAMPAIGN').aggregate(s=Sum('score'))['s'] or Decimal('0'),
    }

    lt_obj = PlayerLT.objects.filter(session=session, user=user).first()
    totals['lt'] = lt_obj.lt_score if lt_obj else Decimal('0')
    totals['is_active_persona'] = lt_obj.is_active_persona if lt_obj else True
    totals['position_bonus'] = get_position_bonus(user)
    totals['personal_modifier'] = (
        totals['lt'] + totals['position_bonus'] +
        totals['debate'] + totals['press'] +
        totals['legislation'] + totals['campaign']
    )
    totals['active_modifier'] = totals['personal_modifier'] if totals['is_active_persona'] else Decimal('0')
    return totals
