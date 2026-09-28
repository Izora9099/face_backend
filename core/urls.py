"""
API routes, mounted once under /api/ (see face_backend/urls.py).

The Android app's session routes are additionally exposed at the site root
for backward compatibility (see ANDROID_ROUTES).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet)
router.register(r'specializations', views.SpecializationViewSet)
router.register(r'levels', views.LevelViewSet)
router.register(r'courses', views.CourseViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'attendance', views.AttendanceViewSet)

# Consumed by the Android app - do not rename. Listed before the router so
# 'attendance/checkin/' is not captured by the attendance detail route.
ANDROID_ROUTES = [
    path('sessions/start/', views.start_attendance_session, name='start_attendance_session'),
    path('sessions/end/', views.end_attendance_session, name='end_attendance_session'),
    path('attendance/checkin/', views.session_based_attendance, name='session_based_attendance'),
    path('sessions/<str:session_id>/stats/', views.get_session_stats, name='get_session_stats'),
]

urlpatterns = ANDROID_ROUTES + [
    # Auth
    path('auth/login/', views.LoginView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/user/', views.get_current_user, name='get_current_user'),

    # Sessions (beyond the Android contract)
    path('sessions/', views.list_sessions, name='list_sessions'),
    path('sessions/<str:session_id>/mark/', views.manual_mark, name='session_manual_mark'),

    # Face enrolment / recognition
    path('register-student/', views.register_student, name='register_student'),
    path('recognize-face/', views.recognize_face, name='recognize_face'),
    path('students/<int:pk>/enroll-face/', views.enroll_face, name='student_enroll_face'),
    path('recognition/report/', views.recognition_report, name='recognition_report'),

    # Legacy flat lists
    path('get-students/', views.get_students, name='get_students'),
    path('get-attendance/', views.get_attendance_records, name='get_attendance_records'),

    # Dashboard and analytics
    path('dashboard/stats/', views.dashboard_stats, name='dashboard_stats'),
    path('analytics/departments/', views.department_stats, name='department_stats'),
    path('analytics/courses/', views.course_stats, name='course_stats'),
    path('analytics/teachers/', views.teacher_stats, name='teacher_stats'),

    # Enrolment
    path('enrollment/student/', views.manage_student_enrollment, name='manage_student_enrollment'),
    path('enrollment/bulk/', views.bulk_enrollment, name='bulk_enrollment'),

    # System
    path('system/stats/', views.system_stats, name='system_stats'),
    path('system/settings/', views.get_system_settings, name='get_system_settings'),
    path('system/settings/update/', views.update_system_settings, name='update_system_settings'),
    path('system/test-email/', views.test_email_settings, name='test_email_settings'),
    path('system/backup/create/', views.create_backup, name='create_backup'),
    path('system/backups/', views.list_backups, name='list_backups'),

    # Admin users
    path('admin-users/', views.get_admin_users, name='get_admin_users'),
    path('admin-users/create/', views.create_admin_user, name='create_admin_user'),
    path('admin-users/<int:user_id>/', views.update_admin_user, name='update_admin_user'),
    path('admin-users/<int:user_id>/delete/', views.delete_admin_user, name='delete_admin_user'),

    # Security
    path('security/activities/', views.get_user_activities, name='get_user_activities'),
    path('security/login-attempts/', views.get_login_attempts, name='get_login_attempts'),
    path('security/active-sessions/', views.get_active_sessions, name='get_active_sessions'),
    path('security/statistics/', views.get_security_statistics, name='get_security_statistics'),
    path('security/settings/', views.get_security_settings, name='get_security_settings'),
    path('security/settings/update/', views.update_security_settings, name='update_security_settings'),
    path('security/sessions/<str:session_id>/terminate/', views.terminate_session, name='terminate_session'),

    # Timetable
    path('timetable/entries/', views.timetable_entries, name='timetable_entries'),
    path('timetable/entries/<int:entry_id>/', views.timetable_entry_detail, name='timetable_entry_detail'),
    path('timetable/timeslots/', views.time_slots, name='time_slots'),
    path('timetable/rooms/', views.rooms, name='rooms'),
    path('timetable/teachers/', views.timetable_teachers, name='timetable_teachers'),
    path('timetable/courses/', views.timetable_courses, name='timetable_courses'),

    # Router (CRUD for academics, students, attendance)
    path('', include(router.urls)),
]
