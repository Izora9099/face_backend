"""Dashboard, analytics and system administration."""

import json
import time
from datetime import timedelta

import psutil
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.models import Avg, Count, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .. import face_engine
from ..activity import log_user_activity
from ..models import (
    AdminUser, AttendanceRecord, AttendanceSession, Course, Department, Level,
    Specialization, Student, SystemBackup, SystemSettings, UserActivity,
)
from ..permissions import IsAdminRole, IsSuperAdmin, is_teacher
from ..serializers import (
    CourseStatsSerializer, DashboardStatsSerializer, DepartmentStatsSerializer,
    MessageSerializer, SystemBackupSerializer, SystemSettingsSerializer,
    SystemStatsSerializer, TeacherStatsSerializer, UserActivitySerializer,
)

ATTENDED = ('present', 'late')


def _rate(qs):
    total = qs.count()
    return round(qs.filter(status__in=ATTENDED).count() / total * 100, 2) if total else 0.0


# --------------------------
# Dashboard and analytics
# --------------------------
@extend_schema(responses=DashboardStatsSerializer)
@api_view(['GET'])
def dashboard_stats(request):
    """Headline numbers. Teachers get figures scoped to their own courses."""
    user = request.user
    today = timezone.localdate()
    courses = Course.objects.filter(status='active')
    records = AttendanceRecord.objects.all()
    sessions = AttendanceSession.objects.filter(status='active')
    students = Student.objects.filter(status='active')
    if is_teacher(user):
        courses = courses.filter(teachers=user)
        records = records.filter(course__in=courses)
        sessions = sessions.filter(course__in=courses)
        students = students.filter(enrolled_courses__in=courses).distinct()

    todays = records.filter(attendance_date=today)
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        trend.append({'day': day.strftime('%a'), 'date': day.isoformat(),
                      'rate': _rate(records.filter(attendance_date=day))})

    activities = UserActivity.objects.select_related('user').order_by('-timestamp')
    if is_teacher(user):
        activities = activities.filter(user=user)

    return Response({
        'total_students': students.count(),
        'total_courses': courses.count(),
        'total_departments': Department.objects.filter(is_active=True).count(),
        'total_specializations': Specialization.objects.filter(is_active=True).count(),
        'total_levels': Level.objects.filter(is_active=True).count(),
        'total_teachers': AdminUser.objects.filter(role='teacher', is_active=True).count(),
        'active_sessions': sessions.count(),
        'total_attendance_records': records.count(),
        'todays_attendance_count': todays.count(),
        'todays_attendance_rate': _rate(todays),
        'weekly_attendance_trend': trend,
        'recent_activities': UserActivitySerializer(activities[:5], many=True).data,
    })


@extend_schema(responses=DepartmentStatsSerializer(many=True))
@api_view(['GET'])
def department_stats(request):
    departments = Department.objects.filter(is_active=True).annotate(
        total_students=Count('students', filter=Q(students__status='active'), distinct=True),
        total_courses=Count('courses', filter=Q(courses__status='active'), distinct=True),
        total_specializations=Count('specializations', filter=Q(specializations__is_active=True), distinct=True),
    ).order_by('department_name')
    data = []
    for d in departments:
        data.append({
            'department_name': d.department_name,
            'total_students': d.total_students,
            'total_courses': d.total_courses,
            'total_specializations': d.total_specializations,
            'average_attendance_rate': _rate(AttendanceRecord.objects.filter(course__department=d)),
        })
    return Response(DepartmentStatsSerializer(data, many=True).data)


@extend_schema(responses=CourseStatsSerializer(many=True))
@api_view(['GET'])
def course_stats(request):
    courses = Course.objects.filter(status='active')
    if is_teacher(request.user):
        courses = courses.filter(teachers=request.user)
    courses = courses.annotate(
        enrolled=Count('enrolled_students', filter=Q(enrolled_students__status='active'), distinct=True),
        total_records=Count('attendance_records', distinct=True),
        attended=Count('attendance_records', filter=Q(attendance_records__status__in=ATTENDED), distinct=True),
    ).order_by('course_code')
    data = [{
        'course_code': c.course_code,
        'course_name': c.course_name,
        'enrolled_students': c.enrolled,
        'total_attendance_records': c.total_records,
        'average_attendance_rate': round(c.attended / c.total_records * 100, 2) if c.total_records else 0.0,
    } for c in courses]
    return Response(CourseStatsSerializer(data, many=True).data)


@extend_schema(responses=TeacherStatsSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAdminRole])
def teacher_stats(request):
    teachers = AdminUser.objects.filter(role='teacher', is_active=True).annotate(
        total_courses=Count('taught_courses', filter=Q(taught_courses__status='active'), distinct=True),
        total_students=Count('taught_courses__enrolled_students',
                             filter=Q(taught_courses__enrolled_students__status='active'), distinct=True),
        total_records=Count('taught_courses__attendance_records', distinct=True),
    ).order_by('first_name', 'last_name')
    data = [{
        'teacher_name': t.full_name or t.username,
        'total_courses': t.total_courses,
        'total_students': t.total_students,
        'total_attendance_records': t.total_records,
    } for t in teachers]
    return Response(TeacherStatsSerializer(data, many=True).data)


