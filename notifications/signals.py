from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Notification, NotificationPreference


# Auto-create notification preferences for new users
@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    if created:
        NotificationPreference.objects.get_or_create(user=instance)


# Cabinet position signals
@receiver(post_save, sender='forum.CabinetPosition')
def notify_cabinet_appointment(sender, instance, created, **kwargs):
    if created:
        # New appointment
        Notification.notify_cabinet_appointment(
            user=instance.user_profile.user,
            position_title=instance.title,
            cabinet_name=instance.cabinet.name
        )


@receiver(pre_save, sender='forum.CabinetPosition')
def notify_cabinet_removal(sender, instance, **kwargs):
    if instance.pk:  # Only for existing positions
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            # Check if end_date is being set (removal)
            if old_instance.end_date is None and instance.end_date is not None:
                Notification.notify_cabinet_removal(
                    user=instance.user_profile.user,
                    position_title=instance.title,
                    cabinet_name=instance.cabinet.name
                )
        except sender.DoesNotExist:
            pass


# Vote signals
@receiver(post_save, sender='voting.Vote')
def notify_vote_opened(sender, instance, created, **kwargs):
    if created and instance.is_active:
        # Notify all MPs that a vote has opened
        Notification.notify_mps_vote_opened(
            bill=instance.bill,
            vote=instance
        )


# Bill signals
@receiver(post_save, sender='voting.Bill')
def notify_bill_status_change(sender, instance, created, **kwargs):
    if not created:
        # Bill status changed
        if instance.status == 'ROYAL_ASSENT':
            Notification.notify_bill_sponsor(
                bill=instance,
                message_text=f'Your bill {instance.bill_number} has received Royal Assent and is now law!'
            )
        elif instance.status == 'FAILED':
            Notification.notify_bill_sponsor(
                bill=instance,
                message_text=f'Your bill {instance.bill_number} has failed.'
            )


# Thread reply signals
@receiver(post_save, sender='forum.Post')
def notify_thread_reply(sender, instance, created, **kwargs):
    if created:
        # New post created
        Notification.notify_thread_reply(
            thread=instance.thread,
            reply_author=instance.author
        )