"""Audit trail, login attempts, active sessions and security settings (superadmin/staff)."""

from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..activity import log_user_activity
from ..models import ActiveSession, LoginAttempt, SecuritySettings, UserActivity
from ..permissions import IsAdminRole, IsSuperAdmin
from ..serializers import (
    ActiveSessionSerializer, LoginAttemptSerializer, MessageSerializer,
    SecuritySettingsSerializer, SecurityStatisticsSerializer, UserActivitySerializer,
)

DAYS = OpenApiParameter('days', int, description='Look-back window in days (default 7)')


def _since(request):
    try:
        days = max(1, min(int(request.query_params.get('days', 7)), 365))
    except ValueError:
        days = 7
    return timezone.now() - timedelta(days=days)


@extend_schema(parameters=[DAYS, OpenApiParameter('user', str), OpenApiParameter('action', str),
                           OpenApiParameter('status', str)],
               responses=UserActivitySerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_user_activities(request):
    qs = UserActivity.objects.filter(timestamp__gte=_since(request)).select_related('user')
    p = request.query_params
    if p.get('user') and p['user'] != 'all':
        qs = qs.filter(user__username__icontains=p['user'])
    if p.get('action') and p['action'] != 'all':
        qs = qs.filter(action=p['action'])
    if p.get('status') and p['status'] != 'all':
        qs = qs.filter(status=p['status'])
    return Response(UserActivitySerializer(qs.order_by('-timestamp')[:200], many=True).data)


@extend_schema(parameters=[DAYS], responses=LoginAttemptSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_login_attempts(request):
    qs = LoginAttempt.objects.filter(timestamp__gte=_since(request)).order_by('-timestamp')[:100]
    return Response(LoginAttemptSerializer(qs, many=True).data)


@extend_schema(responses=ActiveSessionSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_active_sessions(request):
    qs = ActiveSession.objects.filter(is_active=True).select_related('user').order_by('-last_activity')
    return Response(ActiveSessionSerializer(qs, many=True).data)


@extend_schema(parameters=[DAYS], responses=SecurityStatisticsSerializer)
@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_security_statistics(request):
    since = _since(request)
    attempts = LoginAttempt.objects.filter(timestamp__gte=since)
    return Response({
        'total_login_attempts': attempts.count(),
        'successful_logins': attempts.filter(success=True).count(),
        'failed_logins': attempts.filter(success=False).count(),
        'unique_users': attempts.values('username').distinct().count(),
        'suspicious_activities': UserActivity.objects.filter(timestamp__gte=since, status='warning').count(),
        'active_sessions': ActiveSession.objects.filter(is_active=True).count(),
    })


@extend_schema(responses=SecuritySettingsSerializer)
@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_security_settings(request):
    return Response(SecuritySettingsSerializer(SecuritySettings.get_settings()).data)


@extend_schema(request=SecuritySettingsSerializer, responses=SecuritySettingsSerializer)
@api_view(['POST', 'PUT', 'PATCH'])
@permission_classes([IsSuperAdmin])
def update_security_settings(request):
    settings_obj = SecuritySettings.get_settings()
    serializer = SecuritySettingsSerializer(settings_obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save(updated_by=request.user)
    log_user_activity(request.user, 'CHANGE_SECURITY_SETTINGS', 'security_settings',
                      f'Updated security settings: {", ".join(sorted(serializer.validated_data))}', request)
    return Response(serializer.data)


@extend_schema(request=None, responses=MessageSerializer)
@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def terminate_session(request, session_id):
    session = ActiveSession.objects.filter(session_key=session_id).first() \
        or ActiveSession.objects.filter(pk=session_id if str(session_id).isdigit() else None).first()
    if not session:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
    session.is_active = False
    session.save(update_fields=['is_active'])
    log_user_activity(request.user, 'TERMINATE_SESSION', 'sessions',
                      f'Terminated session of {session.user.username}', request, resource_id=session.pk)
    return Response({'message': 'Session terminated successfully'})