# --------------------------
# System management
# --------------------------
def _database_size():
    vendor = connection.vendor
    with connection.cursor() as cursor:
        if vendor == 'sqlite':
            cursor.execute('SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()')
        elif vendor == 'postgresql':
            cursor.execute('SELECT pg_database_size(current_database())')
        else:
            return 0
        row = cursor.fetchone()
    return row[0] if row else 0


@extend_schema(responses=SystemStatsSerializer)
@api_view(['GET'])
@permission_classes([IsAdminRole])
def system_stats(request):
    disk = psutil.disk_usage(str(settings.BASE_DIR))
    last_backup = SystemBackup.objects.first()
    stats = {
        'total_students': Student.objects.count(),
        'total_users': AdminUser.objects.count(),
        'total_attendance_records': AttendanceRecord.objects.count(),
        'total_courses': Course.objects.count(),
        'total_departments': Department.objects.count(),
        'total_specializations': Specialization.objects.count(),
        'total_levels': Level.objects.count(),
        'enrolled_faces': Student.objects.exclude(face_images_count=0).count(),
        'active_sessions': AttendanceSession.objects.filter(status='active').count(),
        'database_size': f'{_database_size() / (1024 * 1024):.2f} MB',
        'storage_used': f'{disk.used / (1024 ** 3):.2f} GB',
        'cpu_usage': psutil.cpu_percent(interval=None),
        'memory_usage': psutil.virtual_memory().percent,
        'disk_usage': disk.percent,
        'system_uptime': str(timedelta(seconds=int(time.time() - psutil.boot_time()))),
        'last_backup': last_backup.created_at.isoformat() if last_backup else 'Never',
        'system_version': settings.VERSION,
        'face_engine': face_engine.ENGINE_NAME,
        'face_match_threshold': face_engine.get_threshold(),
    }
    return Response(SystemStatsSerializer(stats).data)


@extend_schema(responses=SystemSettingsSerializer)
@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_system_settings(request):
    return Response(SystemSettingsSerializer(SystemSettings.get_settings()).data)


@extend_schema(request=SystemSettingsSerializer, responses=SystemSettingsSerializer)
@api_view(['POST', 'PUT', 'PATCH'])
@permission_classes([IsSuperAdmin])
def update_system_settings(request):
    serializer = SystemSettingsSerializer(SystemSettings.get_settings(), data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save(updated_by=request.user)
    log_user_activity(request.user, 'CHANGE_SECURITY_SETTINGS', 'system_settings',
                      f'Updated system settings: {", ".join(sorted(serializer.validated_data))}', request)
    return Response(serializer.data)


@extend_schema(request=None, responses=MessageSerializer)
@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def test_email_settings(request):
    from django.core.mail import get_connection, send_mail

    cfg = SystemSettings.get_settings()
    if not (cfg.email_enabled and cfg.smtp_host):
        return Response({'success': False, 'message': 'Email is disabled or SMTP host is not set.'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        conn = get_connection(host=cfg.smtp_host, port=cfg.smtp_port, username=cfg.smtp_username,
                              password=cfg.smtp_password, use_tls=cfg.smtp_use_tls, timeout=10)
        send_mail('FACE.IT test email', 'SMTP settings work.',
                  cfg.email_from_address or cfg.smtp_username, [request.user.email], connection=conn)
    except Exception as exc:
        return Response({'success': False, 'message': f'SMTP error: {exc}'}, status=status.HTTP_502_BAD_GATEWAY)
    return Response({'success': True, 'message': f'Test email sent to {request.user.email}'})


@extend_schema(request=None, responses={201: SystemBackupSerializer})
@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def create_backup(request):
    """JSON dump of the database (face encodings stay encrypted) into backups/."""
    backup_dir = settings.BASE_DIR / 'backups'
    backup_dir.mkdir(exist_ok=True)
    filename = f'backup_{timezone.now():%Y%m%d_%H%M%S}.json'
    path = backup_dir / filename
    with open(path, 'w', encoding='utf-8') as fh:
        call_command('dumpdata', '--natural-foreign', '--exclude=contenttypes', '--exclude=auth.permission',
                     '--exclude=sessions', '--exclude=admin.logentry', '--exclude=token_blacklist',
                     stdout=fh)
    backup = SystemBackup.objects.create(
        filename=filename, file_path=str(path), file_size=path.stat().st_size,
        backup_type='manual', created_by=request.user)
    log_user_activity(request.user, 'GENERATE_REPORT', 'backups', f'Created backup {filename}', request,
                      resource_id=backup.pk)
    return Response(SystemBackupSerializer(backup).data, status=status.HTTP_201_CREATED)


@extend_schema(responses=SystemBackupSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def list_backups(request):
    return Response(SystemBackupSerializer(SystemBackup.objects.all()[:50], many=True).data)


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([IsAdminRole])
def recognition_report(request):
    """Latest `evaluate_recognition` results (benchmark statistics), if generated."""
    path = settings.BASE_DIR / 'reports' / 'recognition_eval.json'
    if not path.exists():
        return Response({'available': False,
                         'message': 'Run `python manage.py evaluate_recognition` to generate the report.'})
    return Response({'available': True, **json.loads(path.read_text(encoding='utf-8'))})
