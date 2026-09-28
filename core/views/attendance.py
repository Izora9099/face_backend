"""Attendance records (manual marking, corrections, history)."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..activity import log_user_activity
from ..models import AttendanceRecord
from ..permissions import IsAdminOrTeacher, can_access_course, is_teacher
from ..serializers import (
    AttendanceCreateSerializer, AttendanceListSerializer, AttendanceRecordSerializer,
)
from .students import StandardPagination


def records_visible_to(user):
    qs = AttendanceRecord.objects.select_related('student', 'course')
    if is_teacher(user):
        qs = qs.filter(course__teachers=user)
    return qs


def _filter(qs, params):
    for names, field in ((('student', 'student_id'), 'student_id'),
                         (('course', 'course_id'), 'course_id'),
                         (('status',), 'status')):
        value = next((params[n] for n in names if params.get(n)), None)
        if value:
            qs = qs.filter(**{field: value})
    if params.get('date'):
        qs = qs.filter(attendance_date=params['date'])
    if params.get('date_from'):
        qs = qs.filter(attendance_date__gte=params['date_from'])
    if params.get('date_to'):
        qs = qs.filter(attendance_date__lte=params['date_to'])
    return qs


@extend_schema(parameters=[
    OpenApiParameter('student_id', int), OpenApiParameter('course_id', int),
    OpenApiParameter('status', str, enum=[c for c, _ in AttendanceRecord.STATUS_CHOICES]),
    OpenApiParameter('date', str), OpenApiParameter('date_from', str), OpenApiParameter('date_to', str),
])
class AttendanceViewSet(ModelViewSet):
    """Teachers can view and mark attendance only for courses they teach."""
    queryset = AttendanceRecord.objects.all()
    permission_classes = [IsAdminOrTeacher]
    pagination_class = StandardPagination

    def get_queryset(self):
        return _filter(records_visible_to(self.request.user), self.request.query_params) \
            .order_by('-check_in_time')

    def get_serializer_class(self):
        if self.action == 'create':
            return AttendanceCreateSerializer
        if self.action == 'list':
            return AttendanceListSerializer
        return AttendanceRecordSerializer

    def _require_course_access(self, course):
        if not can_access_course(self.request.user, course):
            raise PermissionDenied('You do not have access to this course')

    @extend_schema(responses={201: AttendanceRecordSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._require_course_access(serializer.validated_data['course'])
        record = serializer.save()
        log_user_activity(request.user, 'MARK_ATTENDANCE', 'attendance',
                          f'Marked {record.status} for {record.student.full_name} in {record.course.course_code}',
                          request, resource_id=record.pk)
        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        self._require_course_access(serializer.validated_data.get('course', serializer.instance.course))
        record = serializer.save()
        record.student.calculate_attendance_rate()
        log_user_activity(self.request.user, 'MARK_ATTENDANCE', 'attendance',
                          f'Updated attendance for {record.student.full_name} to {record.status}',
                          self.request, resource_id=record.pk)

    def perform_destroy(self, instance):
        student = instance.student
        log_user_activity(self.request.user, 'DELETE_ATTENDANCE', 'attendance',
                          f'Deleted attendance for {student.full_name} ({instance.course.course_code})',
                          self.request, resource_id=instance.pk)
        instance.delete()
        student.calculate_attendance_rate()


@extend_schema(deprecated=True, responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def get_attendance_records(request):
    """Legacy flat attendance list (kept for older clients)."""
    records = _filter(records_visible_to(request.user), request.query_params)
    return Response([
        {
            'id': r.id,
            'student': {'id': r.student.id, 'name': r.student.full_name,
                        'matric_number': r.student.matric_number},
            'course': {'id': r.course.id, 'code': r.course.course_code, 'name': r.course.course_name},
            'date': r.attendance_date.isoformat(),
            'time_in': r.check_in_time.time().isoformat(),
            'time_out': r.check_out_time.time().isoformat() if r.check_out_time else None,
            'status': r.status,
            'created_at': r.created_at.isoformat(),
        }
        for r in records
    ])
