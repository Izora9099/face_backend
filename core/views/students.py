"""Students and course enrolment."""

from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..activity import log_user_activity
from ..models import Course, Student
from ..permissions import IsAdminOrReadOnly, IsAdminRole, is_teacher
from ..serializers import (
    BulkEnrollmentSerializer, CourseListSerializer, IdListSerializer,
    MessageSerializer, StudentEnrollmentSerializer, StudentListSerializer,
    StudentSerializer,
)


class StandardPagination(PageNumberPagination):
    """`?page=` and `?page_size=` (max 500); responds with {count, next, previous, results}."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


def students_visible_to(user):
    qs = Student.objects.select_related('department', 'specialization', 'level') \
        .prefetch_related('enrolled_courses')
    if is_teacher(user):
        qs = qs.filter(enrolled_courses__teachers=user).distinct()
    return qs


@extend_schema(parameters=[
    OpenApiParameter('department', int), OpenApiParameter('specialization', int),
    OpenApiParameter('level', int), OpenApiParameter('course', int),
    OpenApiParameter('status', str), OpenApiParameter('search', str),
    OpenApiParameter('active_only', bool),
])
class StudentViewSet(ModelViewSet):
    """Teachers get read-only access to students enrolled in their courses."""
    queryset = Student.objects.all()
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = students_visible_to(self.request.user)
        p = self.request.query_params
        for param, field in (('department', 'department_id'), ('specialization', 'specialization_id'),
                             ('level', 'level_id'), ('course', 'enrolled_courses'), ('status', 'status')):
            if p.get(param):
                qs = qs.filter(**{field: p[param]})
        if str(p.get('active_only')).lower() == 'true':
            qs = qs.filter(status='active')
        if p.get('search'):
            term = p['search']
            qs = qs.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term)
                           | Q(matric_number__icontains=term) | Q(email__icontains=term))
        return qs.order_by('first_name', 'last_name', 'id')

    def get_serializer_class(self):
        return StudentListSerializer if self.action == 'list' else StudentSerializer

    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(self.request.user, 'CREATE_STUDENT', 'students',
                          f'Created student: {serializer.instance.full_name}', self.request,
                          resource_id=serializer.instance.pk)

    def perform_update(self, serializer):
        serializer.save()
        log_user_activity(self.request.user, 'UPDATE_STUDENT', 'students',
                          f'Updated student: {serializer.instance.full_name}', self.request,
                          resource_id=serializer.instance.pk)

    def perform_destroy(self, instance):
        log_user_activity(self.request.user, 'UPDATE_STUDENT', 'students',
                          f'Deleted student: {instance.full_name}', self.request, resource_id=instance.pk)
        instance.delete()

    @extend_schema(responses=CourseListSerializer(many=True))
    @action(detail=True, methods=['get'])
    def courses(self, request, pk=None):
        student = self.get_object()
        courses = student.enrolled_courses.select_related('department', 'level')
        if is_teacher(request.user):
            courses = courses.filter(teachers=request.user)
        return Response(CourseListSerializer(courses, many=True).data)

    @extend_schema(request=IdListSerializer, responses=MessageSerializer)
    @action(detail=True, methods=['post'], url_path='enroll-courses', permission_classes=[IsAdminRole])
    def enroll_courses(self, request, pk=None):
        student = self.get_object()
        courses = Course.objects.filter(id__in=request.data.get('course_ids', []), status='active')
        student.enrolled_courses.set(courses)
        log_user_activity(request.user, 'UPDATE_STUDENT', 'students',
                          f'Updated course enrolment for {student.full_name}', request, resource_id=student.pk)
        return Response({'message': 'Updated course enrollment successfully'})

    @extend_schema(request=None, responses=MessageSerializer)
    @action(detail=True, methods=['post'], url_path='auto-assign-courses', permission_classes=[IsAdminRole])
    def auto_assign_courses(self, request, pk=None):
        student = self.get_object()
        student.auto_assign_courses()
        log_user_activity(request.user, 'UPDATE_STUDENT', 'students',
                          f'Auto-assigned courses for {student.full_name}', request, resource_id=student.pk)
        return Response({'message': 'Courses auto-assigned successfully'})

    @action(detail=True, methods=['get'], url_path='attendance-summary')
    def attendance_summary(self, request, pk=None):
        student = self.get_object()
        records = student.attendance_records.all()
        courses = student.enrolled_courses.all()
        if is_teacher(request.user):
            courses = courses.filter(teachers=request.user)
            records = records.filter(course__in=courses)

        def counts(qs):
            total = qs.count()
            attended = qs.filter(status__in=['present', 'late']).count()
            return total, attended

        course_stats = []
        for course in courses:
            total, attended = counts(records.filter(course=course))
            course_stats.append({
                'course_id': course.id,
                'course_code': course.course_code,
                'course_name': course.course_name,
                'total_records': total,
                'present_count': attended,
                'attendance_rate': round(attended / total * 100, 2) if total else 0.0,
            })

        return Response({
            'total': records.count(),
            'present': records.filter(status='present').count(),
            'late': records.filter(status='late').count(),
            'absent': records.filter(status='absent').count(),
            'excused': records.filter(status='excused').count(),
            'overall_attendance_rate': float(student.attendance_rate),
            'course_statistics': course_stats,
        })


# --------------------------
# Legacy list + enrolment endpoints
# --------------------------
@extend_schema(deprecated=True, responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def get_students(request):
    """Legacy flat list of active students (kept for older clients)."""
    students = students_visible_to(request.user).filter(status='active')
    return Response([
        {
            'id': s.id,
            'name': s.full_name,
            'matric_number': s.matric_number,
            'email': s.email,
            'department': s.department.department_name,
            'specialization': s.specialization.specialization_name if s.specialization else None,
            'level': s.level.level_name,
            'student_class': f'{s.department.department_code}-{s.level.level_name}',
            'attendance_rate': float(s.attendance_rate),
            'created_at': s.created_at.isoformat(),
        }
        for s in students
    ])


@extend_schema(request=StudentEnrollmentSerializer, responses=MessageSerializer)
@api_view(['POST'])
@permission_classes([IsAdminRole])
def manage_student_enrollment(request):
    serializer = StudentEnrollmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    student = Student.objects.get(id=serializer.validated_data['student_id'])
    courses = Course.objects.filter(id__in=serializer.validated_data['course_ids'], status='active')
    student.enrolled_courses.set(courses)
    log_user_activity(request.user, 'UPDATE_STUDENT', 'students',
                      f'Updated course enrolment for {student.full_name}', request, resource_id=student.pk)
    return Response({'message': f'Updated enrollment for {student.full_name}',
                     'enrolled_courses': courses.count()})


@extend_schema(request=BulkEnrollmentSerializer, responses=inline_serializer('BulkEnrollmentResponse', {
    'message': serializers.CharField(),
    'students_enrolled': serializers.IntegerField(),
    'courses_count': serializers.IntegerField(),
}))
@api_view(['POST'])
@permission_classes([IsAdminRole])
def bulk_enrollment(request):
    serializer = BulkEnrollmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    courses = list(Course.objects.filter(id__in=data['course_ids'], status='active'))

    student_filter = Q(status='active')
    for key, field in (('department_id', 'department_id'), ('specialization_id', 'specialization_id'),
                       ('level_id', 'level_id')):
        if data.get(key):
            student_filter &= Q(**{field: data[key]})
    students = list(Student.objects.filter(student_filter))

    through = Student.enrolled_courses.through
    through.objects.bulk_create(
        [through(student_id=s.id, course_id=c.id) for s in students for c in courses],
        ignore_conflicts=True,
    )
    log_user_activity(request.user, 'MANAGE_COURSES', 'courses',
                      f'Bulk enrolled {len(students)} students in {len(courses)} courses', request)
    return Response({'message': 'Bulk enrollment completed',
                     'students_enrolled': len(students), 'courses_count': len(courses)},
                    status=status.HTTP_200_OK)
