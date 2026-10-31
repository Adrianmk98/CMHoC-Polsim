from django.db import migrations


def remap_party_fk(apps, schema_editor):
    """UserProfile.party/PartyHistory.party are about to be repointed from the
    hardcoded forum.PoliticalParty enum to the real, joinable parties.Party model.
    Remap existing data by abbreviation where a matching org exists; drop what can't
    be matched rather than leave it pointing at the wrong row once the FK changes."""
    PoliticalParty = apps.get_model('forum', 'PoliticalParty')
    Party = apps.get_model('parties', 'Party')
    UserProfile = apps.get_model('forum', 'UserProfile')
    PartyHistory = apps.get_model('forum', 'PartyHistory')

    code_to_party_id = {}
    for poli in PoliticalParty.objects.all():
        match = Party.objects.filter(abbreviation__iexact=poli.name).first()
        code_to_party_id[poli.id] = match.id if match else None

    for profile_id, old_party_id in UserProfile.objects.exclude(
        party_id__isnull=True
    ).values_list('id', 'party_id'):
        UserProfile.objects.filter(pk=profile_id).update(
            party_id=code_to_party_id.get(old_party_id)
        )

    for history in PartyHistory.objects.exclude(party_id__isnull=True):
        new_id = code_to_party_id.get(history.party_id)
        if new_id is None:
            history.delete()
        else:
            PartyHistory.objects.filter(pk=history.pk).update(party_id=new_id)


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0007_alter_cabinet_id_alter_cabinetposition_id_and_more'),
        ('parties', '0002_partymembership_unique_active_membership_per_user'),
    ]

    operations = [
        migrations.RunPython(remap_party_fk, migrations.RunPython.noop),
    ]
