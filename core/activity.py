"""Audit-trail helper shared by views and middleware."""

import logging

from .models import UserActivity

logger = logging.getLogger('security')


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or '0.0.0.0'


def log_user_activity(user, action, resource, details, request, resource_id=None, status='success'):
    """Record an audit entry. Never pass images or face encodings in `details`."""
    if not user or not user.is_authenticated:
        return
    session = getattr(request, 'session', None)
    try:
        UserActivity.objects.create(
            user=user,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            session_id=(session.session_key or '') if session is not None else '',
            status=status,
        )
    except Exception:
        # Auditing must never break the request it describes.
        logger.exception('failed to record activity %s for user_id=%s', action, user.pk)
