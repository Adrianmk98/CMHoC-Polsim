from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Count

from parties.models import PartyMembership


class Command(BaseCommand):
    help = (
        'Report users with more than one active PartyMembership. '
        'Run this before applying the unique_active_membership_per_user migration, '
        'since that migration will fail if any such rows exist.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help=(
                'Deactivate all but the most recently joined active membership '
                'for each conflicting user, instead of just reporting them.'
            ),
        )

    def handle(self, *args, **options):
        conflicting_user_ids = (
            PartyMembership.objects.filter(is_active=True)
            .values('user')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .values_list('user', flat=True)
        )

        if not conflicting_user_ids:
            self.stdout.write(self.style.SUCCESS('No dual memberships found.'))
            return

        for user in User.objects.filter(id__in=conflicting_user_ids):
            memberships = PartyMembership.objects.filter(
                user=user, is_active=True
            ).select_related('party').order_by('-joined_at')

            self.stdout.write(self.style.WARNING(f'{user.username} (id={user.id}):'))
            for m in memberships:
                self.stdout.write(f'    membership id={m.pk} party={m.party.abbreviation} joined_at={m.joined_at}')

            if options['fix']:
                keep = memberships.first()
                to_deactivate = memberships.exclude(pk=keep.pk)
                for m in to_deactivate:
                    m.is_active = False
                    m.left_at = m.left_at or keep.joined_at
                    m.save(update_fields=['is_active', 'left_at'])
                    self.stdout.write(f'    -> deactivated membership id={m.pk} ({m.party.abbreviation})')
                self.stdout.write(f'    kept membership id={keep.pk} ({keep.party.abbreviation})')

        if not options['fix']:
            self.stdout.write(self.style.NOTICE('\nRe-run with --fix to keep the most recent membership for each user and deactivate the rest.'))
