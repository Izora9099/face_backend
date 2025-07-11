# core/admin.py
from django.contrib import admin
from .models import (
    AdminUser, Student, AttendanceRecord, Department, Specialization, 
    Level, Course, UserActivity, LoginAttempt, ActiveSession, 
    SecuritySettings, SystemSettings, SystemBackup
)

# --------------------------
# Academic Structure Admin
# --------------------------
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['department_name', 'department_code', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['department_name', 'department_code']
    ordering = ['department_name']

@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ['specialization_name', 'specialization_code', 'department', 'is_active', 'created_at']
    list_filter = ['department', 'is_active', 'created_at']
    search_fields = ['specialization_name', 'specialization_code', 'department__department_name']
    ordering = ['specialization_name']

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ['level_name', 'level_code', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['level_name', 'level_code']
    ordering = ['level_name']
    filter_horizontal = ['departments', 'specializations']

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['course_code', 'course_name', 'department', 'level', 'credits', 'status', 'created_at']
    list_filter = ['department', 'level', 'status', 'created_at']
    search_fields = ['course_code', 'course_name', 'department__department_name']
    ordering = ['course_code']
    filter_horizontal = ['specializations', 'teachers']

# --------------------------
# Student Admin
# --------------------------
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'matric_number', 'email', 'department', 'specialization', 'level', 'status', 'attendance_rate']
    list_filter = ['department', 'specialization', 'level', 'status', 'created_at']
    search_fields = ['first_name', 'last_name', 'matric_number', 'email']
    ordering = ['first_name', 'last_name']
    filter_horizontal = ['enrolled_courses']
    readonly_fields = ['full_name', 'attendance_rate', 'created_at', 'updated_at', 'registered_on']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'matric_number', 'email', 'phone', 'address')
        }),
        ('Academic Information', {
            'fields': ('department', 'specialization', 'level', 'enrolled_courses', 'status')
        }),
        ('Face Recognition', {
            'fields': ('face_encoding_model',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('attendance_rate',),
            'classes': ('collapse',)
        }),
        ('Legacy Fields', {
            'fields': ('name', 'student_id', 'student_class'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'registered_on'),
            'classes': ('collapse',)
        }),
    )

# --------------------------
# Attendance Admin
# --------------------------
@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'status', 'attendance_date', 'check_in_time', 'recognition_model']
    list_filter = ['status', 'course', 'attendance_date', 'recognition_model', 'created_at']
    search_fields = ['student__first_name', 'student__last_name', 'student__matric_number', 'course__course_code']
    ordering = ['-check_in_time']
    readonly_fields = ['created_at', 'updated_at', 'timestamp']
    
    fieldsets = (
        ('Attendance Information', {
            'fields': ('student', 'course', 'status', 'attendance_date')
        }),
        ('Time Information', {
            'fields': ('check_in_time', 'check_out_time')
        }),
        ('Recognition Details', {
            'fields': ('recognition_model',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'timestamp'),
            'classes': ('collapse',)
        }),
    )

# --------------------------
# Fixed Admin User Admin
# --------------------------
@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'first_name', 'last_name', 'email', 'role', 'department', 'is_active', 'last_login']
    list_filter = ['role', 'department', 'specialization', 'is_active', 'is_superuser', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'employee_id']
    ordering = ['username']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('username', 'first_name', 'last_name', 'email', 'phone')
        }),
        ('Professional Information', {
            'fields': ('department', 'specialization', 'employee_id', 'job_title', 'hire_date', 'is_department_head'),
            'description': 'Department and role-specific information'
        }),
        ('Role & Permissions', {
            'fields': ('role', 'permissions', 'is_active', 'is_superuser')
        }),
        ('Password', {
            'fields': ('password',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['last_login', 'date_joined']
# --------------------------
# System Management Admin (Only include if models exist)
# --------------------------

# Only register if the models exist
try:
    @admin.register(UserActivity)
    class UserActivityAdmin(admin.ModelAdmin):
        list_display = ['user', 'action', 'resource', 'status', 'timestamp']
        list_filter = ['action', 'status', 'timestamp']
        search_fields = ['user__username', 'resource', 'details']
        ordering = ['-timestamp']
        readonly_fields = ['timestamp']
except:
    pass

try:
    @admin.register(LoginAttempt)
    class LoginAttemptAdmin(admin.ModelAdmin):
        list_display = ['username', 'success', 'ip_address', 'timestamp']
        list_filter = ['success', 'timestamp']
        search_fields = ['username', 'ip_address']
        ordering = ['-timestamp']
        readonly_fields = ['timestamp']
except:
    pass

try:
    @admin.register(ActiveSession)
    class ActiveSessionAdmin(admin.ModelAdmin):
        list_display = ['user', 'session_key', 'ip_address', 'is_active', 'last_activity']
        list_filter = ['is_active', 'last_activity']
        search_fields = ['user__username', 'ip_address', 'session_key']
        ordering = ['-last_activity']
        readonly_fields = ['created_at', 'last_activity']
except:
    pass

try:
    @admin.register(SecuritySettings)
    class SecuritySettingsAdmin(admin.ModelAdmin):
        list_display = ['min_password_length', 'enable_2fa', 'log_all_activities', 'updated_at']
        readonly_fields = ['created_at', 'updated_at']
except:
    pass

try:
    @admin.register(SystemSettings)
    class SystemSettingsAdmin(admin.ModelAdmin):
        list_display = ['school_name', 'academic_year', 'maintenance_mode', 'updated_at']
        readonly_fields = ['created_at', 'updated_at']
except:
    pass

try:
    @admin.register(SystemBackup)
    class SystemBackupAdmin(admin.ModelAdmin):
        list_display = ['filename', 'backup_type', 'file_size', 'created_at', 'created_by']
        list_filter = ['backup_type', 'created_at']
        search_fields = ['filename']
        ordering = ['-created_at']
        readonly_fields = ['created_at']
except:
    pass

# --------------------------
# Admin Site Customization
# --------------------------
admin.site.site_header = "FACE.IT Administration"
admin.site.site_title = "FACE.IT Admin"
admin.site.index_title = "Welcome to FACE.IT Administration"