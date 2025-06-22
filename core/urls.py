# Updated core/urls.py
from django.urls import path
from .views import (
    register_student, take_attendance, post_student_data, notify, admin_users_view,
    get_attendance_records, update_attendance_record, get_students, update_student,
    get_weekly_attendance_summary,
    # Add the new authentication views
    CustomTokenObtainPairView, get_current_user, logout_user,
    # Add the new security dashboard views
    get_user_activities, get_login_attempts, get_active_sessions, terminate_session,
    get_security_settings, update_security_settings, export_activity_log,
    get_security_statistics,
    get_system_settings, update_system_settings, get_system_stats, system_health_check, test_email_settings, create_backup, system_health_check_public,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Student management
    path('register/', register_student),
    path('students/', get_students, name='get_students'),
    path('students/<int:id>/', update_student, name='update_student'),
    path('post/', post_student_data),
    
    # Attendance management
    path('attendance/', take_attendance),
    path('attendance-records/', get_attendance_records, name='get_attendance_records'),
    path('attendance-records/<int:record_id>/', update_attendance_record, name='update_attendance_record'),
    path('attendance-summary/', get_weekly_attendance_summary),
    
    # Admin users
    path('admin-users/', admin_users_view),
    
    # Authentication endpoints
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/user/', get_current_user, name='current_user'),
    path('auth/logout/', logout_user, name='logout'),
    
    # Security Dashboard endpoints
    path('security/user-activities/', get_user_activities, name='get_user_activities'),
    path('security/login-attempts/', get_login_attempts, name='get_login_attempts'),
    path('security/active-sessions/', get_active_sessions, name='get_active_sessions'),
    path('security/terminate-session/<str:session_id>/', terminate_session, name='terminate_session'),
    path('security/settings/', get_security_settings, name='get_security_settings'),
    path('security/settings/update/', update_security_settings, name='update_security_settings'),
    path('security/export/activity-log/', export_activity_log, name='export_activity_log'),
    path('security/statistics/', get_security_statistics, name='get_security_statistics'),
    
    # Notifications
    path('notify/', notify),

    # System Settings endpoints
    path('api/system/settings/', get_system_settings, name='get_system_settings'),
    path('api/system/settings/update/', update_system_settings, name='update_system_settings'),
    path('api/system/stats/', get_system_stats, name='get_system_stats'),
    path('api/system/health/', system_health_check, name='system_health_check'),
    path('api/system/email/test/', test_email_settings, name='test_email_settings'),
    path('api/system/backup/create/', create_backup, name='create_backup'),
    
    # health check endpoints
    path('system/health/', system_health_check_public, name='public_health_check'),
    path('health/', system_health_check_public, name='health_check_alias'),
    
]