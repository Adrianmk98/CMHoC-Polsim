from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from forum.models import Riding, UserProfile
from npcs.models import NPCProfile
from parties.models import Party, PartyMembership


class Command(BaseCommand):
    help = 'Create an AI-driven NPC character (User + UserProfile + NPCProfile) in one step'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--persona', required=True, help='Voice/ideology/tone seed for the system prompt')
        parser.add_argument('--first-name', default='')
        parser.add_argument('--last-name', default='')
        parser.add_argument('--party', default=None, help='Party code, e.g. LIB, CON, NDP, BQ, GRN, PPC, IND')
        parser.add_argument('--riding', default=None, help='Existing riding name')
        parser.add_argument('--role', default='MP')
        parser.add_argument('--reply-chance', type=float, default=0.4)
        parser.add_argument('--cooldown-minutes', type=int, default=20)

    def handle(self, *args, **options):
        username = options['username']
        if User.objects.filter(username=username).exists():
            raise CommandError(f'User "{username}" already exists')

        party = None
        if options['party']:
            party = Party.objects.filter(abbreviation__iexact=options['party']).first()
            if not party:
                raise CommandError(f'No Party with abbreviation "{options["party"]}"')

        riding = None
        if options['riding']:
            try:
                riding = Riding.objects.get(name=options['riding'])
            except Riding.DoesNotExist:
                raise CommandError(f'No Riding named "{options["riding"]}"')

        user = User.objects.create(
            username=username,
            first_name=options['first_name'],
            last_name=options['last_name'],
        )
        user.set_unusable_password()
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.riding = riding
        profile.role = options['role']
        profile.save()

        if party:
            PartyMembership.objects.get_or_create(
                user=user, party=party, defaults={'is_active': True}
            )

        NPCProfile.objects.create(
            user_profile=profile,
            persona=options['persona'],
            reply_chance=options['reply_chance'],
            cooldown_minutes=options['cooldown_minutes'],
        )

        self.stdout.write(self.style.SUCCESS(f'Created NPC "{username}"'))
