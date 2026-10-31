from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import PartyMembership, PartyRole


@receiver(post_save, sender=PartyMembership)
def update_member_count_on_save(sender, instance, **kwargs):
    """Update party member count when membership changes"""
    instance.party.update_member_count()


@receiver(post_delete, sender=PartyMembership)
def update_member_count_on_delete(sender, instance, **kwargs):
    """Update party member count when membership is deleted"""
    instance.party.update_member_count()


@receiver(post_save, sender=PartyMembership)
def sync_profile_party_tag(sender, instance, **kwargs):
    """Keep the forum profile party tag in sync with party membership"""
    from forum.models import UserProfile, PoliticalParty

    poli_party = PoliticalParty.objects.filter(name__iexact=instance.party.abbreviation).first()
    if not poli_party:
        return

    profile, _ = UserProfile.objects.get_or_create(user=instance.user)

    if instance.is_active:
        if profile.party_id != poli_party.id:
            profile.party = poli_party
            profile.save(update_fields=['party'])
    elif profile.party_id == poli_party.id:
        profile.party = None
        profile.save(update_fields=['party'])


@receiver(post_save, sender=PartyRole)
def sync_party_leadership(sender, instance, **kwargs):
    """Sync party leadership fields when roles change"""
    if instance.role == 'LEADER' and instance.is_active:
        instance.party.leader = instance.user
        instance.party.save(update_fields=['leader'])
    
    elif instance.role == 'PRESS' and instance.is_active:
        instance.party.press_secretary = instance.user
        instance.party.save(update_fields=['press_secretary'])