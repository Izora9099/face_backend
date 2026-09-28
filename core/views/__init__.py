"""API views, split by domain. Re-exported here so `from core import views` keeps working."""

from .academics import CourseViewSet, DepartmentViewSet, LevelViewSet, SpecializationViewSet  # noqa: F401
from .attendance import AttendanceViewSet, get_attendance_records  # noqa: F401
from .auth import (  # noqa: F401
    LoginView, create_admin_user, delete_admin_user, get_admin_users, get_current_user,
    update_admin_user,
)
from .recognition import enroll_face, recognize_face, register_student  # noqa: F401
from .security import (  # noqa: F401
    get_active_sessions, get_login_attempts, get_security_settings, get_security_statistics,
    get_user_activities, terminate_session, update_security_settings,
)
from .sessions import (  # noqa: F401
    end_attendance_session, get_session_stats, list_sessions, manual_mark,
    session_based_attendance, start_attendance_session,
)
from .students import (  # noqa: F401
    StudentViewSet, bulk_enrollment, get_students, manage_student_enrollment,
)
from .system import (  # noqa: F401
    course_stats, create_backup, dashboard_stats, department_stats, get_system_settings,
    list_backups, recognition_report, system_stats, teacher_stats, test_email_settings,
    update_system_settings,
)
from .timetable import (  # noqa: F401
    rooms, time_slots, timetable_courses, timetable_entries, timetable_entry_detail,
    timetable_teachers,
)
