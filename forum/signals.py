from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CabinetPosition, PositionHistory, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Ensure every user has a profile so party tags etc. have somewhere to live"""
    if created:
        UserProfile.objects.get_or_create(user=instance)


# CabinetPosition.position_type values that don't have an exact PositionHistory
# counterpart fall back to the closest career position type.
CABINET_TO_CAREER_POSITION_TYPE = {
    'PM': 'PM',
    'DEPUTY_PM': 'DEPUTY_PM',
    'MINISTER': 'MINISTER',
    'MINISTER_STATE': 'MINISTER',
    'PARL_SEC': 'PARL_SEC',
}


@receiver(post_save, sender=CabinetPosition)
def sync_career_position_from_cabinet(sender, instance, **kwargs):
    """Keep PositionHistory (what the public profile's Political Career shows)
    in sync with cabinet appointments made through the moderator tools"""
    existing = PositionHistory.objects.filter(
        user_profile=instance.user_profile,
        position_title=instance.title,
        start_date=instance.start_date,
    ).first()

    if instance.end_date:
        if existing and existing.end_date != instance.end_date:
            existing.end_date = instance.end_date
            existing.save(update_fields=['end_date'])
        return

    if existing:
        return

    PositionHistory.objects.create(
        user_profile=instance.user_profile,
        position_type=CABINET_TO_CAREER_POSITION_TYPE.get(instance.position_type, 'MINISTER'),
        position_title=instance.title,
        start_date=instance.start_date,
        notes=f'Cabinet: {instance.cabinet.name}',
    )
