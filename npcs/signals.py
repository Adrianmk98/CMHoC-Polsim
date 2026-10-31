import threading

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import services


def _is_npc_user(user):
    profile = getattr(user, 'profile', None)
    return profile is not None and hasattr(profile, 'npc_profile')


def _run_async(target, *args):
    transaction.on_commit(lambda: threading.Thread(target=target, args=args, daemon=True).start())


@receiver(post_save, sender='forum.Post')
def on_forum_post_created(sender, instance, created, **kwargs):
    if not created or _is_npc_user(instance.author):
        return
    _run_async(services.maybe_reply_to_thread, instance)


@receiver(post_save, sender='voting.BillDebatePost')
def on_bill_debate_post_created(sender, instance, created, **kwargs):
    if not created or _is_npc_user(instance.author):
        return
    _run_async(services.maybe_reply_to_debate, instance)


@receiver(post_save, sender='press.PressRelease')
def on_press_release_created(sender, instance, created, **kwargs):
    if not created or _is_npc_user(instance.author):
        return
    _run_async(services.maybe_comment_on_press_release, instance)


@receiver(post_save, sender='press.PressComment')
def on_press_comment_created(sender, instance, created, **kwargs):
    if not created or _is_npc_user(instance.author):
        return
    _run_async(services.maybe_comment_on_press_release, instance.press_release)
