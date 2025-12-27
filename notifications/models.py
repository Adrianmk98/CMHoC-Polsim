from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Notification(models.Model):
    """User notifications"""
    NOTIFICATION_TYPES = [
        ('CABINET_APPOINTED', 'Cabinet Appointment'),
        ('CABINET_REMOVED', 'Cabinet Removal'),
        ('VOTE_OPENED', 'Vote Opened'),
        ('VOTE_CLOSING', 'Vote Closing Soon'),
        ('VOTE_CLOSED', 'Vote Closed'),
        ('BILL_CREATED', 'New Bill'),
        ('BILL_STATUS', 'Bill Status Changed'),
        ('THREAD_REPLY', 'Thread Reply'),
        ('MENTION', 'Mentioned'),
        ('POSITION_CHANGED', 'Position Changed'),
        ('PARTY_CHANGED', 'Party Changed'),
        ('GENERAL', 'General Notification'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)  # URL to related object
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: link to related objects
    related_bill_id = models.IntegerField(null=True, blank=True)
    related_vote_id = models.IntegerField(null=True, blank=True)
    related_thread_id = models.IntegerField(null=True, blank=True)
    related_user_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()
    
    @classmethod
    def create_notification(cls, user, notification_type, title, message, link='', **kwargs):
        """Helper method to create a notification"""
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            **kwargs
        )
    
    @classmethod
    def notify_cabinet_appointment(cls, user, position_title, cabinet_name):
        """Notify user of cabinet appointment"""
        return cls.create_notification(
            user=user,
            notification_type='CABINET_APPOINTED',
            title='🏛️ Cabinet Appointment',
            message=f'You have been appointed as {position_title} in the {cabinet_name}.',
            link='/cabinet/'
        )
    
    @classmethod
    def notify_cabinet_removal(cls, user, position_title, cabinet_name):
        """Notify user of cabinet removal"""
        return cls.create_notification(
            user=user,
            notification_type='CABINET_REMOVED',
            title='Cabinet Change',
            message=f'You have been removed from the position of {position_title} in the {cabinet_name}.',
            link='/cabinet/'
        )
    
    @classmethod
    def notify_mps_vote_opened(cls, bill, vote):
        """Notify all MPs when a vote opens"""
        from forum.models import PositionHistory
        
        # Get all current MPs
        current_mps = PositionHistory.objects.filter(
            position_type='MP',
            end_date__isnull=True
        ).select_related('user_profile__user')
        
        notifications = []
        for mp_position in current_mps:
            notifications.append(cls(
                user=mp_position.user_profile.user,
                notification_type='VOTE_OPENED',
                title=f'🗳️ Vote Opened: {bill.bill_number}',
                message=f'A vote has opened on {bill.title}. Vote type: {vote.get_vote_type_display()}. Closes: {vote.closes_at.strftime("%B %d, %Y at %I:%M %p")}',
                link=f'/voting/bill/{bill.id}/',
                related_bill_id=bill.id,
                related_vote_id=vote.id
            ))
        
        # Bulk create for efficiency
        if notifications:
            cls.objects.bulk_create(notifications)
        
        return len(notifications)
    
    @classmethod
    def notify_vote_closing_soon(cls, bill, vote, hours=24):
        """Notify MPs who haven't voted that vote is closing soon"""
        from forum.models import PositionHistory
        from voting.models import Ballot
        
        # Get all current MPs
        current_mps = PositionHistory.objects.filter(
            position_type='MP',
            end_date__isnull=True
        ).select_related('user_profile__user')
        
        # Get MPs who already voted
        voted_users = Ballot.objects.filter(vote_session=vote).values_list('voter_id', flat=True)
        
        notifications = []
        for mp_position in current_mps:
            if mp_position.user_profile.user.id not in voted_users:
                notifications.append(cls(
                    user=mp_position.user_profile.user,
                    notification_type='VOTE_CLOSING',
                    title=f'⏰ Vote Closing Soon: {bill.bill_number}',
                    message=f'Voting on {bill.title} closes in {hours} hours. You have not voted yet!',
                    link=f'/voting/vote/{vote.id}/cast/',
                    related_bill_id=bill.id,
                    related_vote_id=vote.id
                ))
        
        if notifications:
            cls.objects.bulk_create(notifications)
        
        return len(notifications)
    
    @classmethod
    def notify_bill_sponsor(cls, bill, message_text, link=''):
        """Notify bill sponsor"""
        return cls.create_notification(
            user=bill.sponsor,
            notification_type='BILL_STATUS',
            title=f'📜 Bill Update: {bill.bill_number}',
            message=message_text,
            link=link or f'/voting/bill/{bill.id}/',
            related_bill_id=bill.id
        )
    
    @classmethod
    def notify_thread_reply(cls, thread, reply_author):
        """Notify thread author of reply"""
        if thread.author != reply_author:  # Don't notify of own replies
            return cls.create_notification(
                user=thread.author,
                notification_type='THREAD_REPLY',
                title='💬 New Reply',
                message=f'{reply_author.username} replied to your thread "{thread.title}"',
                link=f'/thread/{thread.id}/',
                related_thread_id=thread.id,
                related_user_id=reply_author.id
            )
        return None


class NotificationPreference(models.Model):
    """User notification preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email preferences
    email_on_cabinet_change = models.BooleanField(default=True)
    email_on_vote_opened = models.BooleanField(default=True)
    email_on_vote_closing = models.BooleanField(default=True)
    email_on_thread_reply = models.BooleanField(default=True)
    email_on_mention = models.BooleanField(default=True)
    
    # In-app notification preferences
    notify_cabinet_change = models.BooleanField(default=True)
    notify_vote_opened = models.BooleanField(default=True)
    notify_vote_closing = models.BooleanField(default=True)
    notify_bill_updates = models.BooleanField(default=True)
    notify_thread_reply = models.BooleanField(default=True)
    notify_mention = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username}'s Notification Preferences"