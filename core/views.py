# core/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from .models import Student, AttendanceRecord, AdminUser
import numpy as np
import face_recognition
import json
import datetime
from . import face_utils  # Import the face_utils module
from datetime import timedelta
from .serializers import (
    SystemSettingsSerializer,
    SystemSettingsUpdateSerializer, 
    SystemStatsSerializer,
    SystemBackupSerializer,
    StudentSerializer,
    AttendanceSerializer
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import AdminUser  # Import your custom AdminUser model

from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta
from .models import UserActivity, LoginAttempt, ActiveSession, SecuritySettings
import csv
from django.core.mail import send_mail, get_connection, EmailMessage
from django.conf import settings
from django.db import connection
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import psutil
import os
import csv
import json
import zipfile
import tempfile
import time
from datetime import datetime, timedelta


@csrf_exempt
def register_student(request):
    """Updated student registration with MTCNN detection"""
    if request.method != 'POST':
        return JsonResponse({'status': 'fail', 'message': 'Only POST requests allowed.'}, status=405)

    name = request.POST.get('name')
    matric_number = request.POST.get('matric_number')
    image_file = request.FILES.get('image')

    if not name or not matric_number or not image_file:
        return JsonResponse({'status': 'fail', 'message': 'Missing name, Matriculation Number, or Image.'}, status=400)

    try:
        # Load and validate image using face_utils
        image = face_utils.preprocess_image(image_file)  # ✅ Proper reference
        if image is None:
            return JsonResponse({'status': 'fail', 'message': 'Failed to load image.'}, status=400)
        
        # Validate image quality using face_utils
        is_valid, message = face_utils.validate_image_quality(image)  # ✅ Proper reference
        if not is_valid:
            return JsonResponse({'status': 'fail', 'message': f'Image quality issue: {message}'}, status=400)

        # Get encoding using MTCNN + FaceNet (default)
        encoding, used_model = face_utils.get_encoding(image, model_name='facenet')  # ✅ Proper reference
        
        if encoding is None:
            # Fallback to MTCNN + dlib if FaceNet fails
            print("🔄 FaceNet failed, trying dlib...")
            encoding, used_model = face_utils.get_encoding(image, model_name='dlib')  # ✅ Proper reference
            
        if encoding is None:
            return JsonResponse({'status': 'fail', 'message': 'Failed to detect or encode face. Please ensure face is clearly visible.'}, status=400)

        # Check for existing student
        if Student.objects.filter(matric_number=matric_number).exists():
            return JsonResponse({'status': 'fail', 'message': 'A Student with that matriculation number already exists.'}, status=409)

        # Create student record
        Student.objects.create(
            name=name,
            matric_number=matric_number,
            face_encoding=encoding.tobytes(),
            face_encoding_model=used_model
        )

        return JsonResponse({
            'status': 'success', 
            'message': f'Student {name} registered successfully using {used_model}.',
            'model_used': used_model
        })

    except Exception as e:
        print(f"❌ Registration error: {str(e)}")
        return JsonResponse({'status': 'fail', 'message': f'Server error: {str(e)}'}, status=500)


@csrf_exempt
def take_attendance(request):
    """Updated attendance taking with MTCNN detection"""
    if request.method != 'POST':
        return JsonResponse({'status': 'fail', 'message': 'Only POST requests allowed.'}, status=405)
        
    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'status': 'fail', 'message': 'No image provided.'}, status=400)

    try:
        # Load and validate image using face_utils
        image = face_utils.preprocess_image(image_file)  # ✅ Proper reference
        if image is None:
            return JsonResponse({'status': 'fail', 'message': 'Failed to load image.'}, status=400)
        
        # Validate image quality using face_utils
        is_valid, message = face_utils.validate_image_quality(image)  # ✅ Proper reference
        if not is_valid:
            return JsonResponse({'status': 'fail', 'message': f'Image quality issue: {message}'}, status=400)

        # Try FaceNet first, then dlib
        unknown_encoding, used_model = face_utils.get_encoding(image, model_name='facenet')  # ✅ Proper reference
        
        if unknown_encoding is None:
            print("🔄 FaceNet failed, trying dlib...")
            unknown_encoding, used_model = face_utils.get_encoding(image, model_name='dlib')  # ✅ Proper reference

        if unknown_encoding is None:
            return JsonResponse({'status': 'fail', 'message': 'Failed to detect or encode face. Please ensure face is clearly visible.'}, status=400)

        # Compare against all registered students
        students = Student.objects.all()
        best_match = None
        
        for student in students:
            try:
                known_encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                
                # Use appropriate comparison based on encoding models using face_utils
                is_match = face_utils.compare_faces(known_encoding, unknown_encoding, student.face_encoding_model)  # ✅ Proper reference
                
                if is_match:
                    best_match = student
                    break
                    
            except Exception as e:
                print(f"❌ Error comparing with student {student.name}: {str(e)}")
                continue

        if best_match:
            # Record attendance
            AttendanceRecord.objects.create(
                student=best_match,
                timestamp=timezone.now(),
                recognition_model=used_model
            )
            return JsonResponse({
                'status': 'success', 
                'message': f'Attendance recorded for {best_match.name}.',
                'student_name': best_match.name,
                'model_used': used_model
            })
        else:
            return JsonResponse({'status': 'fail', 'message': 'Face not recognized. Please register first.'}, status=404)

    except Exception as e:
        print(f"❌ Attendance error: {str(e)}")
        return JsonResponse({'status': 'fail', 'message': f'Server error: {str(e)}'}, status=500)


