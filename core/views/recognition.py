"""
Face enrolment and recognition.

Biometric rules: uploaded images are processed in memory and discarded; only
the encrypted 128-d encoding is stored; encodings are never returned.
"""

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .. import face_engine
from ..activity import log_user_activity
from ..models import AttendanceRecord, Course, Department, Level, Specialization, Student
from ..permissions import IsAdminOrTeacher, IsAdminRole, can_access_course
from ..serializers import (
    EnrollFaceRequestSerializer, RecognitionResponseSerializer, RecognizeRequestSerializer,
    RegisterStudentRequestSerializer, StudentSerializer,
)


def _fail(message, http_status, **extra):
    return Response({'status': 'fail', 'message': message, **extra}, status=http_status)


def _enrolment_encoding(image_file, exclude_student_id=None):
    """
    Encode an enrolment photo. Requires exactly one face and rejects faces that
    already match another enrolled student (prevents duplicate identities).
    Returns (encoding, None) or (None, error Response).
    """
    try:
        encodings = face_engine.encode(face_engine.load_image(image_file))
    except face_engine.FaceEngineError as exc:
        return None, _fail(str(exc), status.HTTP_400_BAD_REQUEST, code=exc.code)
    if not encodings:
        return None, _fail('No face detected in image.', status.HTTP_400_BAD_REQUEST, code='no_face')
    if len(encodings) > 1:
        return None, _fail('More than one face detected; enrol with a photo of one person.',
                           status.HTTP_400_BAD_REQUEST, code='multiple_faces')

    others = Student.objects.exclude(face_images_count=0).only('id', 'face_encoding')
    if exclude_student_id:
        others = others.exclude(pk=exclude_student_id)
    duplicate = face_engine.match(encodings[0], face_engine.student_candidates(others))
    if duplicate.matched:
        existing = Student.objects.get(pk=duplicate.student_id)
        return None, _fail(f'This face is already enrolled as {existing.matric_number}.',
                           status.HTTP_409_CONFLICT, code='duplicate_face')
    return encodings[0], None


@extend_schema(request={'multipart/form-data': RegisterStudentRequestSerializer},
               responses={201: inline_serializer('RegisterStudentResponse', {
                   'status': serializers.CharField(),
                   'message': serializers.CharField(),
                   'student_id': serializers.IntegerField(),
                   'enrolled_courses': serializers.IntegerField(),
               })})
@api_view(['POST'])
@permission_classes([IsAdminRole])
@parser_classes([MultiPartParser, FormParser])
def register_student(request):
    """Create a student and enrol their face in one step (legacy flow)."""
    serializer = RegisterStudentRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _fail('Missing or invalid fields.', status.HTTP_400_BAD_REQUEST, errors=serializer.errors)
    data = serializer.validated_data

    department = Department.objects.filter(id=data['department_id'], is_active=True).first()
    specialization = Specialization.objects.filter(
        id=data['specialization_id'], department=department, is_active=True).first()
    level = Level.objects.filter(id=data['level_id'], departments=department, is_active=True).first()
    if not (department and specialization and level):
        return _fail('Invalid academic structure selection.', status.HTTP_400_BAD_REQUEST)

    if Student.objects.filter(Q(matric_number=data['matric_number']) | Q(email=data['email'])).exists():
        return _fail('Student with this matriculation number or email already exists.',
                     status.HTTP_400_BAD_REQUEST)

    encoding, error = _enrolment_encoding(data['image'])
    if error:
        return error

    with transaction.atomic():
        student = Student.objects.create(
            first_name=data['first_name'], last_name=data['last_name'],
            matric_number=data['matric_number'], email=data['email'],
            phone=data.get('phone', ''), address=data.get('address', ''),
            department=department, specialization=specialization, level=level,
            face_encoding=face_engine.to_bytes(encoding),
            face_encoding_model='hog', face_images_count=1,
        )
    log_user_activity(request.user, 'CREATE_STUDENT', 'students',
                      f'Registered new student with face: {student.full_name}', request,
                      resource_id=student.pk)
    return Response({
        'status': 'success',
        'message': 'Student registered successfully!',
        'student_id': student.id,
        'enrolled_courses': student.enrolled_courses.count(),
    }, status=status.HTTP_201_CREATED)


