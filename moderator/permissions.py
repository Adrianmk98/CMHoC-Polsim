"""
Moderator permission checking utilities
"""

def is_moderator(user):
    """Check if user has any moderator permissions"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.is_moderator
    except:
        return False


def can_manage_elections(user):
    """Check if user can manage elections"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.is_moderator and user.profile.can_manage_elections
    except:
        return False


def can_manage_cabinet(user):
    """Check if user can manage cabinet"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.is_moderator and user.profile.can_manage_cabinet
    except:
        return False


def can_manage_bills(user):
    """Check if user can manage bills"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.is_moderator and user.profile.can_manage_bills
    except:
        return False


def can_manage_users(user):
    """Check if user can manage users"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.is_moderator and user.profile.can_manage_users
    except:
        return False


def can_manage_scores(user):
    """Check if user can enter/edit player scores"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.is_moderator and user.profile.can_manage_scores
    except:
        return False


def can_manage_parties(user):
    """Check if user can manage parties (members, roles, join requests)"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    try:
        return user.profile.is_moderator and user.profile.can_manage_parties
    except:
        return False


def is_sitting_member(user, chamber):
    """Check if user currently holds the seat needed to vote in the given chamber
    (MP for the Commons, Senator for the Senate)."""
    if not user.is_authenticated:
        return False
    from forum.models import PositionHistory
    position_type = 'SENATOR' if chamber == 'SENATE' else 'MP'
    return PositionHistory.objects.filter(
        user_profile__user=user,
        position_type=position_type,
        end_date__isnull=True,
    ).exists()


def is_speaker(user):
    """Check if user currently holds the Speaker or Deputy Speaker position"""
    if not user.is_authenticated:
        return False
    from forum.models import PositionHistory
    return PositionHistory.objects.filter(
        user_profile__user=user,
        position_type__in=['SPEAKER', 'DEPUTY_SPEAKER'],
        end_date__isnull=True,
    ).exists()


def get_moderator_permissions(user):
    """Get dict of all moderator permissions for a user"""
    return {
        'is_moderator': is_moderator(user),
        'can_manage_elections': can_manage_elections(user),
        'can_manage_cabinet': can_manage_cabinet(user),
        'can_manage_bills': can_manage_bills(user),
        'can_manage_users': can_manage_users(user),
        'can_manage_scores': can_manage_scores(user),
        'can_manage_parties': can_manage_parties(user),
    }