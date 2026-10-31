from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Ensure every user has a profile so party tags etc. have somewhere to live"""
    if created:
        UserProfile.objects.get_or_create(user=instance)
