"""Timetable: entries, time slots, rooms and pickers."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..activity import log_user_activity
from ..models import AdminUser, Course, Room, TimeSlot, TimetableEntry
from ..permissions import is_admin, is_teacher
from ..serializers import (
    CourseBasicSerializer, MessageSerializer, RoomSerializer, TeacherBasicSerializer,
    TimeSlotSerializer, TimetableEntrySerializer,
)


def _forbidden():
    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)


def _save(serializer):
    try:
        return serializer.save(), None
    except DjangoValidationError as exc:
        return None, Response({'error': exc.messages}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(methods=['GET'], responses=TimetableEntrySerializer(many=True))
@extend_schema(methods=['POST'], request=TimetableEntrySerializer, responses={201: TimetableEntrySerializer})
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def timetable_entries(request):
    if request.method == 'GET':
        qs = TimetableEntry.objects.filter(is_active=True) \
            .select_related('course', 'teacher', 'time_slot', 'room')
        p = request.query_params
        for param, field in (('teacher_id', 'teacher_id'), ('course_id', 'course_id'),
                             ('room_id', 'room_id'), ('academic_year', 'academic_year'),
                             ('semester', 'semester')):
            if p.get(param):
                qs = qs.filter(**{field: p[param]})
        if p.get('level') and p['level'] != 'all':
            qs = qs.filter(course__level__level_name=p['level'])
        if p.get('department') and p['department'] != 'all':
            qs = qs.filter(course__department__department_name=p['department'])
        if is_teacher(request.user):
            qs = qs.filter(teacher=request.user)
        return Response(TimetableEntrySerializer(qs, many=True).data)

    if not is_admin(request.user):
        return _forbidden()
    serializer = TimetableEntrySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    entry, error = _save(serializer)
    if error:
        return error
    log_user_activity(request.user, 'CREATE_TIMETABLE_ENTRY', 'timetable',
                      f'Created timetable entry for {entry.course.course_code}', request, resource_id=entry.id)
    return Response(TimetableEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@extend_schema(methods=['GET', 'PUT', 'PATCH'], request=TimetableEntrySerializer,
               responses=TimetableEntrySerializer)
@extend_schema(methods=['DELETE'], request=None, responses=MessageSerializer)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def timetable_entry_detail(request, entry_id):
    entry = TimetableEntry.objects.filter(id=entry_id).first()
    if not entry:
        return Response({'error': 'Timetable entry not found'}, status=status.HTTP_404_NOT_FOUND)
    if is_teacher(request.user) and entry.teacher_id != request.user.pk:
        return _forbidden()

    if request.method == 'GET':
        return Response(TimetableEntrySerializer(entry).data)
    if not is_admin(request.user):
        return _forbidden()

    if request.method == 'DELETE':
        course_code = entry.course.course_code
        entry.delete()
        log_user_activity(request.user, 'DELETE_TIMETABLE_ENTRY', 'timetable',
                          f'Deleted timetable entry for {course_code}', request, resource_id=entry_id)
        return Response({'message': 'Timetable entry deleted successfully'})

    serializer = TimetableEntrySerializer(entry, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    updated, error = _save(serializer)
    if error:
        return error
    log_user_activity(request.user, 'UPDATE_TIMETABLE_ENTRY', 'timetable',
                      f'Updated timetable entry for {updated.course.course_code}', request, resource_id=updated.id)
    return Response(TimetableEntrySerializer(updated).data)


def _list_or_create(request, queryset, serializer_class, action, label):
    if request.method == 'GET':
        return Response(serializer_class(queryset, many=True).data)
    if not is_admin(request.user):
        return _forbidden()
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save()
    log_user_activity(request.user, action, label, f'Created {label} {obj}', request, resource_id=obj.id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(methods=['GET'], responses=TimeSlotSerializer(many=True))
@extend_schema(methods=['POST'], request=TimeSlotSerializer, responses={201: TimeSlotSerializer})
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def time_slots(request):
    return _list_or_create(request, TimeSlot.objects.all(), TimeSlotSerializer, 'CREATE_TIME_SLOT', 'timeslot')


@extend_schema(methods=['GET'], responses=RoomSerializer(many=True))
@extend_schema(methods=['POST'], request=RoomSerializer, responses={201: RoomSerializer})
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def rooms(request):
    return _list_or_create(request, Room.objects.filter(is_available=True), RoomSerializer, 'CREATE_ROOM', 'room')


@extend_schema(responses=TeacherBasicSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def timetable_teachers(request):
    teachers = AdminUser.objects.filter(role='teacher', is_active=True).order_by('first_name', 'last_name')
    return Response(TeacherBasicSerializer(teachers, many=True).data)


@extend_schema(responses=CourseBasicSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def timetable_courses(request):
    courses = Course.objects.filter(status='active').order_by('course_code')
    if is_teacher(request.user):
        courses = courses.filter(teachers=request.user)
    return Response(CourseBasicSerializer(courses, many=True).data)
