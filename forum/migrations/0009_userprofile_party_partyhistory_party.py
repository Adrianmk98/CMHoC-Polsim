import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0008_remap_party_fk_to_parties_party'),
        ('parties', '0002_partymembership_unique_active_membership_per_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='party',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='tagged_profiles', to='parties.party',
            ),
        ),
        migrations.AlterField(
            model_name='partyhistory',
            name='party',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='history_entries', to='parties.party',
            ),
        ),
    ]
