from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from forum.models import UserProfile


class Command(BaseCommand):
    help = 'Make a user a moderator with specified permissions'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to make moderator')
        parser.add_argument('--elections', action='store_true', help='Grant election management permission')
        parser.add_argument('--cabinet', action='store_true', help='Grant cabinet management permission')
        parser.add_argument('--bills', action='store_true', help='Grant bill management permission')
        parser.add_argument('--users', action='store_true', help='Grant user management permission')
        parser.add_argument('--all', action='store_true', help='Grant all permissions')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not exist'))
            return
        
        # Get or create profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created profile for {username}'))
        
        # Set moderator flag
        profile.is_moderator = True
        
        # Set specific permissions
        if options['all']:
            profile.can_manage_elections = True
            profile.can_manage_cabinet = True
            profile.can_manage_bills = True
            profile.can_manage_users = True
            self.stdout.write(self.style.SUCCESS('Granted ALL permissions'))
        else:
            if options['elections']:
                profile.can_manage_elections = True
                self.stdout.write(self.style.SUCCESS('Granted election management permission'))
            if options['cabinet']:
                profile.can_manage_cabinet = True
                self.stdout.write(self.style.SUCCESS('Granted cabinet management permission'))
            if options['bills']:
                profile.can_manage_bills = True
                self.stdout.write(self.style.SUCCESS('Granted bill management permission'))
            if options['users']:
                profile.can_manage_users = True
                self.stdout.write(self.style.SUCCESS('Granted user management permission'))
        
        profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ {username} is now a moderator!'))
        self.stdout.write(f'Permissions:')
        self.stdout.write(f'  - Elections: {profile.can_manage_elections}')
        self.stdout.write(f'  - Cabinet: {profile.can_manage_cabinet}')
        self.stdout.write(f'  - Bills: {profile.can_manage_bills}')
        self.stdout.write(f'  - Users: {profile.can_manage_users}')