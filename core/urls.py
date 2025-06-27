# core/urls.py - Add these URL patterns to your existing urlpatterns

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet)
router.register(r'specializations', views.SpecializationViewSet)
router.register(r'levels', views.LevelViewSet)
router.register(r'courses', views.CourseViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'attendance', views.AttendanceViewSet)

urlpatterns = [
    # Include ViewSet routes
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/user/', views.get_current_user, name='get_current_user'),  # Add this if missing
    
    # Legacy student and attendance endpoints (backward compatibility)
    path('register-student/', views.register_student, name='register_student'),
    path('recognize-face/', views.recognize_face, name='recognize_face'),
    path('get-students/', views.get_students, name='get_students'),
    path('get-attendance/', views.get_attendance_records, name='get_attendance_records'),
    
    # Dashboard and Analytics endpoints
    path('dashboard/stats/', views.dashboard_stats, name='dashboard_stats'),
    path('analytics/departments/', views.department_stats, name='department_stats'),
    path('analytics/courses/', views.course_stats, name='course_stats'),
    path('analytics/teachers/', views.teacher_stats, name='teacher_stats'),
    
    # Enrollment management endpoints
    path('enrollment/student/', views.manage_student_enrollment, name='manage_student_enrollment'),
    path('enrollment/bulk/', views.bulk_enrollment, name='bulk_enrollment'),
    
    # System management endpoints
    path('system/stats/', views.system_stats, name='system_stats'),
    path('system/settings/', views.get_system_settings, name='get_system_settings'),
    path('system/settings/update/', views.update_system_settings, name='update_system_settings'),
    path('system/test-email/', views.test_email_settings, name='test_email_settings'),
    path('system/backup/create/', views.create_backup, name='create_backup'),
    
    # Admin User Management endpoints
    path('admin-users/', views.get_admin_users, name='get_admin_users'),
    path('admin-users/create/', views.create_admin_user, name='create_admin_user'),
    path('admin-users/<int:user_id>/', views.update_admin_user, name='update_admin_user'),
    path('admin-users/<int:user_id>/delete/', views.delete_admin_user, name='delete_admin_user'),
    
    # Security Management endpoints
    path('security/activities/', views.get_user_activities, name='get_user_activities'),
    path('security/login-attempts/', views.get_login_attempts, name='get_login_attempts'),
    path('security/active-sessions/', views.get_active_sessions, name='get_active_sessions'),
    path('security/statistics/', views.get_security_statistics, name='get_security_statistics'),
    path('security/settings/', views.get_security_settings, name='get_security_settings'),
    path('security/settings/update/', views.update_security_settings, name='update_security_settings'),
    path('security/sessions/<str:session_id>/terminate/', views.terminate_session, name='terminate_session'),
    
    # Academic structure quick access endpoints
    path('departments/<int:pk>/', views.department_detail, name='department-detail'),
    path('specializations/<int:pk>/', views.specialization_detail, name='specialization-detail'),
    path('levels/<int:pk>/', views.level_detail, name='level-detail'),
    
    # Course detail endpoints
    path('courses/<int:pk>/', views.course_detail, name='course-detail'),
    path('courses/<int:pk>/students/', views.CourseViewSet.as_view({'get': 'students'}), name='course-students'),
    path('courses/<int:pk>/attendance/', views.CourseViewSet.as_view({'get': 'attendance'}), name='course-attendance'),
    path('courses/<int:pk>/enroll-students/', views.CourseViewSet.as_view({'post': 'enroll_students'}), name='course-enroll-students'),
    
    # Student detail endpoints
    path('students/<int:pk>/', views.student_detail, name='student-detail'),
    path('students/<int:pk>/courses/', views.StudentViewSet.as_view({'get': 'courses'}), name='student-courses'),
    path('students/<int:pk>/enroll-courses/', views.StudentViewSet.as_view({'post': 'enroll_courses'}), name='student-enroll-courses'),
    path('students/<int:pk>/auto-assign-courses/', views.StudentViewSet.as_view({'post': 'auto_assign_courses'}), name='student-auto-assign-courses'),
    path('students/<int:pk>/attendance-summary/', views.StudentViewSet.as_view({'get': 'attendance_summary'}), name='student-attendance-summary'),
    
    # Attendance detail endpoints
    path('attendance/<int:pk>/', views.attendance_detail, name='attendance-detail'),

    # Session Management Endpoints (matches Android app expectations)
    path('sessions/start/', views.start_attendance_session, name='start_attendance_session'),
    path('sessions/end/', views.end_attendance_session, name='end_attendance_session'),
    path('attendance/checkin/', views.session_based_attendance, name='session_based_attendance'),
    path('sessions/<str:session_id>/stats/', views.get_session_stats, name='get_session_stats'),
]