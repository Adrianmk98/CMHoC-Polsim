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


def get_moderator_permissions(user):
    """Get dict of all moderator permissions for a user"""
    return {
        'is_moderator': is_moderator(user),
        'can_manage_elections': can_manage_elections(user),
        'can_manage_cabinet': can_manage_cabinet(user),
        'can_manage_bills': can_manage_bills(user),
        'can_manage_users': can_manage_users(user),
    }