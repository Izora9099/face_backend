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
    readonly_fields = ['full_name', 'attendance_rate', 'created_at', 'updated_at']
    
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
# Admin User Admin (Enhanced)
# --------------------------
@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'first_name', 'last_name', 'email', 'role', 'is_active', 'last_login']
    list_filter = ['role', 'is_active', 'is_superuser', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']
    filter_horizontal = ['taught_courses']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('username', 'first_name', 'last_name', 'email', 'phone')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'permissions', 'is_active', 'is_superuser')
        }),
        ('Teaching Assignment', {
            'fields': ('taught_courses',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

# --------------------------
# System Management Admin
# --------------------------
@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'resource', 'status', 'timestamp']
    list_filter = ['action', 'status', 'timestamp']
    search_fields = ['user__username', 'resource', 'details']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']

@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['username', 'success', 'ip_address', 'timestamp']
    list_filter = ['success', 'timestamp']
    search_fields = ['username', 'ip_address']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']

@admin.register(ActiveSession)
class ActiveSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'session_key', 'ip_address', 'is_active', 'last_activity']
    list_filter = ['is_active', 'last_activity']
    search_fields = ['user__username', 'ip_address', 'session_key']
    ordering = ['-last_activity']
    readonly_fields = ['created_at', 'last_activity']

@admin.register(SecuritySettings)
class SecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ['min_password_length', 'enable_2fa', 'log_all_activities', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Password Policy', {
            'fields': ('min_password_length', 'require_uppercase', 'require_lowercase', 
                      'require_numbers', 'require_special_chars', 'password_expiry_days')
        }),
        ('Session Management', {
            'fields': ('session_timeout_minutes', 'max_concurrent_sessions')
        }),
        ('Login Security', {
            'fields': ('max_failed_attempts', 'lockout_duration_minutes')
        }),
        ('Two-Factor Authentication', {
            'fields': ('enable_2fa', 'force_2fa_for_admins')
        }),
        ('IP Restrictions', {
            'fields': ('enable_ip_whitelist', 'allowed_ip_ranges')
        }),
        ('Audit Settings', {
            'fields': ('log_all_activities', 'log_retention_days')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['school_name', 'academic_year', 'maintenance_mode', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('School Information', {
            'fields': ('school_name', 'school_address', 'school_phone', 'school_email', 'academic_year')
        }),
        ('Time and Localization', {
            'fields': ('timezone', 'date_format', 'time_format')
        }),
        ('Attendance Settings', {
            'fields': ('attendance_grace_period', 'late_threshold', 'auto_mark_absent_after', 
                      'require_checkout', 'allow_manual_attendance', 'attendance_notifications')
        }),
        ('Face Recognition Settings', {
            'fields': ('face_recognition_enabled', 'face_confidence_threshold', 'max_face_images_per_student',
                      'face_detection_timeout', 'auto_capture_enabled', 'face_image_quality_threshold'),
            'classes': ('collapse',)
        }),
        ('Email Settings', {
            'fields': ('email_enabled', 'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
                      'smtp_use_tls', 'email_from_address', 'email_from_name'),
            'classes': ('collapse',)
        }),
        ('Notification Settings', {
            'fields': ('send_absence_notifications', 'send_late_notifications', 'send_weekly_reports',
                      'parent_notification_enabled', 'admin_notification_enabled'),
            'classes': ('collapse',)
        }),
        ('Storage Settings', {
            'fields': ('max_file_upload_size', 'image_compression_quality', 'auto_backup_enabled',
                      'backup_frequency', 'backup_retention_days', 'storage_cleanup_enabled'),
            'classes': ('collapse',)
        }),
        ('System Maintenance', {
            'fields': ('maintenance_mode', 'maintenance_message', 'system_announcement',
                      'debug_mode', 'log_level')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(SystemBackup)
class SystemBackupAdmin(admin.ModelAdmin):
    list_display = ['filename', 'backup_type', 'file_size', 'created_at', 'created_by']
    list_filter = ['backup_type', 'created_at']
    search_fields = ['filename']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

# --------------------------
# Admin Site Customization
# --------------------------
admin.site.site_header = "FACE.IT Administration"
admin.site.site_title = "FACE.IT Admin"
admin.site.index_title = "Welcome to FACE.IT Administration"