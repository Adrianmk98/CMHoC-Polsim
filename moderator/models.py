from django.db import models
from django.contrib.auth.models import User


class ModeratorProfile(models.Model):
    """Moderator access control for a user, kept separate from forum.UserProfile.

    Only staff/superusers can create or change these (Django admin, or the
    make_moderator management command) - never other moderators, to avoid
    self- or peer-promotion.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='moderator_profile')
    is_moderator = models.BooleanField(default=False)
    can_manage_elections = models.BooleanField(default=False)
    can_manage_cabinet = models.BooleanField(default=False)
    can_manage_bills = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_manage_scores = models.BooleanField(default=False)
    can_manage_parties = models.BooleanField(default=False)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_moderator_profiles')
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ModeratorProfile({self.user.username})"


class AuditLog(models.Model):
    """Record of every change made through the moderator tools: who, what, when."""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('end', 'End'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_log_entries')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=50, blank=True)
    target_repr = models.CharField(max_length=300, blank=True)
    view_name = models.CharField(max_length=100, blank=True)
    changes = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        who = self.actor.username if self.actor else 'unknown'
        return f"{who} {self.action} {self.target_type} #{self.target_id} @ {self.timestamp}"
