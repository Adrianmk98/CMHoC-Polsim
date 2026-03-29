from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BillDebatePost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reading_stage', models.CharField(choices=[('DRAFT', 'Draft'), ('FIRST_READING', 'First Reading'), ('SECOND_READING', 'Second Reading'), ('COMMITTEE', 'In Committee'), ('THIRD_READING', 'Third Reading'), ('ROYAL_ASSENT', 'Royal Assent'), ('FAILED', 'Failed')], max_length=20)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='debate_posts', to='voting.bill')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='debate_posts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
