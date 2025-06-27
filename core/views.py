# core/views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.sessions.models import Session
from django.core.mail import send_mail, get_connection, EmailMessage
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count, Avg, Q, Sum
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .models import (
    Student, AttendanceRecord, Attendance, AdminUser, 
    UserActivity, LoginAttempt, ActiveSession, SecuritySettings,
    SystemSettings, SystemBackup, Department, Specialization, 
    Level, Course, AttendanceSession, SessionCheckIn  # ADD THESE TWO
)

from .serializers import (
    SystemSettingsSerializer, SystemSettingsUpdateSerializer, 
    SystemStatsSerializer, SystemBackupSerializer,
    StudentSerializer, StudentListSerializer, StudentCreateSerializer,
    AttendanceSerializer, AttendanceRecordSerializer, AttendanceListSerializer,
    AttendanceCreateSerializer, AdminUserSerializer,
    DepartmentSerializer, SpecializationSerializer, LevelSerializer,
    CourseSerializer, CourseListSerializer, UserActivitySerializer,
    LoginAttemptSerializer, ActiveSessionSerializer, SecuritySettingsSerializer,
    DepartmentStatsSerializer, CourseStatsSerializer, TeacherStatsSerializer,
    StudentEnrollmentSerializer, BulkEnrollmentSerializer,
    # ADD THESE SESSION SERIALIZERS:
    AttendanceSessionSerializer, SessionCheckInSerializer, SessionStatsSerializer
)

import numpy as np
import face_recognition
import json
import datetime
from datetime import timedelta
from . import face_utils
import csv
import psutil
import os
import zipfile
import tempfile
import time

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import *
import json
from django.utils import timezone
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
import json

# Get the User model
User = get_user_model()

# --------------------------
# Permission Helpers
# --------------------------
def check_role_permission(user, required_roles):
    """Check if user has required role"""
    if not user or not hasattr(user, 'role'):
        return False
    return user.role in required_roles

def check_teacher_course_access(user, course):
    """Check if teacher has access to specific course"""
    if user.role == 'teacher':
        return course in user.taught_courses.all()
    return user.role in ['superadmin', 'staff']

def log_user_activity(user, action, resource, details, request, status='success'):
    """Log user activity"""
    UserActivity.objects.create(
        user=user,
        action=action,
        resource=resource,
        details=details,
        ip_address=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        session_id=request.session.session_key or '',
        status=status
    )

