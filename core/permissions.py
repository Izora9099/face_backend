"""
Role-based access for FACE.IT.

Roles (AdminUser.role): superadmin, staff, teacher. Django superusers are
always treated as superadmin.

- superadmin: everything
- staff: manage academics, students, enrolment, timetable; read reports
- teacher: read-only academics; students/attendance/sessions limited to the
  courses they teach
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

SUPERADMIN = 'superadmin'
STAFF = 'staff'
TEACHER = 'teacher'
ADMIN_ROLES = (SUPERADMIN, STAFF)


def user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return SUPERADMIN
    return getattr(user, 'role', None) or STAFF


def is_teacher(user):
    return user_role(user) == TEACHER


def is_admin(user):
    """superadmin or staff."""
    return user_role(user) in ADMIN_ROLES


def teacher_owns_course(user, course):
    return course.teachers.filter(pk=user.pk).exists()


def can_access_course(user, course):
    return is_admin(user) or (is_teacher(user) and teacher_owns_course(user, course))


class IsSuperAdmin(BasePermission):
    message = 'Superadmin role required.'

    def has_permission(self, request, view):
        return user_role(request.user) == SUPERADMIN


class IsAdminRole(BasePermission):
    """superadmin or staff."""
    message = 'Superadmin or staff role required.'

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsAdminOrReadOnly(BasePermission):
    """Any role may read; only superadmin/staff may write."""
    message = 'Only superadmin or staff can modify this resource.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or is_admin(request.user)


class IsAdminOrTeacher(BasePermission):
    """Any known role. Object/queryset scoping for teachers is done in views."""

    def has_permission(self, request, view):
        return user_role(request.user) in (SUPERADMIN, STAFF, TEACHER)
