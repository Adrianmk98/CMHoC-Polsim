"""Helper for writing moderator.AuditLog entries from mod views."""


def log_action(user, action, obj, changes=None, view_name=None, target_repr=None):
    """Record a moderator action.

    - user: the acting user (request.user)
    - action: one of AuditLog.ACTION_CHOICES
    - obj: the model instance affected (used for target_type/target_id/target_repr)
    - changes: dict of {field: [old, new]} for updates, or any JSON-able description
    - view_name: name of the view that made the change, for traceability
    - target_repr: override for the human-readable label (falls back to str(obj))
    """
    from .models import AuditLog

    if target_repr is None:
        try:
            target_repr = str(obj)
        except Exception:
            target_repr = f"{obj.__class__.__name__} #{getattr(obj, 'pk', '?')}"

    AuditLog.objects.create(
        actor=user if getattr(user, 'is_authenticated', False) else None,
        action=action,
        target_type=obj.__class__.__name__,
        target_id=str(getattr(obj, 'pk', '') or ''),
        target_repr=target_repr[:300],
        view_name=view_name or '',
        changes=changes,
    )


def diff_fields(instance, fields, before):
    """Build a {field: [old, new]} dict for the given field names, comparing `before`
    (a dict of old values captured prior to mutating `instance`) against the instance's
    current values. Only includes fields that actually changed."""
    changes = {}
    for field in fields:
        old = before.get(field)
        new = getattr(instance, field)
        old_cmp = str(old) if old is not None else None
        new_cmp = str(new) if new is not None else None
        if old_cmp != new_cmp:
            changes[field] = [old_cmp, new_cmp]
    return changes