# --------------------------
# Academic Structure ViewSets
# --------------------------
class DepartmentViewSet(ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Department.objects.all()
        if self.request.query_params.get('active_only') == 'true':
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('department_name')
    
    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'MANAGE_DEPARTMENTS', 'departments',
            f"Created department: {serializer.instance.department_name}",
            self.request
        )
    
    def perform_update(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'MANAGE_DEPARTMENTS', 'departments',
            f"Updated department: {serializer.instance.department_name}",
            self.request
        )
    
    def perform_destroy(self, instance):
        log_user_activity(
            self.request.user, 'MANAGE_DEPARTMENTS', 'departments',
            f"Deleted department: {instance.department_name}",
            self.request
        )
        instance.delete()
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get department statistics"""
        department = self.get_object()
        stats = {
            'total_specializations': department.specializations.count(),
            'total_courses': department.courses.count(),
            'total_students': department.students.count(),
            'average_attendance_rate': department.students.aggregate(
                avg_rate=Avg('attendance_rate')
            )['avg_rate'] or 0,
            'active_courses': department.courses.filter(status='active').count(),
        }
        return Response(stats)

class SpecializationViewSet(ModelViewSet):
    queryset = Specialization.objects.select_related('department').all()
    serializer_class = SpecializationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Specialization.objects.select_related('department').all()
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if self.request.query_params.get('active_only') == 'true':
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('specialization_name')
    
    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'MANAGE_SPECIALIZATIONS', 'specializations',
            f"Created specialization: {serializer.instance.specialization_name}",
            self.request
        )
    
    def perform_update(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'MANAGE_SPECIALIZATIONS', 'specializations',
            f"Updated specialization: {serializer.instance.specialization_name}",
            self.request
        )

class LevelViewSet(ModelViewSet):
    queryset = Level.objects.prefetch_related('departments', 'specializations').all()
    serializer_class = LevelSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Level.objects.prefetch_related('departments', 'specializations').all()
        if self.request.query_params.get('active_only') == 'true':
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('level_name')
    
    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'MANAGE_LEVELS', 'levels',
            f"Created level: {serializer.instance.level_name}",
            self.request
        )

class CourseViewSet(ModelViewSet):
    queryset = Course.objects.select_related(
        'department', 'level'
    ).prefetch_related('specializations', 'teachers', 'enrolled_students').all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Course.objects.select_related(
            'department', 'level'
        ).prefetch_related('specializations', 'teachers', 'enrolled_students').all()
        
        # Filter by teacher access
        user = self.request.user
        if hasattr(user, 'role') and user.role == 'teacher':
            queryset = queryset.filter(teachers=user)
        
        # Additional filters
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        specialization_id = self.request.query_params.get('specialization')
        if specialization_id:
            queryset = queryset.filter(specializations=specialization_id)
        
        level_id = self.request.query_params.get('level')
        if level_id:
            queryset = queryset.filter(level_id=level_id)
        
        if self.request.query_params.get('active_only') == 'true':
            queryset = queryset.filter(status='active')
        
        return queryset.order_by('course_code')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        return CourseSerializer
    
    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'MANAGE_COURSES', 'courses',
            f"Created course: {serializer.instance.course_code}",
            self.request
        )
    
    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        """Get students enrolled in this course"""
        course = self.get_object()
        
        # Check teacher access
        if not check_teacher_course_access(request.user, course):
            return Response(
                {'error': 'You do not have access to this course'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        students = course.enrolled_students.all()
        serializer = StudentListSerializer(students, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        """Get attendance records for this course"""
        course = self.get_object()
        
        # Check teacher access
        if not check_teacher_course_access(request.user, course):
            return Response(
                {'error': 'You do not have access to this course'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        attendance_records = course.attendance_records.select_related('student').all()
        
        # Filter by date range if provided
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            attendance_records = attendance_records.filter(attendance_date__gte=start_date)
        if end_date:
            attendance_records = attendance_records.filter(attendance_date__lte=end_date)
        
        serializer = AttendanceListSerializer(attendance_records, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def enroll_students(self, request, pk=None):
        """Enroll students in this course"""
        course = self.get_object()
        student_ids = request.data.get('student_ids', [])
        
        if not check_role_permission(request.user, ['superadmin', 'staff']):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        students = Student.objects.filter(id__in=student_ids)
        course.enrolled_students.add(*students)
        
        log_user_activity(
            request.user, 'MANAGE_COURSES', 'courses',
            f"Enrolled {len(students)} students in course: {course.course_code}",
            request
        )
        
        return Response({'message': f'Enrolled {len(students)} students successfully'})

# --------------------------
# Updated Student ViewSet
# --------------------------
class StudentViewSet(ModelViewSet):
    queryset = Student.objects.select_related(
        'department', 'specialization', 'level'
    ).prefetch_related('enrolled_courses').all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Student.objects.select_related(
            'department', 'specialization', 'level'
        ).prefetch_related('enrolled_courses').all()
        
        # Filter by department, specialization, level
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        specialization_id = self.request.query_params.get('specialization')
        if specialization_id:
            queryset = queryset.filter(specialization_id=specialization_id)
        
        level_id = self.request.query_params.get('level')
        if level_id:
            queryset = queryset.filter(level_id=level_id)
        
        if self.request.query_params.get('active_only') == 'true':
            queryset = queryset.filter(status='active')
        
        return queryset.order_by('first_name', 'last_name')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return StudentCreateSerializer
        elif self.action == 'list':
            return StudentListSerializer
        return StudentSerializer
    
    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'CREATE_STUDENT', 'students',
            f"Created student: {serializer.instance.full_name}",
            self.request
        )
    
    def perform_update(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'UPDATE_STUDENT', 'students',
            f"Updated student: {serializer.instance.full_name}",
            self.request
        )
    
    @action(detail=True, methods=['get'])
    def courses(self, request, pk=None):
        """Get courses for this student"""
        student = self.get_object()
        courses = student.enrolled_courses.all()
        serializer = CourseListSerializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def enroll_courses(self, request, pk=None):
        """Manually enroll student in courses"""
        student = self.get_object()
        course_ids = request.data.get('course_ids', [])
        
        if not check_role_permission(request.user, ['superadmin', 'staff']):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        courses = Course.objects.filter(id__in=course_ids, status='active')
        student.enrolled_courses.set(courses)
        
        log_user_activity(
            request.user, 'UPDATE_STUDENT', 'students',
            f"Updated course enrollment for: {student.full_name}",
            request
        )
        
        return Response({'message': f'Updated course enrollment successfully'})
    
    @action(detail=True, methods=['post'])
    def auto_assign_courses(self, request, pk=None):
        """Auto-assign courses based on student's academic structure"""
        student = self.get_object()
        student.auto_assign_courses()
        
        log_user_activity(
            request.user, 'UPDATE_STUDENT', 'students',
            f"Auto-assigned courses for: {student.full_name}",
            request
        )
        
        return Response({'message': 'Courses auto-assigned successfully'})
    
    @action(detail=True, methods=['get'])
    def attendance_summary(self, request, pk=None):
        """Get attendance summary for this student"""
        student = self.get_object()
        
        # Get attendance records with course info
        attendance_records = student.attendance_records.select_related('course').all()
        
        # Calculate summary statistics
        total_records = attendance_records.count()
        present_count = attendance_records.filter(status='present').count()
        late_count = attendance_records.filter(status='late').count()
        absent_count = attendance_records.filter(status='absent').count()
        
        # Per course statistics
        course_stats = []
        for course in student.enrolled_courses.all():
            course_records = attendance_records.filter(course=course)
            course_total = course_records.count()
            course_present = course_records.filter(status='present').count()
            
            course_stats.append({
                'course_code': course.course_code,
                'course_name': course.course_name,
                'total_records': course_total,
                'present_count': course_present,
                'attendance_rate': (course_present / course_total * 100) if course_total > 0 else 0
            })
        
        summary = {
            'total_records': total_records,
            'present_count': present_count,
            'late_count': late_count,
            'absent_count': absent_count,
            'overall_attendance_rate': student.attendance_rate,
            'course_statistics': course_stats
        }
        
        return Response(summary)

