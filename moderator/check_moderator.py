from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from forum.models import UserProfile


class Command(BaseCommand):
    help = 'Check moderator status and permissions for a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to check')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ User "{username}" does not exist'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n👤 User: {username}'))
        self.stdout.write(f'   Staff Status: {user.is_staff}')
        
        # Check if profile exists
        try:
            profile = user.profile
            self.stdout.write(self.style.SUCCESS(f'\n✅ Profile exists'))
            
            self.stdout.write(f'\n🔐 Moderator Permissions:')
            self.stdout.write(f'   is_moderator: {profile.is_moderator}')
            self.stdout.write(f'   can_manage_elections: {profile.can_manage_elections}')
            self.stdout.write(f'   can_manage_cabinet: {profile.can_manage_cabinet}')
            self.stdout.write(f'   can_manage_bills: {profile.can_manage_bills}')
            self.stdout.write(f'   can_manage_users: {profile.can_manage_users}')
            
            # Test permission functions
            from moderator.permissions import (
                is_moderator,
                can_manage_elections,
                can_manage_cabinet,
                can_manage_bills,
                can_manage_users
            )
            
            self.stdout.write(f'\n🧪 Permission Function Tests:')
            self.stdout.write(f'   is_moderator(user): {is_moderator(user)}')
            self.stdout.write(f'   can_manage_elections(user): {can_manage_elections(user)}')
            self.stdout.write(f'   can_manage_cabinet(user): {can_manage_cabinet(user)}')
            self.stdout.write(f'   can_manage_bills(user): {can_manage_bills(user)}')
            self.stdout.write(f'   can_manage_users(user): {can_manage_users(user)}')
            
            if is_moderator(user):
                self.stdout.write(self.style.SUCCESS(f'\n✅ {username} has moderator access'))
            else:
                self.stdout.write(self.style.WARNING(f'\n⚠️  {username} does NOT have moderator access'))
                if not profile.is_moderator:
                    self.stdout.write(self.style.ERROR('   is_moderator is False'))
                    
        except UserProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ No profile exists for {username}'))
            self.stdout.write(f'   Run: python manage.py make_moderator {username} --elections')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {e}'))