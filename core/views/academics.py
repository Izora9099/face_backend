"""Departments, specializations, levels and courses."""

from django.db.models import Avg
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..activity import log_user_activity
from ..models import Course, Department, Level, Specialization, Student
from ..permissions import IsAdminOrReadOnly, IsAdminRole, can_access_course, is_teacher
from ..serializers import (
    AttendanceListSerializer, CourseSerializer, DepartmentSerializer,
    IdListSerializer, LevelSerializer, MessageSerializer, SpecializationSerializer,
    StudentListSerializer,
)


def _truthy(value):
    return str(value).lower() in ('1', 'true', 'yes')


class _AuditedViewSet(ModelViewSet):
    """ModelViewSet that records create/update/delete in the audit trail."""
    permission_classes = [IsAdminOrReadOnly]
    audit_action = ''
    audit_resource = ''

    def _label(self, obj):
        return str(obj)

    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(self.request.user, self.audit_action, self.audit_resource,
                          f'Created {self._label(serializer.instance)}', self.request,
                          resource_id=serializer.instance.pk)

    def perform_update(self, serializer):
        serializer.save()
        log_user_activity(self.request.user, self.audit_action, self.audit_resource,
                          f'Updated {self._label(serializer.instance)}', self.request,
                          resource_id=serializer.instance.pk)

    def perform_destroy(self, instance):
        log_user_activity(self.request.user, self.audit_action, self.audit_resource,
                          f'Deleted {self._label(instance)}', self.request, resource_id=instance.pk)
        instance.delete()


class DepartmentViewSet(_AuditedViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    audit_action, audit_resource = 'MANAGE_DEPARTMENTS', 'departments'

    def get_queryset(self):
        qs = Department.objects.all()
        if _truthy(self.request.query_params.get('active_only')):
            qs = qs.filter(is_active=True)
        return qs.order_by('department_name')

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        department = self.get_object()
        return Response({
            'total_specializations': department.specializations.count(),
            'total_courses': department.courses.count(),
            'total_students': department.students.count(),
            'average_attendance_rate': float(
                department.students.aggregate(v=Avg('attendance_rate'))['v'] or 0),
            'active_courses': department.courses.filter(status='active').count(),
        })


class SpecializationViewSet(_AuditedViewSet):
    queryset = Specialization.objects.select_related('department')
    serializer_class = SpecializationSerializer
    audit_action, audit_resource = 'MANAGE_SPECIALIZATIONS', 'specializations'

    def get_queryset(self):
        qs = Specialization.objects.select_related('department')
        department_id = self.request.query_params.get('department')
        if department_id:
            qs = qs.filter(department_id=department_id)
        if _truthy(self.request.query_params.get('active_only')):
            qs = qs.filter(is_active=True)
        return qs.order_by('specialization_name')


class LevelViewSet(_AuditedViewSet):
    queryset = Level.objects.prefetch_related('departments', 'specializations')
    serializer_class = LevelSerializer
    audit_action, audit_resource = 'MANAGE_LEVELS', 'levels'

    def get_queryset(self):
        qs = Level.objects.prefetch_related('departments', 'specializations')
        if _truthy(self.request.query_params.get('active_only')):
            qs = qs.filter(is_active=True)
        return qs.order_by('level_order', 'level_name')


class CourseViewSet(_AuditedViewSet):
    """Teachers only ever see the courses they teach."""
    queryset = Course.objects.select_related('department', 'level') \
        .prefetch_related('specializations', 'teachers', 'enrolled_students')
    serializer_class = CourseSerializer
    audit_action, audit_resource = 'MANAGE_COURSES', 'courses'

    def get_queryset(self):
        qs = super().get_queryset()
        if is_teacher(self.request.user):
            qs = qs.filter(teachers=self.request.user)
        params = self.request.query_params
        if params.get('department'):
            qs = qs.filter(department_id=params['department'])
        if params.get('specialization'):
            qs = qs.filter(specializations=params['specialization'])
        if params.get('level'):
            qs = qs.filter(level_id=params['level'])
        if params.get('search'):
            from django.db.models import Q
            term = params['search']
            qs = qs.filter(Q(course_code__icontains=term) | Q(course_name__icontains=term))
        if _truthy(params.get('active_only')):
            qs = qs.filter(status='active')
        return qs.order_by('course_code').distinct()

    @extend_schema(responses=StudentListSerializer(many=True))
    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        course = self.get_object()
        students = course.enrolled_students.select_related('department', 'specialization', 'level') \
            .prefetch_related('enrolled_courses')
        return Response(StudentListSerializer(students, many=True).data)

    @extend_schema(responses=AttendanceListSerializer(many=True))
    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        course = self.get_object()
        records = course.attendance_records.select_related('student', 'course')
        if request.query_params.get('start_date'):
            records = records.filter(attendance_date__gte=request.query_params['start_date'])
        if request.query_params.get('end_date'):
            records = records.filter(attendance_date__lte=request.query_params['end_date'])
        return Response(AttendanceListSerializer(records, many=True).data)

    @extend_schema(request=IdListSerializer, responses=MessageSerializer)
    @action(detail=True, methods=['post'], url_path='enroll-students',
            permission_classes=[IsAdminRole])
    def enroll_students(self, request, pk=None):
        course = self.get_object()
        students = Student.objects.filter(id__in=request.data.get('student_ids', []))
        course.enrolled_students.add(*students)
        count = students.count()
        log_user_activity(request.user, 'MANAGE_COURSES', 'courses',
                          f'Enrolled {count} students in {course.course_code}', request,
                          resource_id=course.pk)
        return Response({'message': f'Enrolled {count} students successfully', 'enrolled': count},
                        status=status.HTTP_200_OK)

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if not can_access_course(request.user, obj):
            self.permission_denied(request, message='You do not have access to this course')