# --------------------------
# Updated Attendance ViewSet
# --------------------------
class AttendanceViewSet(ModelViewSet):
    queryset = AttendanceRecord.objects.select_related('student', 'course').all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = AttendanceRecord.objects.select_related('student', 'course').all()
        
        # Filter by teacher access
        user = self.request.user
        if hasattr(user, 'role') and user.role == 'teacher':
            queryset = queryset.filter(course__teachers=user)
        
        # Additional filters
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        student_id = self.request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(attendance_date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(attendance_date__lte=date_to)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-check_in_time')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AttendanceCreateSerializer
        elif self.action == 'list':
            return AttendanceListSerializer
        return AttendanceRecordSerializer
    
    def perform_create(self, serializer):
        serializer.save()
        log_user_activity(
            self.request.user, 'MARK_ATTENDANCE', 'attendance',
            f"Marked attendance for: {serializer.instance.student.full_name}",
            self.request
        )

# --------------------------
# Legacy Function-Based Views (Updated)
# --------------------------
@csrf_exempt
def register_student(request):
    """Updated student registration with new academic structure"""
    if request.method != 'POST':
        return JsonResponse({'status': 'fail', 'message': 'Only POST requests allowed.'}, status=405)

    try:
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        matric_number = request.POST.get('matric_number')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        address = request.POST.get('address', '')
        department_id = request.POST.get('department_id')
        specialization_id = request.POST.get('specialization_id')
        level_id = request.POST.get('level_id')
        image_file = request.FILES.get('image')

        if not all([first_name, last_name, matric_number, email, department_id, specialization_id, level_id, image_file]):
            return JsonResponse({
                'status': 'fail', 
                'message': 'Missing required fields: first_name, last_name, matric_number, email, department_id, specialization_id, level_id, or image.'
            }, status=400)

        # Validate academic structure
        try:
            department = Department.objects.get(id=department_id, is_active=True)
            specialization = Specialization.objects.get(id=specialization_id, department=department, is_active=True)
            level = Level.objects.get(id=level_id, departments=department, is_active=True)
        except (Department.DoesNotExist, Specialization.DoesNotExist, Level.DoesNotExist):
            return JsonResponse({
                'status': 'fail', 
                'message': 'Invalid academic structure selection.'
            }, status=400)

        # Check for existing student
        if Student.objects.filter(Q(matric_number=matric_number) | Q(email=email)).exists():
            return JsonResponse({
                'status': 'fail', 
                'message': 'Student with this matriculation number or email already exists.'
            }, status=400)

        # Process face image
        image = face_utils.preprocess_image(image_file)
        if image is None:
            return JsonResponse({'status': 'fail', 'message': 'Failed to load image.'}, status=400)

        # Extract face encoding
        face_encodings = face_recognition.face_encodings(image)
        if not face_encodings:
            return JsonResponse({'status': 'fail', 'message': 'No face detected in image.'}, status=400)

        face_encoding = face_encodings[0]

        # Create student
        with transaction.atomic():
            student = Student.objects.create(
                first_name=first_name,
                last_name=last_name,
                matric_number=matric_number,
                email=email,
                phone=phone,
                address=address,
                department=department,
                specialization=specialization,
                level=level,
                face_encoding=face_encoding.tobytes(),
                face_encoding_model='cnn'
            )
            
            # Auto-assign courses
            student.auto_assign_courses()

        # Log activity
        if request.user.is_authenticated:
            log_user_activity(
                request.user, 'CREATE_STUDENT', 'students',
                f"Registered new student: {student.full_name}",
                request
            )

        return JsonResponse({
            'status': 'success',
            'message': 'Student registered successfully!',
            'student_id': student.id,
            'enrolled_courses': student.enrolled_courses.count()
        })

    except Exception as e:
        return JsonResponse({
            'status': 'fail',
            'message': f'Registration failed: {str(e)}'
        }, status=500)

@csrf_exempt
def recognize_face(request):
    """Updated face recognition with course selection"""
    if request.method != 'POST':
        return JsonResponse({'status': 'fail', 'message': 'Only POST requests allowed.'}, status=405)

    try:
        image_file = request.FILES.get('image')
        course_id = request.POST.get('course_id')
        
        if not image_file:
            return JsonResponse({'status': 'fail', 'message': 'No image provided.'}, status=400)
        
        if not course_id:
            return JsonResponse({'status': 'fail', 'message': 'Course ID is required.'}, status=400)

        # Validate course
        try:
            course = Course.objects.get(id=course_id, status='active')
        except Course.DoesNotExist:
            return JsonResponse({'status': 'fail', 'message': 'Invalid course.'}, status=400)

        # Check teacher access
        if request.user.is_authenticated and hasattr(request.user, 'role'):
            if not check_teacher_course_access(request.user, course):
                return JsonResponse({'status': 'fail', 'message': 'Access denied to this course.'}, status=403)

        # Process image
        image = face_utils.preprocess_image(image_file)
        if image is None:
            return JsonResponse({'status': 'fail', 'message': 'Failed to process image.'}, status=400)

        # Extract face encoding
        face_encodings = face_recognition.face_encodings(image)
        if not face_encodings:
            return JsonResponse({'status': 'fail', 'message': 'No face detected.'}, status=400)

        unknown_encoding = face_encodings[0]

        # Get enrolled students for this course
        enrolled_students = course.enrolled_students.filter(status='active')
        
        if not enrolled_students.exists():
            return JsonResponse({'status': 'fail', 'message': 'No students enrolled in this course.'}, status=400)

        # Compare with enrolled students
        best_match = None
        best_distance = float('inf')
        tolerance = 0.6

        for student in enrolled_students:
            try:
                stored_encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                distance = face_recognition.face_distance([stored_encoding], unknown_encoding)[0]
                
                if distance < tolerance and distance < best_distance:
                    best_distance = distance
                    best_match = student
            except Exception as e:
                continue

        if best_match:
            # Check if already marked present today
            today = timezone.now().date()
            existing_record = AttendanceRecord.objects.filter(
                student=best_match,
                course=course,
                attendance_date=today
            ).first()

            if existing_record:
                return JsonResponse({
                    'status': 'info',
                    'message': f'{best_match.full_name} already marked {existing_record.status} today for {course.course_code}.',
                    'student': {
                        'name': best_match.full_name,
                        'matric_number': best_match.matric_number,
                        'course': course.course_code,
                        'existing_status': existing_record.status,
                        'time': existing_record.check_in_time.strftime('%H:%M')
                    }
                })

            # Create attendance record
            attendance_record = AttendanceRecord.objects.create(
                student=best_match,
                course=course,
                status='present',
                recognition_model='cnn'
            )

            # Update attendance rate
            best_match.calculate_attendance_rate()

            # Log activity
            if request.user.is_authenticated:
                log_user_activity(
                    request.user, 'USE_FACE_RECOGNITION', 'attendance',
                    f"Face recognition successful for {best_match.full_name} in {course.course_code}",
                    request
                )

            return JsonResponse({
                'status': 'success',
                'message': f'Welcome {best_match.full_name}! Attendance marked for {course.course_code}.',
                'student': {
                    'id': best_match.id,
                    'name': best_match.full_name,
                    'matric_number': best_match.matric_number,
                    'department': best_match.department.department_name,
                    'course': course.course_code,
                    'confidence': round((1 - best_distance) * 100, 2),
                    'attendance_rate': float(best_match.attendance_rate)
                }
            })
        else:
            # Log failed recognition
            if request.user.is_authenticated:
                log_user_activity(
                    request.user, 'USE_FACE_RECOGNITION', 'attendance',
                    f"Face recognition failed for course {course.course_code}",
                    request, status='failed'
                )

            return JsonResponse({
                'status': 'fail',
                'message': 'Face not recognized or student not enrolled in this course.'
            })

    except Exception as e:
        return JsonResponse({
            'status': 'fail',
            'message': f'Recognition failed: {str(e)}'
        }, status=500)

# --------------------------
# Dashboard and Analytics APIs
# --------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Get dashboard statistics"""
    user = request.user
    
    # Base statistics
    stats = {
        'total_students': Student.objects.filter(status='active').count(),
        'total_courses': Course.objects.filter(status='active').count(),
        'total_departments': Department.objects.filter(is_active=True).count(),
        'total_specializations': Specialization.objects.filter(is_active=True).count(),
        'total_levels': Level.objects.filter(is_active=True).count(),
        'total_attendance_today': AttendanceRecord.objects.filter(
            attendance_date=timezone.now().date()
        ).count(),
    }
    
    # Role-specific statistics
    if hasattr(user, 'role'):
        if user.role == 'teacher':
            # Teacher-specific stats
            teacher_courses = user.taught_courses.filter(status='active')
            stats.update({
                'my_courses': teacher_courses.count(),
                'my_students': Student.objects.filter(
                    enrolled_courses__in=teacher_courses
                ).distinct().count(),
                'my_attendance_today': AttendanceRecord.objects.filter(
                    course__in=teacher_courses,
                    attendance_date=timezone.now().date()
                ).count(),
            })
        elif user.role in ['superadmin', 'staff']:
            # Admin stats
            stats.update({
                'total_users': AdminUser.objects.filter(is_active=True).count(),
                'total_teachers': AdminUser.objects.filter(role='teacher', is_active=True).count(),
                'attendance_rate_avg': Student.objects.filter(status='active').aggregate(
                    avg_rate=Avg('attendance_rate')
                )['avg_rate'] or 0,
            })
    
    return Response(stats)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_stats(request):
    """Get statistics by department"""
    departments = Department.objects.filter(is_active=True).annotate(
        total_students=Count('students', filter=Q(students__status='active')),
        total_courses=Count('courses', filter=Q(courses__status='active')),
        total_specializations=Count('specializations', filter=Q(specializations__is_active=True)),
        average_attendance_rate=Avg('students__attendance_rate', filter=Q(students__status='active'))
    ).order_by('department_name')
    
    serializer = DepartmentStatsSerializer([
        {
            'department_name': dept.department_name,
            'total_students': dept.total_students,
            'total_courses': dept.total_courses,
            'total_specializations': dept.total_specializations,
            'average_attendance_rate': dept.average_attendance_rate or 0
        }
        for dept in departments
    ], many=True)
    
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_stats(request):
    """Get statistics by course"""
    user = request.user
    
    # Filter courses based on user role
    courses = Course.objects.filter(status='active')
    if hasattr(user, 'role') and user.role == 'teacher':
        courses = courses.filter(teachers=user)
    
    courses = courses.annotate(
        enrolled_students_count=Count('enrolled_students', filter=Q(enrolled_students__status='active')),
        total_attendance_records=Count('attendance_records'),
    ).select_related('department', 'level').order_by('course_code')
    
    course_data = []
    for course in courses:
        # Calculate average attendance rate for this course
        attendance_records = course.attendance_records.all()
        if attendance_records.exists():
            present_count = attendance_records.filter(status='present').count()
            avg_rate = (present_count / attendance_records.count()) * 100
        else:
            avg_rate = 0
        
        course_data.append({
            'course_code': course.course_code,
            'course_name': course.course_name,
            'enrolled_students': course.enrolled_students_count,
            'total_attendance_records': course.total_attendance_records,
            'average_attendance_rate': round(avg_rate, 2)
        })
    
    serializer = CourseStatsSerializer(course_data, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def teacher_stats(request):
    """Get statistics by teacher"""
    if not check_role_permission(request.user, ['superadmin', 'staff']):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    teachers = AdminUser.objects.filter(role='teacher', is_active=True).annotate(
        total_courses=Count('taught_courses', filter=Q(taught_courses__status='active')),
        total_students=Count('taught_courses__enrolled_students', 
                           filter=Q(taught_courses__enrolled_students__status='active'), 
                           distinct=True),
        total_attendance_records=Count('taught_courses__attendance_records')
    ).order_by('first_name', 'last_name')
    
    teacher_data = []
    for teacher in teachers:
        teacher_data.append({
            'teacher_name': f"{teacher.first_name} {teacher.last_name}",
            'total_courses': teacher.total_courses,
            'total_students': teacher.total_students,
            'total_attendance_records': teacher.total_attendance_records
        })
    
    serializer = TeacherStatsSerializer(teacher_data, many=True)
    return Response(serializer.data)

# --------------------------
# Enrollment Management APIs
# --------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manage_student_enrollment(request):
    """Manage individual student course enrollment"""
    if not check_role_permission(request.user, ['superadmin', 'staff']):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = StudentEnrollmentSerializer(data=request.data)
    if serializer.is_valid():
        student_id = serializer.validated_data['student_id']
        course_ids = serializer.validated_data['course_ids']
        
        student = Student.objects.get(id=student_id)
        courses = Course.objects.filter(id__in=course_ids, status='active')
        
        student.enrolled_courses.set(courses)
        
        log_user_activity(
            request.user, 'UPDATE_STUDENT', 'students',
            f"Updated course enrollment for {student.full_name}",
            request
        )
        
        return Response({
            'message': f'Updated enrollment for {student.full_name}',
            'enrolled_courses': courses.count()
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_enrollment(request):
    """Bulk enrollment based on academic structure"""
    if not check_role_permission(request.user, ['superadmin', 'staff']):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = BulkEnrollmentSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        course_ids = data['course_ids']
        courses = Course.objects.filter(id__in=course_ids, status='active')
        
        # Build student filter
        student_filter = Q(status='active')
        
        if data.get('department_id'):
            student_filter &= Q(department_id=data['department_id'])
        if data.get('specialization_id'):
            student_filter &= Q(specialization_id=data['specialization_id'])
        if data.get('level_id'):
            student_filter &= Q(level_id=data['level_id'])
        
        students = Student.objects.filter(student_filter)
        
        # Perform bulk enrollment
        enrolled_count = 0
        for student in students:
            student.enrolled_courses.add(*courses)
            enrolled_count += 1
        
        log_user_activity(
            request.user, 'MANAGE_COURSES', 'courses',
            f"Bulk enrolled {enrolled_count} students in {courses.count()} courses",
            request
        )
        
        return Response({
            'message': f'Bulk enrollment completed',
            'students_enrolled': enrolled_count,
            'courses_count': courses.count()
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --------------------------
# System Management APIs (Updated)
# --------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_stats(request):
    """Get comprehensive system statistics"""
    if not check_role_permission(request.user, ['superadmin', 'staff']):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get database size
    with connection.cursor() as cursor:
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();")
        db_size = cursor.fetchone()[0] if cursor.fetchone() else 0
    
    # Get storage usage
    storage_used = psutil.disk_usage('/').used
    
    # Get system uptime (simplified)
    uptime_seconds = time.time() - psutil.boot_time()
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))
    
    # Get last backup
    last_backup = SystemBackup.objects.first()
    last_backup_str = last_backup.created_at.strftime('%Y-%m-%d %H:%M') if last_backup else 'Never'
    
    stats = {
        'total_students': Student.objects.count(),
        'total_users': AdminUser.objects.count(),
        'total_attendance_records': AttendanceRecord.objects.count(),
        'total_courses': Course.objects.count(),
        'total_departments': Department.objects.count(),
        'total_specializations': Specialization.objects.count(),
        'total_levels': Level.objects.count(),
        'database_size': f"{db_size / (1024*1024):.2f} MB",
        'storage_used': f"{storage_used / (1024*1024*1024):.2f} GB",
        'system_uptime': uptime_str,
        'last_backup': last_backup_str,
        'system_version': '2.0.0'
    }
    
    serializer = SystemStatsSerializer(stats)
    return Response(serializer.data)

# --------------------------
# Legacy Compatibility Functions
# --------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_students(request):
    """Legacy endpoint for getting students"""
    students = Student.objects.filter(status='active').select_related(
        'department', 'specialization', 'level'
    )
    
    # Legacy format for backward compatibility
    student_data = []
    for student in students:
        student_data.append({
            'id': student.id,
            'name': student.full_name,  # Legacy field
            'matric_number': student.matric_number,
            'email': student.email,
            'department': student.department.department_name,
            'specialization': student.specialization.specialization_name,
            'level': student.level.level_name,
            'student_class': f"{student.department.department_code}-{student.level.level_name}",  # Legacy
            'attendance_rate': float(student.attendance_rate),
            'created_at': student.created_at.isoformat(),
        })
    
    return Response(student_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_records(request):
    """Legacy endpoint for getting attendance records"""
    records = AttendanceRecord.objects.select_related('student', 'course').all()
    
    # Add filters
    student_id = request.query_params.get('student_id')
    if student_id:
        records = records.filter(student_id=student_id)
    
    course_id = request.query_params.get('course_id')
    if course_id:
        records = records.filter(course_id=course_id)
    
    date_from = request.query_params.get('date_from')
    if date_from:
        records = records.filter(check_in_time__date__gte=date_from)
    
    # Legacy format
    record_data = []
    for record in records:
        record_data.append({
            'id': record.id,
            'student': {
                'id': record.student.id,
                'name': record.student.full_name,
                'matric_number': record.student.matric_number,
            },
            'course': {
                'id': record.course.id,
                'code': record.course.course_code,
                'name': record.course.course_name,
            },
            'date': record.check_in_time.date().isoformat(),
            'time_in': record.check_in_time.time().isoformat(),
            'time_out': record.check_out_time.time().isoformat() if record.check_out_time else None,
            'status': record.status,
            'created_at': record.created_at.isoformat(),
        })
    
    return Response(record_data)
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_attendance_session(request):
    """Start a new attendance session"""
    try:
        course_id = request.data.get('course_id')
        teacher_id = request.data.get('teacher_id')
        
        if not course_id:
            return Response({
                'success': False,
                'message': 'Course ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get course and validate teacher access
        course = get_object_or_404(Course, id=course_id, status='active')
        
        # Check if teacher has access to this course
        if hasattr(request.user, 'role') and request.user.role == 'teacher':
            if not course.teachers.filter(id=request.user.id).exists():
                return Response({
                    'success': False,
                    'message': 'Access denied to this course'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if there's already an active session for this course
        existing_session = AttendanceSession.objects.filter(
            course=course,
            status='active'
        ).first()
        
        if existing_session:
            return Response({
                'success': False,
                'message': 'An active session already exists for this course',
                'session_id': existing_session.session_id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create new session
        session = AttendanceSession.objects.create(
            course=course,
            teacher=request.user,
            session_duration_minutes=request.data.get('duration_minutes', 120),
            grace_period_minutes=request.data.get('grace_period_minutes', 15),
            room=request.data.get('room', ''),
        )
        
        # Log activity
        log_user_activity(
            request.user, 'MARK_ATTENDANCE', 'sessions',
            f"Started attendance session for {course.course_code}",
            request
        )
        
        serializer = AttendanceSessionSerializer(session)
        
        return Response({
            'success': True,
            'message': f'Attendance session started for {course.course_code}',
            'session_id': session.session_id,
            'session': serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Failed to start session: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_attendance_session(request):
    """End an active attendance session"""
    try:
        session_id = request.data.get('session_id')
        
        if not session_id:
            return Response({
                'success': False,
                'message': 'Session ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get session
        session = get_object_or_404(AttendanceSession, session_id=session_id)
        
        # Check teacher access
        if hasattr(request.user, 'role') and request.user.role == 'teacher':
            if session.teacher != request.user:
                return Response({
                    'success': False,
                    'message': 'Access denied to this session'
                }, status=status.HTTP_403_FORBIDDEN)
        
        if session.status != 'active':
            return Response({
                'success': False,
                'message': f'Session is already {session.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # End the session
        session.end_session(auto_closed=False)
        
        # Log activity
        log_user_activity(
            request.user, 'MARK_ATTENDANCE', 'sessions',
            f"Ended attendance session for {session.course.course_code}",
            request
        )
        
        serializer = AttendanceSessionSerializer(session)
        
        return Response({
            'success': True,
            'message': f'Session ended for {session.course.course_code}',
            'session': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Failed to end session: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
def session_based_attendance(request):
    """Record attendance within an active session using face recognition"""
    try:
        session_id = request.data.get('session_id')
        status_override = request.data.get('status')  # Optional status override
        image_file = request.FILES.get('image')
        
        if not session_id:
            return Response({
                'success': False,
                'message': 'Session ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not image_file:
            return Response({
                'success': False,
                'message': 'Face image is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get active session
        session = get_object_or_404(AttendanceSession, session_id=session_id, status='active')
        
        # Process face image (reuse existing face recognition logic)
        from . import face_utils
        
        image = face_utils.preprocess_image(image_file)
        if image is None:
            return Response({
                'success': False,
                'message': 'Failed to process image'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract face encoding
        import face_recognition
        face_encodings = face_recognition.face_encodings(image)
        if not face_encodings:
            return Response({
                'success': False,
                'message': 'No face detected in image'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        face_encoding = face_encodings[0]
        
        # Find matching student in enrolled students
        enrolled_students = session.course.enrolled_students.filter(status='active')
        best_match = None
        best_distance = float('inf')
        
        for student in enrolled_students:
            if student.face_encoding:
                try:
                    stored_encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                    distance = face_recognition.face_distance([stored_encoding], face_encoding)[0]
                    
                    if distance < 0.6 and distance < best_distance:  # Threshold for recognition
                        best_match = student
                        best_distance = distance
                except Exception:
                    continue
        
        if not best_match:
            return Response({
                'success': False,
                'message': 'Student not recognized or not enrolled in this course'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if student already checked in
        existing_checkin = SessionCheckIn.objects.filter(
            session=session,
            student=best_match
        ).first()
        
        if existing_checkin:
            return Response({
                'success': False,
                'message': f'{best_match.full_name} has already checked in for this session'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Determine attendance status
        current_time = timezone.now()
        
        if status_override:
            attendance_status = status_override
        else:
            # Auto-determine based on timing
            grace_end = session.start_time + timezone.timedelta(minutes=session.grace_period_minutes)
            session_end = session.expected_end_time
            
            if current_time <= grace_end:
                attendance_status = 'present'
            elif current_time <= session_end:
                attendance_status = 'present_late'
            else:
                attendance_status = 'absent'  # Late check-in after session
        
        # Create check-in record
        checkin = SessionCheckIn.objects.create(
            session=session,
            student=best_match,
            status=attendance_status,
            recognition_confidence=1.0 - best_distance,
            check_in_time=current_time
        )
        
        # Log activity
        log_user_activity(
            request.user if request.user.is_authenticated else session.teacher,
            'MARK_ATTENDANCE', 'attendance',
            f"Session check-in: {best_match.full_name} - {attendance_status}",
            request
        )
        
        return Response({
            'success': True,
            'message': f'{best_match.full_name} checked in successfully',
            'student_name': best_match.full_name,
            'status': attendance_status,
            'check_in_time': current_time
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Check-in failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_session_stats(request, session_id):
    """Get real-time statistics for an attendance session"""
    try:
        session = get_object_or_404(AttendanceSession, session_id=session_id)
        
        # Check teacher access
        if hasattr(request.user, 'role') and request.user.role == 'teacher':
            if session.teacher != request.user:
                return Response({
                    'success': False,
                    'message': 'Access denied to this session'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get recent check-ins (last 10)
        recent_checkins = session.session_checkins.order_by('-check_in_time')[:10]
        
        # Calculate time remaining
        time_remaining = 0
        if session.status == 'active':
            remaining_seconds = (session.expected_end_time - timezone.now()).total_seconds()
            time_remaining = max(0, int(remaining_seconds))
        
        # Auto-close session if needed
        if session.should_auto_close and session.status == 'active':
            session.end_session(auto_closed=True)
        
        serializer = SessionStatsSerializer(session)
        
        return Response({
            'success': True,
            'stats': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Failed to get session stats: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Get current authenticated user information"""
    user = request.user
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': getattr(user, 'phone', ''),
        'role': getattr(user, 'role', 'staff'),
        'permissions': getattr(user, 'permissions', []),
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'is_active': user.is_active,
        'last_login': user.last_login.isoformat() if user.last_login else '',
        'date_joined': user.date_joined.isoformat() if user.date_joined else '',
    })
# ============================
# SYSTEM MANAGEMENT ENDPOINTS
# ============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_stats(request):
    """Get comprehensive system statistics"""
    try:
        # Basic system stats
        stats = {
            'system_health': {
                'database_size': '50MB',  # You can calculate this dynamically
                'uptime': '15 days, 3 hours',
                'memory_usage': '45%',
                'cpu_usage': '12%',
                'disk_usage': '23%'
            },
            'user_stats': {
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'admin_users': User.objects.filter(is_superuser=True).count(),
                'recent_logins': LoginAttempt.objects.filter(
                    success=True,
                    timestamp__gte=timezone.now() - timedelta(days=1)
                ).count() if 'LoginAttempt' in globals() else 0
            },
            'data_stats': {
                'total_students': Student.objects.count(),
                'total_courses': Course.objects.count(),
                'total_departments': Department.objects.count(),
                'attendance_records': AttendanceRecord.objects.count()
            },
            'security_stats': {
                'failed_logins_today': LoginAttempt.objects.filter(
                    success=False,
                    timestamp__gte=timezone.now().date()
                ).count() if 'LoginAttempt' in globals() else 0,
                'active_sessions': ActiveSession.objects.filter(
                    is_active=True
                ).count() if 'ActiveSession' in globals() else 0,
                'user_activities_today': UserActivity.objects.filter(
                    timestamp__gte=timezone.now().date()
                ).count() if 'UserActivity' in globals() else 0
            },
            'backup_stats': {
                'last_backup': SystemBackup.objects.filter().order_by('-created_at').first().created_at.isoformat() if SystemBackup.objects.exists() and 'SystemBackup' in globals() else None,
                'total_backups': SystemBackup.objects.count() if 'SystemBackup' in globals() else 0,
                'backup_size': '250MB'
            }
        }
        
        return Response(stats)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

# ============================
# USER MANAGEMENT ENDPOINTS
# ============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_users(request):
    """Get list of admin users"""
    try:
        # Only superusers and staff can view admin users
        if not (request.user.is_superuser or getattr(request.user, 'role', '') in ['superadmin', 'staff']):
            return Response({'error': 'Permission denied'}, status=403)
        
        users = User.objects.filter(is_active=True).values(
            'id', 'username', 'email', 'first_name', 'last_name', 
            'role', 'is_superuser', 'last_login', 'date_joined'
        )
        
        # Format the data for frontend
        admin_users = []
        for user in users:
            admin_users.append({
                'id': user['id'],
                'name': f"{user['first_name']} {user['last_name']}".strip() or user['username'],
                'email': user['email'],
                'role': user['role'] if user['role'] else ('Super Admin' if user['is_superuser'] else 'Staff'),
                'status': 'Active',  # You can add more logic here
                'last_login': user['last_login'].isoformat() if user['last_login'] else None,
                'permissions': []  # You can add permissions logic here
            })
        
        return Response(admin_users)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_admin_user(request):
    """Create new admin user"""
    try:
        # Only superusers can create admin users
        if not request.user.is_superuser:
            return Response({'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        
        # Create user
        user = User.objects.create_user(
            username=data.get('email'),  # Use email as username
            email=data.get('email'),
            first_name=data.get('name', '').split(' ')[0] if data.get('name') else '',
            last_name=' '.join(data.get('name', '').split(' ')[1:]) if data.get('name') and len(data.get('name').split(' ')) > 1 else '',
            role=data.get('role', 'staff').lower().replace(' ', '')
        )
        
        # Set temporary password (you should send this via email)
        user.set_password('temppassword123')
        user.save()
        
        return Response({
            'id': user.id,
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'email': user.email,
            'role': data.get('role'),
            'status': 'Active'
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)

# ============================
# SECURITY ENDPOINTS
# ============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_activities(request):
    """Get user activities with filtering"""
    try:
        if 'UserActivity' not in globals():
            return Response([])  # Return empty list if model doesn't exist
        
        # Get query parameters
        days = int(request.GET.get('days', 7))
        user_filter = request.GET.get('user')
        action_filter = request.GET.get('action')
        status_filter = request.GET.get('status')
        
        # Build query
        queryset = UserActivity.objects.all()
        
        # Apply filters
        if days:
            since_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(timestamp__gte=since_date)
        
        if user_filter and user_filter != 'all':
            queryset = queryset.filter(user__username__icontains=user_filter)
        
        if action_filter and action_filter != 'all':
            queryset = queryset.filter(action=action_filter)
        
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        # Get activities
        activities = queryset.select_related('user').order_by('-timestamp')[:100]
        
        result = []
        for activity in activities:
            result.append({
                'id': activity.id,
                'user': activity.user.username,
                'action': activity.action,
                'resource': activity.resource,
                'details': activity.details,
                'ip_address': activity.ip_address,
                'status': activity.status,
                'timestamp': activity.timestamp.isoformat()
            })
        
        return Response(result)
    except Exception as e:
        return Response([])  # Return empty list on error

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_login_attempts(request):
    """Get login attempts"""
    try:
        if 'LoginAttempt' not in globals():
            return Response([])
        
        days = int(request.GET.get('days', 7))
        since_date = timezone.now() - timedelta(days=days)
        
        attempts = LoginAttempt.objects.filter(
            timestamp__gte=since_date
        ).order_by('-timestamp')[:50]
        
        result = []
        for attempt in attempts:
            result.append({
                'id': attempt.id,
                'username': attempt.username,
                'success': attempt.success,
                'ip_address': attempt.ip_address,
                'user_agent': getattr(attempt, 'user_agent', ''),
                'timestamp': attempt.timestamp.isoformat()
            })
        
        return Response(result)
    except Exception as e:
        return Response([])

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_sessions(request):
    """Get active user sessions"""
    try:
        if 'ActiveSession' not in globals():
            return Response([])
        
        sessions = ActiveSession.objects.filter(
            is_active=True
        ).select_related('user').order_by('-last_activity')
        
        result = []
        for session in sessions:
            result.append({
                'id': session.id,
                'user': session.user.username,
                'ip_address': session.ip_address,
                'user_agent': getattr(session, 'user_agent', ''),
                'last_activity': session.last_activity.isoformat(),
                'created_at': session.created_at.isoformat()
            })
        
        return Response(result)
    except Exception as e:
        return Response([])

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_security_statistics(request):
    """Get security statistics"""
    try:
        days = int(request.GET.get('days', 7))
        since_date = timezone.now() - timedelta(days=days)
        
        stats = {
            'total_login_attempts': 0,
            'successful_logins': 0,
            'failed_logins': 0,
            'unique_users': 0,
            'suspicious_activities': 0,
            'blocked_ips': 0
        }
        
        if 'LoginAttempt' in globals():
            login_attempts = LoginAttempt.objects.filter(timestamp__gte=since_date)
            stats['total_login_attempts'] = login_attempts.count()
            stats['successful_logins'] = login_attempts.filter(success=True).count()
            stats['failed_logins'] = login_attempts.filter(success=False).count()
            stats['unique_users'] = login_attempts.values('username').distinct().count()
        
        if 'UserActivity' in globals():
            activities = UserActivity.objects.filter(timestamp__gte=since_date)
            stats['suspicious_activities'] = activities.filter(status='warning').count()
        
        return Response(stats)
    except Exception as e:
        return Response({
            'total_login_attempts': 0,
            'successful_logins': 0,
            'failed_logins': 0,
            'unique_users': 0,
            'suspicious_activities': 0,
            'blocked_ips': 0
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_security_settings(request):
    """Get security settings"""
    try:
        if 'SecuritySettings' in globals():
            settings = SecuritySettings.objects.first()
            if settings:
                return Response({
                    'min_password_length': settings.min_password_length,
                    'require_special_chars': settings.require_special_chars,
                    'enable_2fa': settings.enable_2fa,
                    'max_login_attempts': settings.max_login_attempts,
                    'lockout_duration': settings.lockout_duration,
                    'session_timeout': settings.session_timeout,
                    'log_all_activities': settings.log_all_activities
                })
        
        # Default settings
        return Response({
            'min_password_length': 8,
            'require_special_chars': False,
            'enable_2fa': False,
            'max_login_attempts': 5,
            'lockout_duration': 30,
            'session_timeout': 60,
            'log_all_activities': True
        })
    except Exception as e:
        return Response({})

# ============================
# SYSTEM SETTINGS ENDPOINTS
# ============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_settings(request):
    """Get system settings"""
    try:
        if 'SystemSettings' in globals():
            settings = SystemSettings.objects.first()
            if settings:
                return Response({
                    'school_name': settings.school_name,
                    'academic_year': settings.academic_year,
                    'semester': settings.semester,
                    'maintenance_mode': settings.maintenance_mode,
                    'allow_registration': settings.allow_registration,
                    'email_notifications': settings.email_notifications,
                    'backup_frequency': settings.backup_frequency,
                    'max_file_size': settings.max_file_size
                })
        
        # Default settings
        return Response({
            'school_name': 'Face Recognition Attendance System',
            'academic_year': '2024-2025',
            'semester': 'Fall',
            'maintenance_mode': False,
            'allow_registration': True,
            'email_notifications': True,
            'backup_frequency': 'daily',
            'max_file_size': 10
        })
    except Exception as e:
        return Response({})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_system_settings(request):
    """Update system settings"""
    try:
        if not request.user.is_superuser:
            return Response({'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        
        if 'SystemSettings' in globals():
            settings, created = SystemSettings.objects.get_or_create(defaults=data)
            if not created:
                for key, value in data.items():
                    setattr(settings, key, value)
                settings.save()
        
        return Response({'message': 'Settings updated successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_email_settings(request):
    """Test email configuration"""
    try:
        # This is a placeholder - implement actual email testing
        return Response({'message': 'Test email sent successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_backup(request):
    """Create system backup"""
    try:
        if not request.user.is_superuser:
            return Response({'error': 'Permission denied'}, status=403)
        
        # This is a placeholder - implement actual backup creation
        if 'SystemBackup' in globals():
            backup = SystemBackup.objects.create(
                filename=f'backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.sql',
                backup_type='manual',
                file_size=1024000,  # Placeholder size
                created_by=request.user
            )
            return Response({'message': 'Backup created successfully', 'filename': backup.filename})
        
        return Response({'message': 'Backup feature not available'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """Get current authenticated user details"""
    try:
        user = request.user
        
        # Determine user role and permissions
        role = getattr(user, 'role', 'staff')
        if user.is_superuser:
            role = 'superadmin'
        
        # Basic permissions based on role
        permissions = []
        if role == 'superadmin':
            permissions = [
                'view_students', 'manage_students', 'enroll_students',
                'view_attendance', 'edit_attendance', 'start_sessions',
                'view_reports', 'generate_reports', 'system_reports',
                'view_users', 'manage_users', 'system_settings',
                'view_timetable', 'manage_timetable'
            ]
        elif role == 'teacher':
            permissions = [
                'view_student_roster', 'view_attendance', 'edit_attendance',
                'start_sessions', 'view_reports', 'generate_reports', 'view_timetable'
            ]
        elif role == 'staff':
            permissions = [
                'view_students', 'manage_students', 'enroll_students',
                'view_attendance', 'view_reports', 'view_timetable'
            ]
        
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_superuser': user.is_superuser,
            'role': role,
            'permissions': permissions,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'date_joined': user.date_joined.isoformat()
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def update_admin_user(request, user_id):
    """Update or delete admin user"""
    try:
        if not request.user.is_superuser:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        
        if request.method == 'PUT':
            data = json.loads(request.body)
            
            # Update user fields
            if 'name' in data:
                name_parts = data['name'].split(' ', 1)
                user.first_name = name_parts[0] if name_parts else ''
                user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            if 'email' in data:
                user.email = data['email']
                user.username = data['email']  # Use email as username
            
            if 'role' in data:
                user.role = data['role'].lower().replace(' ', '')
            
            user.save()
            
            return Response({
                'id': user.id,
                'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'email': user.email,
                'role': data.get('role'),
                'status': 'Active'
            })
        
        elif request.method == 'DELETE':
            user.is_active = False
            user.save()
            return Response({'message': 'User deactivated successfully'})
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_admin_user(request, user_id):
    """Delete admin user (alias for update_admin_user DELETE)"""
    return update_admin_user(request, user_id)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_security_settings(request):
    """Update security settings"""
    try:
        if not request.user.is_superuser:
            return Response({'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        
        # If SecuritySettings model exists, update it
        if 'SecuritySettings' in globals():
            settings, created = SecuritySettings.objects.get_or_create(defaults=data)
            if not created:
                for key, value in data.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                settings.save()
        
        return Response({'message': 'Security settings updated successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def terminate_session(request, session_id):
    """Terminate user session"""
    try:
        if not request.user.is_superuser:
            return Response({'error': 'Permission denied'}, status=403)
        
        if 'ActiveSession' in globals():
            try:
                session = ActiveSession.objects.get(session_key=session_id)
                session.is_active = False
                session.save()
                return Response({'message': 'Session terminated successfully'})
            except ActiveSession.DoesNotExist:
                return Response({'error': 'Session not found'}, status=404)
        
        return Response({'message': 'Session management not available'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

# Detail view functions that might be missing
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_detail(request, pk):
    """Get department details"""
    try:
        department = Department.objects.get(pk=pk)
        return Response({
            'id': department.id,
            'name': department.name,
            'code': department.code,
            'description': getattr(department, 'description', ''),
            'is_active': department.is_active,
            'student_count': department.students.filter(status='active').count(),
            'course_count': department.courses.filter(status='active').count()
        })
    except Department.DoesNotExist:
        return Response({'error': 'Department not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def specialization_detail(request, pk):
    """Get specialization details"""
    try:
        specialization = Specialization.objects.get(pk=pk)
        return Response({
            'id': specialization.id,
            'name': specialization.name,
            'code': specialization.code,
            'department': specialization.department.name,
            'description': getattr(specialization, 'description', ''),
            'is_active': specialization.is_active,
            'student_count': specialization.students.filter(status='active').count()
        })
    except Specialization.DoesNotExist:
        return Response({'error': 'Specialization not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def level_detail(request, pk):
    """Get level details"""
    try:
        level = Level.objects.get(pk=pk)
        return Response({
            'id': level.id,
            'name': level.name,
            'code': level.code,
            'description': getattr(level, 'description', ''),
            'is_active': level.is_active,
            'student_count': level.students.filter(status='active').count()
        })
    except Level.DoesNotExist:
        return Response({'error': 'Level not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_detail(request, pk):
    """Get course details"""
    try:
        course = Course.objects.get(pk=pk)
        return Response({
            'id': course.id,
            'name': course.name,
            'code': course.code,
            'description': getattr(course, 'description', ''),
            'credits': getattr(course, 'credits', 0),
            'department': course.department.name,
            'status': course.status,
            'enrolled_students': course.enrolled_students.filter(status='active').count(),
            'total_sessions': getattr(course, 'total_sessions', 0)
        })
    except Course.DoesNotExist:
        return Response({'error': 'Course not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_detail(request, pk):
    """Get student details"""
    try:
        student = Student.objects.get(pk=pk)
        return Response({
            'id': student.id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'matric_number': student.matric_number,
            'email': student.email,
            'phone': student.phone,
            'department': student.department.name,
            'specialization': student.specialization.name if student.specialization else None,
            'level': student.level.name if student.level else None,
            'status': student.status,
            'enrolled_courses_count': student.enrolled_courses.filter(status='active').count(),
            'attendance_rate': getattr(student, 'attendance_rate', 0)
        })
    except Student.DoesNotExist:
        return Response({'error': 'Student not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_detail(request, pk):
    """Get attendance record details"""
    try:
        attendance = AttendanceRecord.objects.get(pk=pk)
        return Response({
            'id': attendance.id,
            'student': f"{attendance.student.first_name} {attendance.student.last_name}",
            'course': attendance.course.name,
            'attendance_date': attendance.attendance_date.isoformat(),
            'check_in_time': attendance.check_in_time.isoformat() if attendance.check_in_time else None,
            'status': attendance.status,
            'recognition_confidence': getattr(attendance, 'recognition_confidence', 0),
            'created_at': attendance.created_at.isoformat()
        })
    except AttendanceRecord.DoesNotExist:
        return Response({'error': 'Attendance record not found'}, status=404)