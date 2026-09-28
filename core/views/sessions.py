"""
Session-based attendance (Android contract).

Paths and response keys here are consumed by the Android app; only add keys,
never rename or remove them.
"""

import logging

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .. import face_engine
from ..activity import log_user_activity
from ..models import AttendanceSession, Course, SessionCheckIn
from ..permissions import IsAdminOrTeacher, can_access_course, is_teacher
from ..serializers import (
    AttendanceSessionSerializer, CheckInRequestSerializer, CheckInResponseSerializer,
    ManualMarkRequestSerializer, SessionCheckInSerializer, SessionEndRequestSerializer,
    SessionResponseSerializer, SessionStartRequestSerializer, SessionStatsResponseSerializer,
    SessionStatsSerializer,
)

logger = logging.getLogger('core.face_engine')


def _fail(message, http_status, **extra):
    return Response({'success': False, 'message': message, **extra}, status=http_status)


def _can_manage_session(user, session):
    if is_teacher(user):
        return session.teacher_id == user.pk or can_access_course(user, session.course)
    return can_access_course(user, session.course)


def timing_status(session, at=None):
    """present within the grace period, late until the expected end, absent after."""
    at = at or timezone.now()
    grace_end = session.start_time + timezone.timedelta(minutes=session.grace_period_minutes)
    if at <= grace_end:
        return 'present'
    if session.expected_end_time and at <= session.expected_end_time:
        return 'late'
    return 'absent'


@extend_schema(request=SessionStartRequestSerializer, responses={201: SessionResponseSerializer})
@api_view(['POST'])
@permission_classes([IsAdminOrTeacher])
def start_attendance_session(request):
    serializer = SessionStartRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _fail('Course ID is required' if 'course_id' in serializer.errors else 'Invalid request',
                     status.HTTP_400_BAD_REQUEST, errors=serializer.errors)
    data = serializer.validated_data

    course = Course.objects.filter(id=data['course_id'], status='active').first()
    if not course:
        return _fail('Course not found or inactive', status.HTTP_404_NOT_FOUND)
    if not can_access_course(request.user, course):
        return _fail('Access denied to this course', status.HTTP_403_FORBIDDEN)

    existing = AttendanceSession.objects.filter(course=course, status='active').first()
    if existing and existing.should_auto_close:
        existing.end_session(auto_closed=True)
        existing = None
    if existing:
        return _fail('An active session already exists for this course',
                     status.HTTP_400_BAD_REQUEST, session_id=existing.session_id)

    session = AttendanceSession.objects.create(
        course=course,
        teacher=request.user,
        session_duration_minutes=data['duration_minutes'],
        grace_period_minutes=data['grace_period_minutes'],
        room=data['room'],
    )
    log_user_activity(request.user, 'MARK_ATTENDANCE', 'sessions',
                      f'Started attendance session for {course.course_code}', request, resource_id=session.pk)
    return Response({
        'success': True,
        'message': f'Attendance session started for {course.course_code}',
        'session_id': session.session_id,
        'session': AttendanceSessionSerializer(session).data,
    }, status=status.HTTP_201_CREATED)


@extend_schema(request=SessionEndRequestSerializer, responses=SessionResponseSerializer)
@api_view(['POST'])
@permission_classes([IsAdminOrTeacher])
def end_attendance_session(request):
    session_id = request.data.get('session_id')
    if not session_id:
        return _fail('Session ID is required', status.HTTP_400_BAD_REQUEST)
    session = get_object_or_404(AttendanceSession.objects.select_related('course'), session_id=session_id)
    if not _can_manage_session(request.user, session):
        return _fail('Access denied to this session', status.HTTP_403_FORBIDDEN)
    if session.status != 'active':
        return _fail(f'Session is already {session.status}', status.HTTP_400_BAD_REQUEST)

    session.end_session(auto_closed=False)
    log_user_activity(request.user, 'MARK_ATTENDANCE', 'sessions',
                      f'Ended attendance session for {session.course.course_code}', request,
                      resource_id=session.pk)
    return Response({
        'success': True,
        'message': f'Session ended for {session.course.course_code}',
        'session': AttendanceSessionSerializer(session).data,
    })


@extend_schema(request={'multipart/form-data': CheckInRequestSerializer},
               responses={201: CheckInResponseSerializer, 404: CheckInResponseSerializer})
