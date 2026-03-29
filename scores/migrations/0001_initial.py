from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ParliamentSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['-start_date'],
            },
        ),
        migrations.CreateModel(
            name='PlayerLT',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lt_score', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=8)),
                ('is_active_persona', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_lts', to='scores.parliamentsession')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lt_scores', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['user__username'],
                'unique_together': {('session', 'user')},
            },
        ),
        migrations.CreateModel(
            name='ScoreEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score_type', models.CharField(choices=[('DEBATE', 'Debate'), ('PRESS', 'Press'), ('LEGISLATION', 'Legislation'), ('CAMPAIGN', 'Campaign')], max_length=20)),
                ('score', models.DecimalField(decimal_places=2, max_digits=8)),
                ('description', models.CharField(blank=True, max_length=300)),
                ('bill_id', models.IntegerField(blank=True, null=True)),
                ('press_release_id', models.IntegerField(blank=True, null=True)),
                ('thread_id', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_entries', to='scores.parliamentsession')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_entries', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='score_entries_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
