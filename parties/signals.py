from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Party, PartyMembership, PartyRole


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
    """Keep the forum profile party tag and party history in sync with party membership"""
    from forum.models import UserProfile, PartyHistory

    party = instance.party
    profile, _ = UserProfile.objects.get_or_create(user=instance.user)
    today = timezone.now().date()

    if instance.is_active:
        if profile.party_id != party.id:
            profile.party = party
            profile.save(update_fields=['party'])

        # Close out any other open affiliation and open one for this party
        PartyHistory.objects.filter(
            user_profile=profile, end_date__isnull=True
        ).exclude(party=party).update(end_date=today)

        if not PartyHistory.objects.filter(
            user_profile=profile, party=party, end_date__isnull=True
        ).exists():
            PartyHistory.objects.create(
                user_profile=profile,
                party=party,
                start_date=today,
            )
    else:
        if profile.party_id == party.id:
            profile.party = None
            profile.save(update_fields=['party'])

        PartyHistory.objects.filter(
            user_profile=profile, party=party, end_date__isnull=True
        ).update(end_date=today)


@receiver(post_save, sender=PartyRole)
def sync_party_leadership(sender, instance, **kwargs):
    """Sync party leadership fields when roles change"""
    if instance.role == 'LEADER' and instance.is_active:
        instance.party.leader = instance.user
        instance.party.save(update_fields=['leader'])
    
    elif instance.role == 'PRESS' and instance.is_active:
        instance.party.press_secretary = instance.user
        instance.party.save(update_fields=['press_secretary'])


def _party_npc_persona(party):
    """Seed text for the party HQ NPC, built from the party's current platform."""
    platform = party.platform.strip() if party.platform else 'This party has not published a platform yet.'
    return (
        f"You are the official voice of the {party.name} ({party.abbreviation}), "
        f"a {party.get_ideology_display()} party. Speak on behalf of the party and stay "
        f"strictly consistent with its platform:\n\n{platform}"
    )


def _party_npc_username(party):
    from django.contrib.auth.models import User

    base = f"npc_{party.abbreviation.lower()}_hq"
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


@receiver(post_save, sender=Party)
def sync_party_npc_profile(sender, instance, created, **kwargs):
    """Give every party an NPC "HQ" account whose persona tracks the party's platform:
    created alongside the party, and refreshed whenever the platform text changes."""
    from forum.models import UserProfile
    from npcs.models import NPCProfile

    party = instance
    persona = _party_npc_persona(party)

    if created:
        from django.contrib.auth.models import User

        user = User.objects.create(username=_party_npc_username(party), first_name=party.name)
        user.set_unusable_password()
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.party = party
        profile.role = 'Party Headquarters'
        profile.save(update_fields=['party', 'role'])

        NPCProfile.objects.create(
            user_profile=profile,
            party=party,
            persona=persona,
        )
    else:
        npc_profile = getattr(party, 'npc_profile', None)
        if (
            npc_profile is not None
            and not npc_profile.persona_manually_edited
            and npc_profile.persona != persona
        ):
            npc_profile.persona = persona
            npc_profile.save(update_fields=['persona'])