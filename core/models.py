from django.db import models
from django_cryptography.fields import encrypt
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.validators import MinValueValidator, MaxValueValidator
import json

# --------------------------
# Custom Admin User Model
# --------------------------
class AdminUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, default='Staff')
    permissions = models.JSONField(default=list)

    def __str__(self):
        return self.username

# --------------------------
# Student Model
# --------------------------
class Student(models.Model):
    name = models.CharField(max_length=255)
    matric_number = models.CharField(max_length=50, unique=True)
    
    # Add fields that are referenced in views but missing
    student_id = models.CharField(max_length=50, unique=True, null=True, blank=True)  # Add this
    email = models.EmailField(blank=True)  # Add this
    student_class = models.CharField(max_length=100, blank=True)  # Add this

    # 🔐 Encrypted binary field
    face_encoding = encrypt(models.BinaryField())
    face_encoding_model = models.CharField(max_length=10, default='cnn')
    registered_on = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Add this

    def __str__(self):
        return f"{self.name} ({self.matric_number})"

# --------------------------
# Attendance Record Model
# --------------------------
class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default='Present')
    recognition_model = models.CharField(max_length=10, default='cnn')

    def __str__(self):
        return f"{self.student.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

# Add an alias for compatibility with views
class Attendance(AttendanceRecord):
    class Meta:
        proxy = True
    
    @property
    def date(self):
        return self.timestamp.date()
    
    @property
    def check_in_time(self):
        return self.timestamp.time()
    
    @property
    def check_out_time(self):
        # Return None or implement checkout logic if needed
        return None
    
    @property
    def created_at(self):
        return self.timestamp

# Get the User model
User = get_user_model()

class UserActivity(models.Model):
    """Track all user activities in the system"""
    ACTION_CHOICES = [
        ('VIEW_STUDENTS', 'View Students'),
        ('MARK_ATTENDANCE', 'Mark Attendance'),
        ('USE_FACE_RECOGNITION', 'Use Face Recognition'),
        ('GENERATE_REPORT', 'Generate Report'),
        ('UPDATE_STUDENT', 'Update Student'),
        ('DELETE_ATTENDANCE', 'Delete Attendance'),
        ('CREATE_STUDENT', 'Create Student'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('VIEW_ADMIN_USERS', 'View Admin Users'),
        ('CREATE_ADMIN_USER', 'Create Admin User'),
        ('UPDATE_ADMIN_USER', 'Update Admin User'),
        ('DELETE_ADMIN_USER', 'Delete Admin User'),
        ('CHANGE_SECURITY_SETTINGS', 'Change Security Settings'),
        ('TERMINATE_SESSION', 'Terminate Session'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    resource = models.CharField(max_length=100)  # e.g., 'students', 'attendance', etc.
    resource_id = models.IntegerField(null=True, blank=True)  # ID of the affected resource
    details = models.TextField()  # Human-readable description
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='success')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['status', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"


class LoginAttempt(models.Model):
    """Track all login attempts (successful and failed)"""
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=100, blank=True)  # Geolocation
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=200, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
            models.Index(fields=['success', '-timestamp']),
        ]
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.username} - {status} - {self.timestamp}"


class ActiveSession(models.Model):
    """Track active user sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    activity_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.username} - {self.session_key[:8]}... - {self.last_activity}"


class SecuritySettings(models.Model):
    """Store security configuration settings"""
    max_login_attempts = models.PositiveIntegerField(default=5)
    lockout_duration = models.PositiveIntegerField(default=30)  # minutes
    session_timeout = models.PositiveIntegerField(default=60)  # minutes
    require_2fa = models.BooleanField(default=False)
    password_expiry_days = models.PositiveIntegerField(default=90)
    min_password_length = models.PositiveIntegerField(default=8)
    allow_multiple_sessions = models.BooleanField(default=True)
    ip_whitelist_enabled = models.BooleanField(default=False)
    ip_whitelist = models.JSONField(default=list, blank=True)  # List of allowed IPs
    audit_log_retention_days = models.PositiveIntegerField(default=365)
    track_user_activities = models.BooleanField(default=True)
    alert_on_suspicious_activity = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "Security Settings"
        verbose_name_plural = "Security Settings"
    
    def __str__(self):
        return f"Security Settings - Updated: {self.updated_at}"
    
    @classmethod
    def get_settings(cls):
        """Get or create security settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class SystemSettings(models.Model):
    # General Settings
    school_name = models.CharField(max_length=200, default="FACE.IT School")
    school_address = models.TextField(blank=True)
    school_phone = models.CharField(max_length=20, blank=True)
    school_email = models.EmailField(blank=True)
    academic_year = models.CharField(max_length=20, default="2024-2025")
    timezone = models.CharField(max_length=50, default="UTC")
    date_format = models.CharField(max_length=20, default="YYYY-MM-DD")
    time_format = models.CharField(max_length=10, default="24h")
    
    # Attendance Settings
    attendance_grace_period = models.IntegerField(default=15, validators=[MinValueValidator(0), MaxValueValidator(60)])
    late_threshold = models.IntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(120)])
    auto_mark_absent_after = models.IntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(24)])
    require_checkout = models.BooleanField(default=False)
    allow_manual_attendance = models.BooleanField(default=True)
    attendance_notifications = models.BooleanField(default=True)
    
    # Face Recognition Settings
    face_recognition_enabled = models.BooleanField(default=True)
    face_confidence_threshold = models.IntegerField(default=80, validators=[MinValueValidator(50), MaxValueValidator(99)])
    max_face_images_per_student = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    face_detection_timeout = models.IntegerField(default=10, validators=[MinValueValidator(5), MaxValueValidator(60)])
    auto_capture_enabled = models.BooleanField(default=False)
    face_image_quality_threshold = models.IntegerField(default=70, validators=[MinValueValidator(50), MaxValueValidator(100)])
    
    # Email Settings
    email_enabled = models.BooleanField(default=False)
    smtp_host = models.CharField(max_length=100, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=100, blank=True)
    smtp_password = models.CharField(max_length=100, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    email_from_address = models.EmailField(blank=True)
    email_from_name = models.CharField(max_length=100, default="FACE.IT System")
    
    # Notification Settings
    send_absence_notifications = models.BooleanField(default=True)
    send_late_notifications = models.BooleanField(default=True)
    send_weekly_reports = models.BooleanField(default=False)
    parent_notification_enabled = models.BooleanField(default=False)
    admin_notification_enabled = models.BooleanField(default=True)
    
    # Storage Settings
    max_file_upload_size = models.IntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    image_compression_quality = models.IntegerField(default=85, validators=[MinValueValidator(50), MaxValueValidator(100)])
    auto_backup_enabled = models.BooleanField(default=False)
    backup_frequency = models.CharField(max_length=20, default="weekly", choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ])
    backup_retention_days = models.IntegerField(default=30, validators=[MinValueValidator(7), MaxValueValidator(365)])
    storage_cleanup_enabled = models.BooleanField(default=True)
    
    # System Maintenance
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(default="System is under maintenance. Please check back later.")
    system_announcement = models.TextField(blank=True)
    debug_mode = models.BooleanField(default=False)
    log_level = models.CharField(max_length=20, default="INFO", choices=[
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ])
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
    
    def __str__(self):
        return f"System Settings - {self.school_name}"
    
    @classmethod
    def get_settings(cls):
        """Get or create system settings (singleton pattern)"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class SystemBackup(models.Model):
    filename = models.CharField(max_length=200)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField()  # in bytes
    backup_type = models.CharField(max_length=20, choices=[
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
        ('scheduled', 'Scheduled'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Backup - {self.filename}"