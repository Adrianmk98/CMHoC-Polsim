from django.db import models
from django.utils import timezone
from datetime import timedelta

from forum.models import UserProfile


class NPCProfile(models.Model):
    """Behavior/persona config for an AI-driven NPC character."""

    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='npc_profile')
    persona = models.TextField(help_text='Voice, ideology, and tone used to seed the system prompt')
    is_active = models.BooleanField(default=True, help_text='Kill switch for this NPC')
    reply_chance = models.FloatField(default=0.4, help_text='Probability (0-1) this NPC reacts to an eligible trigger')
    cooldown_minutes = models.IntegerField(default=20, help_text='Minimum minutes between this NPC\'s posts')
    last_posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user_profile__user__username']

    def __str__(self):
        return f"NPC: {self.user_profile.user.username}"

    def can_post_now(self):
        if not self.is_active:
            return False
        if self.last_posted_at is None:
            return True
        return timezone.now() >= self.last_posted_at + timedelta(minutes=self.cooldown_minutes)

    def mark_posted(self):
        self.last_posted_at = timezone.now()
        self.save(update_fields=['last_posted_at'])