@extend_schema(request={'multipart/form-data': EnrollFaceRequestSerializer}, responses=StudentSerializer)
@api_view(['POST'])
@permission_classes([IsAdminRole])
@parser_classes([MultiPartParser, FormParser])
def enroll_face(request, pk):
    """Set or replace an existing student's face encoding from a photo."""
    student = get_object_or_404(Student, pk=pk)
    image = request.FILES.get('image')
    if not image:
        return _fail('Face image is required.', status.HTTP_400_BAD_REQUEST)
    encoding, error = _enrolment_encoding(image, exclude_student_id=student.pk)
    if error:
        return error
    student.face_encoding = face_engine.to_bytes(encoding)
    student.face_encoding_model = 'hog'
    student.face_images_count = 1
    student.save(update_fields=['face_encoding', 'face_encoding_model', 'face_images_count', 'updated_at'])
    log_user_activity(request.user, 'UPDATE_STUDENT', 'students',
                      f'Enrolled face for {student.full_name}', request, resource_id=student.pk)
    return Response(StudentSerializer(student).data)


@extend_schema(request={'multipart/form-data': RecognizeRequestSerializer},
               responses=RecognitionResponseSerializer)
@api_view(['POST'])
@permission_classes([IsAdminOrTeacher])
@parser_classes([MultiPartParser, FormParser])
def recognize_face(request):
    """Recognise a face among a course's enrolled students and mark them present today."""
    image_file = request.FILES.get('image')
    course_id = request.data.get('course_id')
    if not image_file:
        return _fail('No image provided.', status.HTTP_400_BAD_REQUEST)
    if not course_id:
        return _fail('Course ID is required.', status.HTTP_400_BAD_REQUEST)

    course = Course.objects.filter(id=course_id, status='active').first()
    if not course:
        return _fail('Invalid course.', status.HTTP_400_BAD_REQUEST)
    if not can_access_course(request.user, course):
        return _fail('Access denied to this course.', status.HTTP_403_FORBIDDEN)

    try:
        probe = face_engine.encode_single(image_file)
    except face_engine.FaceEngineError as exc:
        return _fail(str(exc), status.HTTP_400_BAD_REQUEST, code=exc.code)

    enrolled = course.enrolled_students.filter(status='active').only('id', 'face_encoding')
    result = face_engine.match(probe, face_engine.student_candidates(enrolled))
    scores = {'confidence': result.confidence, 'distance': result.distance, 'threshold': result.threshold}

    if not result.matched:
        log_user_activity(request.user, 'USE_FACE_RECOGNITION', 'attendance',
                          f'Face not recognised for {course.course_code}', request, status='failed')
        return Response({'status': 'fail',
                         'message': 'Face not recognized or student not enrolled in this course.',
                         **scores})

    student = Student.objects.select_related('department').get(pk=result.student_id)
    student_info = {
        'id': student.id,
        'name': student.full_name,
        'matric_number': student.matric_number,
        'department': student.department.department_name,
        'course': course.course_code,
        'confidence': result.confidence,
    }

    existing = AttendanceRecord.objects.filter(
        student=student, course=course, attendance_date=timezone.localdate()).first()
    if existing:
        return Response({
            'status': 'info',
            'message': f'{student.full_name} already marked {existing.status} today for {course.course_code}.',
            **scores,
            'student': {**student_info, 'existing_status': existing.status},
        })

    AttendanceRecord.objects.create(
        student=student, course=course, status='present',
        recognition_confidence=result.confidence, recognition_model='hog')
    student.refresh_from_db(fields=['attendance_rate'])
    log_user_activity(request.user, 'USE_FACE_RECOGNITION', 'attendance',
                      f'Recognised {student.full_name} in {course.course_code}', request,
                      resource_id=student.pk)
    return Response({
        'status': 'success',
        'message': f'Welcome {student.full_name}! Attendance marked for {course.course_code}.',
        **scores,
        'student': {**student_info, 'attendance_rate': float(student.attendance_rate)},
    })
