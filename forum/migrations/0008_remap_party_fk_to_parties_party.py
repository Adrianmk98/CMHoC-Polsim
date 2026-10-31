from django.db import migrations


def remap_party_fk(apps, schema_editor):
    """UserProfile.party/PartyHistory.party are about to be repointed from the
    hardcoded forum.PoliticalParty enum to the real, joinable parties.Party model.
    party_id values currently reference forum_politicalparty rows; those IDs are
    not valid parties_party rows (different table, unrelated PK sequence), so
    writing a 'matching' parties.Party PK into the column here would violate the
    FK constraint that still points at forum_politicalparty until the AlterField
    in the next migration runs. Null everything out now (always valid under any
    FK constraint) - this app's data is test/seed data that gets reseeded under
    the new party-org model right after this migration anyway."""
    UserProfile = apps.get_model('forum', 'UserProfile')
    PartyHistory = apps.get_model('forum', 'PartyHistory')

    UserProfile.objects.update(party_id=None)
    PartyHistory.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0007_alter_cabinet_id_alter_cabinetposition_id_and_more'),
        ('parties', '0002_partymembership_unique_active_membership_per_user'),
    ]

    operations = [
        migrations.RunPython(remap_party_fk, migrations.RunPython.noop),
    ]