@api_view(['POST'])
@permission_classes([AllowAny])  # Android kiosk flow; the active session id is the capability.
@parser_classes([MultiPartParser, FormParser])
def session_based_attendance(request):
    """Recognise the face in `image` among the students enrolled in the session's course."""
    session_id = request.data.get('session_id')
    image_file = request.FILES.get('image')
    if not session_id:
        return _fail('Session ID is required', status.HTTP_400_BAD_REQUEST)
    if not image_file:
        return _fail('Face image is required', status.HTTP_400_BAD_REQUEST)

    session = AttendanceSession.objects.select_related('course', 'teacher') \
        .filter(session_id=session_id, status='active').first()
    if not session:
        return _fail('No active session with this ID', status.HTTP_404_NOT_FOUND)
    if session.should_auto_close:
        session.end_session(auto_closed=True)
        return _fail('Session has ended', status.HTTP_400_BAD_REQUEST)

    try:
        probe = face_engine.encode_single(image_file)
    except face_engine.FaceEngineError as exc:
        return _fail(str(exc), status.HTTP_400_BAD_REQUEST, code=exc.code)

    enrolled = session.course.enrolled_students.filter(status='active').only('id', 'face_encoding')
    result = face_engine.match(probe, face_engine.student_candidates(enrolled))
    if not result.matched:
        return _fail('Student not recognized or not enrolled in this course', status.HTTP_404_NOT_FOUND,
                     confidence=result.confidence, distance=result.distance, threshold=result.threshold)

    student = session.course.enrolled_students.get(pk=result.student_id)
    if SessionCheckIn.objects.filter(attendance_session=session, student=student).exists():
        return _fail(f'{student.full_name} has already checked in for this session',
                     status.HTTP_400_BAD_REQUEST, student_name=student.full_name)

    # An explicit status is only honoured from an authenticated course owner/admin.
    requested = request.data.get('status')
    user = request.user if request.user.is_authenticated else None
    if requested in dict(SessionCheckIn.STATUS_CHOICES) and user and _can_manage_session(user, session):
        attendance_status = requested
    else:
        attendance_status = timing_status(session)

    try:
        with transaction.atomic():
            checkin = SessionCheckIn.objects.create(
                attendance_session=session,
                student=student,
                status=attendance_status,
                recognition_confidence=result.confidence,
            )
    except IntegrityError:
        return _fail(f'{student.full_name} has already checked in for this session',
                     status.HTTP_400_BAD_REQUEST, student_name=student.full_name)

    log_user_activity(user or session.teacher, 'USE_FACE_RECOGNITION', 'attendance',
                      f'Session check-in: {student.full_name} - {attendance_status}', request,
                      resource_id=checkin.pk)
    return Response({
        'success': True,
        'message': f'{student.full_name} checked in successfully',
        'student_id': student.id,
        'student_name': student.full_name,
        'matric_number': student.matric_number,
        'status': attendance_status,
        'check_in_time': checkin.check_in_time,
        'confidence': result.confidence,
        'distance': result.distance,
        'threshold': result.threshold,
    }, status=status.HTTP_201_CREATED)


@extend_schema(request=ManualMarkRequestSerializer, responses={200: SessionCheckInSerializer})
@api_view(['POST'])
@permission_classes([IsAdminOrTeacher])
def manual_mark(request, session_id):
    """Manual override: set a student's status in a session (e.g. recognition failed, excused)."""
    session = get_object_or_404(AttendanceSession.objects.select_related('course'), session_id=session_id)
    if not _can_manage_session(request.user, session):
        return _fail('Access denied to this session', status.HTTP_403_FORBIDDEN)

    serializer = ManualMarkRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    student = session.course.enrolled_students.filter(pk=data['student_id']).first()
    if not student:
        return _fail('Student is not enrolled in this course', status.HTTP_400_BAD_REQUEST)

    checkin = SessionCheckIn.objects.filter(attendance_session=session, student=student).first()
    if checkin:
        checkin.status = data['status']
        checkin.is_manual_override = True
        checkin.notes = data['notes']
        checkin.save()
    else:
        checkin = SessionCheckIn.objects.create(
            attendance_session=session, student=student, status=data['status'],
            is_manual_override=True, notes=data['notes'])

    log_user_activity(request.user, 'MARK_ATTENDANCE', 'attendance',
                      f'Manual override: {student.full_name} -> {data["status"]} ({session.course.course_code})',
                      request, resource_id=checkin.pk)
    return Response(SessionCheckInSerializer(checkin).data)


@extend_schema(responses=SessionStatsResponseSerializer)
@api_view(['GET'])
@permission_classes([IsAdminOrTeacher])
def get_session_stats(request, session_id):
    session = get_object_or_404(AttendanceSession.objects.select_related('course'), session_id=session_id)
    if not _can_manage_session(request.user, session):
        return _fail('Access denied to this session', status.HTTP_403_FORBIDDEN)
    if session.should_auto_close:
        session.end_session(auto_closed=True)
    return Response({'success': True, 'stats': SessionStatsSerializer(session).data})


@extend_schema(responses=AttendanceSessionSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAdminOrTeacher])
def list_sessions(request):
    """Sessions visible to the caller. Filters: ?status=active|completed, ?course=<id>."""
    qs = AttendanceSession.objects.select_related('course', 'teacher')
    if is_teacher(request.user):
        qs = qs.filter(course__teachers=request.user).distinct()
    if request.query_params.get('status'):
        qs = qs.filter(status=request.query_params['status'])
    if request.query_params.get('course'):
        qs = qs.filter(course_id=request.query_params['course'])
    return Response(AttendanceSessionSerializer(qs[:200], many=True).data)
