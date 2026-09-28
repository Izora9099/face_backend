"""Automatic activity logging and active-session tracking."""

import logging

from django.utils import timezone

from .activity import get_client_ip, log_user_activity
from .models import ActiveSession, SecuritySettings

logger = logging.getLogger('security')

# (path fragment, method) -> (action, resource, details)
_ROUTES = [
    ('/students/', 'GET', ('VIEW_STUDENTS', 'students', 'Viewed student list or details')),
    ('/students/', 'POST', ('CREATE_STUDENT', 'students', 'Created new student')),
    ('/students/', 'PUT', ('UPDATE_STUDENT', 'students', 'Updated student information')),
    ('/students/', 'PATCH', ('UPDATE_STUDENT', 'students', 'Updated student information')),
    ('/admin-users/', 'GET', ('VIEW_ADMIN_USERS', 'admin_users', 'Viewed admin users list')),
    ('/security/settings', 'POST', ('CHANGE_SECURITY_SETTINGS', 'security_settings', 'Changed security settings')),
]


class ActivityLoggingMiddleware:
    """Tracks active sessions and records coarse-grained reads/writes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, 'user', None) and request.user.is_authenticated:
            self._touch_session(request)
        response = self.get_response(request)
        # DRF authenticates JWT inside the view, so check the user again here.
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and 200 <= response.status_code < 300:
            self._log(request)
        return response

    def _touch_session(self, request):
        session_key = getattr(request, 'session', None) and request.session.session_key
        if not session_key:
            return
        try:
            session, created = ActiveSession.objects.get_or_create(
                session_key=session_key,
                defaults={
                    'user': request.user,
                    'ip_address': get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'location': _location(get_client_ip(request)),
                },
            )
            if not created:
                session.last_activity = timezone.now()
                session.save(update_fields=['last_activity'])
        except Exception:
            logger.exception('failed to update active session')

    def _log(self, request):
        for fragment, method, (action, resource, details) in _ROUTES:
            if fragment in request.path and request.method == method:
                if SecuritySettings.get_settings().log_all_activities:
                    log_user_activity(request.user, action, resource, details, request)
                return


def _location(ip):
    if ip and (ip.startswith('192.168.') or ip.startswith('127.') or ip.startswith('10.')):
        return 'Local Network'
    return 'Unknown Location'