@csrf_exempt
def post_student_data(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        matric_number = request.POST.get('matric_number')

        if not name or not matric_number:
            return JsonResponse({'status': 'fail', 'message': 'Name and matric number required.'}, status=400)

        if Student.objects.filter(matric_number=matric_number).exists():
            return JsonResponse({'status': 'fail', 'message': 'Student already exists.'}, status=400)

        Student.objects.create(name=name, matric_number=matric_number, face_encoding=b'')
        return JsonResponse({'status': 'success', 'message': 'Student info saved. Awaiting face scan.'})


@csrf_exempt
def notify(request):
    if request.method == 'GET':
        message = request.GET.get('message', 'Notification received.')
        return JsonResponse({'status': 'info', 'message': message})


@csrf_exempt
def admin_users_view(request):
    if request.method == 'GET':
        users = AdminUser.objects.all()
        data = [{
            "id": user.id,
            "name": user.first_name or user.username,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "status": "Active" if user.is_active else "Inactive",
            "permissions": user.permissions,
            "lastLogin": user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else ""
        } for user in users]
        return JsonResponse(data, safe=False)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)

            user = AdminUser.objects.create(
                username=data['email'],
                email=data['email'],
                first_name=data.get('name', ''),
                phone=data.get('phone', ''),
                role=data.get('role', 'Staff'),
                permissions=data.get('permissions', []),
                password=make_password('default1234')
            )
            return JsonResponse({'status': 'success', 'id': user.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


def user_list(request):
    users = AdminUser.objects.all()
    return render(request, 'user_list.html', {'users': users})


@csrf_exempt
def get_students(request):
    if request.method == 'GET':
        students = Student.objects.all()
        data = [
            {
                "id": student.id,
                "name": student.name,
                "matric_number": student.matric_number,
                "face_encoding_model": student.face_encoding_model,
                "registered_on": student.registered_on.strftime("%Y-%m-%d %H:%M")
            }
            for student in students
        ]
        return JsonResponse(data, safe=False)

    return JsonResponse({"error": "Only GET allowed"}, status=405)


@csrf_exempt
def update_student(request, id):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Only PUT allowed'}, status=405)

    try:
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)

        student = Student.objects.get(id=id)

        student.name = data.get('name', student.name)
        student.matric_number = data.get('matric_number', student.matric_number)
        student.face_encoding_model = data.get('face_encoding_model', student.face_encoding_model)
        student.save()

        return JsonResponse({'status': 'success', 'message': 'Student updated'})
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_attendance_records(request):
    date = request.GET.get('date')
    student_name = request.GET.get('name')
    matric_number = request.GET.get('matric_number')

    queryset = AttendanceRecord.objects.select_related('student').all()

    if date:
        queryset = queryset.filter(timestamp__date=date)
    if student_name:
        queryset = queryset.filter(student__name__icontains=student_name)
    if matric_number:
        queryset = queryset.filter(student__matric_number__icontains=matric_number)

    records = [{
        "id": record.id,
        "student_id": record.student.id,
        "student_name": record.student.name,
        "matric_number": record.student.matric_number,
        "status": record.status,
        "check_in": record.timestamp.strftime("%H:%M"),
        "date": record.timestamp.strftime("%Y-%m-%d"),
    } for record in queryset]

    return JsonResponse(
        records,
        safe=False,
        json_dumps_params={"ensure_ascii": False}
    )


@csrf_exempt
@require_http_methods(["PUT"])
def update_attendance_record(request, record_id):
    try:
        data = json.loads(request.body)
        record = AttendanceRecord.objects.select_related('student').get(id=record_id)

        new_status = data.get('status')
        new_time = data.get('check_in')

        if new_status:
            record.status = new_status

        if new_time:
            date_part = record.timestamp.strftime("%Y-%m-%d")
            updated_timestamp = datetime.datetime.strptime(f"{date_part} {new_time}", "%Y-%m-%d %H:%M")
            record.timestamp = timezone.make_aware(updated_timestamp)

        record.save()
        return JsonResponse({"status": "success", "message": "Attendance updated"})

    except AttendanceRecord.DoesNotExist:
        return JsonResponse({'error': 'Attendance record not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_weekly_attendance_summary(request):
    today = timezone.now().date()
    summary = []

    for i in range(7):
        day = today - timedelta(days=i)
        records = AttendanceRecord.objects.filter(timestamp__date=day)
        present_count = records.filter(status='Present').count()
        absent_count = records.filter(status='Absent').count()

        summary.append({
            "date": day.strftime("%a"),
            "present": present_count,
            "absent": absent_count,
        })

    return JsonResponse(list(reversed(summary)), safe=False)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer to include user data in token response"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add user data to the response
        user = self.user
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'phone': getattr(user, 'phone', ''),  # If your AdminUser has phone field
            'is_active': user.is_active,
            'is_staff': getattr(user, 'is_staff', False),
            'is_superuser': getattr(user, 'is_superuser', False),
            'role': getattr(user, 'role', 'Admin'),  # If your AdminUser has role field
        }
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view that includes user data"""
    serializer_class = CustomTokenObtainPairSerializer

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get or update current authenticated user information
    """
    if request.method == 'GET':
        try:
            user = request.user
            
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': getattr(user, 'first_name', ''),
                'last_name': getattr(user, 'last_name', ''),
                'name': f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or user.username,
                'phone': getattr(user, 'phone', ''),
                'is_active': user.is_active,
                'is_staff': getattr(user, 'is_staff', False),
                'is_superuser': getattr(user, 'is_superuser', False),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'date_joined': getattr(user, 'date_joined', None),
            }
            
            # Add AdminUser specific fields if available
            if hasattr(user, 'role'):
                user_data['role'] = user.role
            if hasattr(user, 'permissions'):
                user_data['permissions'] = user.permissions
                
            # Convert date_joined to ISO format if it exists
            if user_data['date_joined']:
                user_data['date_joined'] = user_data['date_joined'].isoformat()
            
            return Response(user_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to get user information',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'PUT':
        try:
            user = request.user
            data = request.data
            
            # Check if user can update (only superusers can update their own profile)
            if not user.is_superuser:
                return Response({
                    'error': 'Permission denied',
                    'message': 'Only superadmin can update profile information'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate current password if changing password
            if 'new_password' in data and data['new_password']:
                current_password = data.get('current_password')
                if not current_password:
                    return Response({
                        'error': 'Current password required',
                        'message': 'Current password is required to change password'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if not check_password(current_password, user.password):
                    return Response({
                        'error': 'Invalid password',
                        'message': 'Current password is incorrect'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update basic fields
            if 'first_name' in data:
                user.first_name = data['first_name']
            if 'last_name' in data:
                user.last_name = data['last_name']
            if 'email' in data:
                # Check if email is already taken by another user
                if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
                    return Response({
                        'error': 'Email already exists',
                        'message': 'This email is already registered to another user'
                    }, status=status.HTTP_400_BAD_REQUEST)
                user.email = data['email']
            
            # Update phone if user model has phone field
            if 'phone' in data and hasattr(user, 'phone'):
                user.phone = data['phone']
            
            # Update password if provided
            if 'new_password' in data and data['new_password']:
                user.set_password(data['new_password'])
            
            user.save()
            
            # Return updated user data
            updated_user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'phone': getattr(user, 'phone', ''),
                'is_active': user.is_active,
                'is_staff': getattr(user, 'is_staff', False),
                'is_superuser': getattr(user, 'is_superuser', False),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'date_joined': user.date_joined.isoformat() if hasattr(user, 'date_joined') else None,
                'role': getattr(user, 'role', None),
                'permissions': getattr(user, 'permissions', []),
            }
            
            return Response(updated_user_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to update profile',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """
    Logout user by blacklisting the refresh token
    """
    try:
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                message = 'Successfully logged out and token blacklisted'
            except Exception as e:
                # If blacklisting fails, still consider logout successful
                message = f'Logged out (token blacklist failed: {str(e)})'
        else:
            message = 'Logged out (no refresh token provided)'
        
        return Response({
            'success': True,
            'message': message
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error during logout: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

# Helper function to log user activities
def log_user_activity(user, action, resource, details, request, resource_id=None, status_type='success'):
    """Log user activity"""
    try:
        UserActivity.objects.create(
            user=user,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            session_id=request.session.session_key or '',
            status=status_type
        )
    except Exception as e:
        print(f"Error logging activity: {e}")

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_user_activities(request):
    """Get user activities with filtering"""
    try:
        # Get query parameters for filtering
        user_filter = request.GET.get('user', '')
        action_filter = request.GET.get('action', '')
        status_filter = request.GET.get('status', '')
        days = int(request.GET.get('days', 7))  # Default last 7 days
        
        # Base queryset
        activities = UserActivity.objects.select_related('user').all()
        
        # Apply filters
        if user_filter:
            activities = activities.filter(user__username=user_filter)
        if action_filter:
            activities = activities.filter(action=action_filter)
        if status_filter:
            activities = activities.filter(status=status_filter)
        
        # Date filter
        start_date = timezone.now() - timedelta(days=days)
        activities = activities.filter(timestamp__gte=start_date)
        
        # Limit results
        activities = activities[:500]  # Limit to 500 recent activities
        
        # Serialize data
        data = []
        for activity in activities:
            data.append({
                'id': activity.id,
                'user': {
                    'username': activity.user.username,
                    'full_name': f"{activity.user.first_name} {activity.user.last_name}".strip() or activity.user.username,
                    'role': getattr(activity.user, 'role', 'User')
                },
                'action': activity.action,
                'resource': activity.resource,
                'resource_id': activity.resource_id,
                'details': activity.details,
                'ip_address': activity.ip_address,
                'timestamp': activity.timestamp.isoformat(),
                'status': activity.status,
                'session_id': activity.session_id
            })
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to fetch user activities',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_login_attempts(request):
    """Get login attempts"""
    try:
        days = int(request.GET.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        attempts = LoginAttempt.objects.filter(
            timestamp__gte=start_date
        ).order_by('-timestamp')[:200]
        
        data = []
        for attempt in attempts:
            data.append({
                'id': attempt.id,
                'username': attempt.username,
                'ip_address': attempt.ip_address,
                'location': attempt.location,
                'timestamp': attempt.timestamp.isoformat(),
                'success': attempt.success,
                'user_agent': attempt.user_agent,
                'reason': attempt.failure_reason
            })
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to fetch login attempts',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_active_sessions(request):
    """Get active user sessions"""
    try:
        # Clean up expired sessions first
        expired_sessions = ActiveSession.objects.filter(
            last_activity__lt=timezone.now() - timedelta(hours=24)
        )
        expired_sessions.delete()
        
        sessions = ActiveSession.objects.select_related('user').filter(
            last_activity__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-last_activity')
        
        data = []
        for session in sessions:
            data.append({
                'id': session.session_key,
                'user': session.user.username,
                'role': getattr(session.user, 'role', 'User'),
                'ip_address': session.ip_address,
                'location': session.location,
                'device': session.user_agent,
                'last_activity': session.last_activity.isoformat(),
                'created_at': session.created_at.isoformat(),
                'activity_count': session.activity_count
            })
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to fetch active sessions',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def terminate_session(request, session_id):
    """Terminate a user session"""
    try:
        # Remove from Django sessions
        try:
            session = Session.objects.get(session_key=session_id)
            session.delete()
        except Session.DoesNotExist:
            pass
        
        # Remove from our tracking
        try:
            active_session = ActiveSession.objects.get(session_key=session_id)
            terminated_user = active_session.user.username
            active_session.delete()
        except ActiveSession.DoesNotExist:
            terminated_user = "Unknown"
        
        # Log the action
        log_user_activity(
            user=request.user,
            action='TERMINATE_SESSION',
            resource='sessions',
            details=f'Terminated session for user: {terminated_user}',
            request=request
        )
        
        return Response({
            'success': True,
            'message': 'Session terminated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to terminate session',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_security_settings(request):
    """Get current security settings"""
    try:
        settings = SecuritySettings.get_settings()
        
        data = {
            'max_login_attempts': settings.max_login_attempts,
            'lockout_duration': settings.lockout_duration,
            'session_timeout': settings.session_timeout,
            'require_2fa': settings.require_2fa,
            'password_expiry_days': settings.password_expiry_days,
            'min_password_length': settings.min_password_length,
            'allow_multiple_sessions': settings.allow_multiple_sessions,
            'ip_whitelist_enabled': settings.ip_whitelist_enabled,
            'audit_log_retention_days': settings.audit_log_retention_days,
            'track_user_activities': settings.track_user_activities,
            'alert_on_suspicious_activity': settings.alert_on_suspicious_activity,
        }
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to fetch security settings',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_security_settings(request):
    """Update security settings"""
    try:
        settings = SecuritySettings.get_settings()
        
        # Update fields from request data
        for field in ['max_login_attempts', 'lockout_duration', 'session_timeout', 
                     'require_2fa', 'password_expiry_days', 'min_password_length',
                     'allow_multiple_sessions', 'ip_whitelist_enabled', 
                     'audit_log_retention_days', 'track_user_activities', 
                     'alert_on_suspicious_activity']:
            if field in request.data:
                setattr(settings, field, request.data[field])
        
        settings.updated_by = request.user
        settings.save()
        
        # Log the action
        log_user_activity(
            user=request.user,
            action='CHANGE_SECURITY_SETTINGS',
            resource='security_settings',
            details='Updated security configuration',
            request=request
        )
        
        return Response({
            'success': True,
            'message': 'Security settings updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to update security settings',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def export_activity_log(request):
    """Export activity log as CSV"""
    try:
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        activities = UserActivity.objects.select_related('user').filter(
            timestamp__gte=start_date
        ).order_by('-timestamp')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="activity_log_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'User', 'Role', 'Action', 'Resource', 
            'Details', 'Status', 'IP Address', 'User Agent'
        ])
        
        for activity in activities:
            writer.writerow([
                activity.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                activity.user.username,
                getattr(activity.user, 'role', 'User'),
                activity.get_action_display(),
                activity.resource,
                activity.details,
                activity.get_status_display(),
                activity.ip_address,
                activity.user_agent
            ])
        
        # Log the export action
        log_user_activity(
            user=request.user,
            action='GENERATE_REPORT',
            resource='activity_log',
            details=f'Exported activity log for last {days} days',
            request=request
        )
        
        return response
        
    except Exception as e:
        return Response({
            'error': 'Failed to export activity log',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_security_statistics(request):
    """Get security statistics and metrics"""
    try:
        days = int(request.GET.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        # Activity statistics
        total_activities = UserActivity.objects.filter(timestamp__gte=start_date).count()
        failed_activities = UserActivity.objects.filter(
            timestamp__gte=start_date, status='failed'
        ).count()
        
        # Login statistics
        total_logins = LoginAttempt.objects.filter(timestamp__gte=start_date).count()
        failed_logins = LoginAttempt.objects.filter(
            timestamp__gte=start_date, success=False
        ).count()
        
        # Active users
        active_users = UserActivity.objects.filter(
            timestamp__gte=start_date
        ).values('user').distinct().count()
        
        # Active sessions
        active_sessions = ActiveSession.objects.filter(
            last_activity__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        data = {
            'total_activities': total_activities,
            'failed_activities': failed_activities,
            'total_logins': total_logins,
            'failed_logins': failed_logins,
            'active_users': active_users,
            'active_sessions': active_sessions,
            'period_days': days
        }
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to fetch security statistics',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        exclude = ['created_at', 'updated_at', 'updated_by']
    
    def validate_smtp_password(self, value):
        """Don't return the actual password for security"""
        if value:
            return '***HIDDEN***'
        return value

class SystemSettingsUpdateSerializer(serializers.ModelSerializer):
    """Separate serializer for updates to handle password properly"""
    class Meta:
        model = SystemSettings
        exclude = ['created_at', 'updated_at', 'updated_by']
    
    def update(self, instance, validated_data):
        # Handle password field specially
        if 'smtp_password' in validated_data:
            password = validated_data['smtp_password']
            if password != '***HIDDEN***':  # Only update if not the hidden placeholder
                instance.smtp_password = password
            validated_data.pop('smtp_password')
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

class SystemStatsSerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()
    database_size = serializers.CharField()
    storage_used = serializers.CharField()
    system_uptime = serializers.CharField()
    last_backup = serializers.CharField()
    system_version = serializers.CharField()

class SystemBackupSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemBackup
        fields = ['id', 'filename', 'file_size', 'file_size_mb', 'backup_type', 'created_at', 'created_by']
    
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_settings(request):
    """Get current system settings"""
    try:
        settings_obj = SystemSettings.get_settings()
        serializer = SystemSettingsSerializer(settings_obj)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve system settings: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def update_system_settings(request):
    """Update system settings"""
    try:
        settings_obj = SystemSettings.get_settings()
        serializer = SystemSettingsUpdateSerializer(settings_obj, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response({'message': 'System settings updated successfully'})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f'Failed to update system settings: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_stats(request):
    """Get system statistics"""
    try:
        # Count totals
        total_students = Student.objects.count()
        total_users = User.objects.count()
        total_attendance_records = Attendance.objects.count()
        
        # Database size (SQLite specific since you're using db.sqlite3)
        try:
            db_path = settings.DATABASES['default']['NAME']
            db_size_bytes = os.path.getsize(db_path)
            db_size = f"{round(db_size_bytes / (1024 * 1024), 1)} MB"
        except:
            db_size = "Unknown"
        
        # Storage usage
        try:
            disk_usage = psutil.disk_usage('/')
            storage_used = f"{round(disk_usage.used / (1024**3), 1)} GB"
        except:
            storage_used = "Unknown"
        
        # System uptime
        try:
            uptime_seconds = int(time.time() - psutil.boot_time())
            uptime_days = uptime_seconds // 86400
            uptime_hours = (uptime_seconds % 86400) // 3600
            system_uptime = f"{uptime_days} days, {uptime_hours} hours"
        except:
            system_uptime = "Unknown"
        
        # Last backup
        last_backup = SystemBackup.objects.first()
        last_backup_str = last_backup.created_at.isoformat() if last_backup else "Never"
        
        stats = {
            'total_students': total_students,
            'total_users': total_users,
            'total_attendance_records': total_attendance_records,
            'database_size': db_size,
            'storage_used': storage_used,
            'system_uptime': system_uptime,
            'last_backup': last_backup_str,
            'system_version': getattr(settings, 'VERSION', '1.0.0')
        }
        
        serializer = SystemStatsSerializer(stats)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve system stats: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_email_settings(request):
    """Test email configuration by sending a test email"""
    try:
        settings_obj = SystemSettings.get_settings()
        
        if not settings_obj.email_enabled:
            return Response(
                {'error': 'Email is not enabled in system settings'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Configure email settings temporarily
        connection = get_connection(
            host=settings_obj.smtp_host,
            port=settings_obj.smtp_port,
            username=settings_obj.smtp_username,
            password=settings_obj.smtp_password,
            use_tls=settings_obj.smtp_use_tls,
        )
        
        # Send test email
        email = EmailMessage(
            subject='FACE.IT System - Test Email',
            body=f'This is a test email from the FACE.IT attendance system.\n\nSent at: {timezone.now()}',
            from_email=f"{settings_obj.email_from_name} <{settings_obj.email_from_address}>",
            to=[request.user.email] if request.user.email else [settings_obj.school_email],
            connection=connection,
        )
        
        email.send()
        
        return Response({'message': 'Test email sent successfully'})
    except Exception as e:
        return Response(
            {'error': f'Failed to send test email: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_backup(request):
    """Create a system backup"""
    try:
        # Create backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"faceit_backup_{timestamp}.zip"
        
        # Create temporary directory for backup files
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = os.path.join(temp_dir, backup_filename)
            
            # Create zip file
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Export students data
                students_file = os.path.join(temp_dir, 'students.csv')
                with open(students_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['ID', 'Student ID', 'Name', 'Email', 'Class', 'Created At'])
                    for student in Student.objects.all():
                        writer.writerow([
                            student.id, student.student_id, student.name, 
                            student.email, student.student_class, student.created_at
                        ])
                zipf.write(students_file, 'students.csv')
                
                # Export attendance data
                attendance_file = os.path.join(temp_dir, 'attendance.csv')
                with open(attendance_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['ID', 'Student ID', 'Student Name', 'Date', 'Status', 'Check In', 'Check Out', 'Created At'])
                    for attendance in Attendance.objects.select_related('student').all():
                        writer.writerow([
                            attendance.id, attendance.student.student_id, attendance.student.name,
                            attendance.date, attendance.status, attendance.check_in_time,
                            attendance.check_out_time, attendance.created_at
                        ])
                zipf.write(attendance_file, 'attendance.csv')
                
                # Export system settings
                settings_file = os.path.join(temp_dir, 'system_settings.json')
                settings_obj = SystemSettings.get_settings()
                settings_data = SystemSettingsSerializer(settings_obj).data
                with open(settings_file, 'w') as jsonfile:
                    json.dump(settings_data, jsonfile, indent=2, default=str)
                zipf.write(settings_file, 'system_settings.json')
                
                # Copy the SQLite database
                db_path = settings.DATABASES['default']['NAME']
                if os.path.exists(db_path):
                    zipf.write(db_path, 'database.sqlite3')
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            
            # Save backup record
            backup_record = SystemBackup.objects.create(
                filename=backup_filename,
                file_path=backup_path,  # In production, move to permanent storage
                file_size=file_size,
                backup_type='manual',
                created_by=request.user
            )
            
            return Response({
                'message': 'Backup created successfully',
                'backup_id': backup_record.id,
                'filename': backup_filename,
                'size_mb': round(file_size / (1024 * 1024), 2)
            })
    except Exception as e:
        return Response(
            {'error': f'Failed to create backup: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health_check(request):
    """Check system health status"""
    try:
        health_status = {
            'database': 'connected',
            'storage': 'available',
            'email': 'not_configured',
            'face_recognition': 'active'
        }
        
        # Check database connection
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status['database'] = 'connected'
        except:
            health_status['database'] = 'error'
        
        # Check email configuration
        settings_obj = SystemSettings.get_settings()
        if settings_obj.email_enabled and settings_obj.smtp_host:
            health_status['email'] = 'configured'
        
        # Check storage
        try:
            disk_usage = psutil.disk_usage('/')
            if disk_usage.free < 1024**3:  # Less than 1GB free
                health_status['storage'] = 'low_space'
        except:
            health_status['storage'] = 'error'
        
        return Response(health_status)
    except Exception as e:
        return Response(
            {'error': f'Failed to check system health: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
