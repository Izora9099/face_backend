from django.urls import path
from .views import (
    register_student, take_attendance, post_student_data, notify, admin_users_view, get_attendance_records, update_attendance_record
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import get_students, update_student
from .views import get_weekly_attendance_summary

urlpatterns = [
    path('register/', register_student),
    path('attendance/', take_attendance),
    path('post/', post_student_data),
    path('notify/', notify),
    path('admin-users/', admin_users_view),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('students/', get_students, name='get_students'),
    path('students/<int:id>/', update_student, name='update_student'),
    path('attendance-records/', get_attendance_records, name='get_attendance_records'),
    path('attendance-records/<int:record_id>/', update_attendance_record, name='update_attendance_record'),
    path('attendance-summary/', get_weekly_attendance_summary),

]
