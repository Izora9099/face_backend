# core/models.py
from django.db import models
from django_cryptography.fields import encrypt
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import json
import uuid  # This was missing - causing the error!
import numpy as np  # Needed for face recognition processing


def generate_session_id():
    """Generate a unique session ID using UUID4"""
    return str(uuid.uuid4())

# --------------------------
# Custom Admin User Model
# --------------------------
class AdminUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    
    ROLE_CHOICES = [
        ('superadmin', 'Superadmin'),
        ('staff', 'Staff'),
        ('teacher', 'Teacher'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    permissions = models.JSONField(default=list)
    
    def save(self, *args, **kwargs):
        # Auto-generate username from first and last name if not provided
        if not self.username and self.first_name and self.last_name:
            self.username = f"{self.first_name} {self.last_name}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username or f"{self.first_name} {self.last_name}"

# --------------------------
# Academic Structure Models
# --------------------------
class Department(models.Model):
    department_name = models.CharField(max_length=100)
    department_code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['department_name']
    
    def __str__(self):
        return f"{self.department_name} ({self.department_code})"

class Specialization(models.Model):
    specialization_name = models.CharField(max_length=100)
    specialization_code = models.CharField(max_length=10, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='specializations')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['specialization_name']
    
    def __str__(self):
        return f"{self.specialization_name} ({self.specialization_code})"

class Level(models.Model):
    level_name = models.CharField(max_length=50)  # e.g., "100", "200", "Year 1"
    level_code = models.CharField(max_length=10, unique=True)
    departments = models.ManyToManyField(Department, related_name='levels')
    specializations = models.ManyToManyField(Specialization, related_name='levels')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['level_name']
    
    def __str__(self):
        return f"Level {self.level_name}"

class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)
    course_name = models.CharField(max_length=200)
    credits = models.IntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    specializations = models.ManyToManyField(Specialization, related_name='courses')
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='courses')
    teachers = models.ManyToManyField(AdminUser, related_name='taught_courses', 
                                    limit_choices_to={'role': 'teacher'}, blank=True)
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['course_code']
    
    def __str__(self):
        return f"{self.course_code} - {self.course_name}"

# --------------------------
# Updated Student Model
# --------------------------
class Student(models.Model):
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    matric_number = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    
    # Legacy fields for compatibility
    student_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    student_class = models.CharField(max_length=100, blank=True)  # Deprecated, use level instead
    name = models.CharField(max_length=255, blank=True)  # Deprecated, use first_name + last_name
    
    # Academic Structure Relationships
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='students')
    specialization = models.ForeignKey(Specialization, on_delete=models.CASCADE, related_name='students')
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='students')
    enrolled_courses = models.ManyToManyField(Course, related_name='enrolled_students', blank=True)
    
    # Status and Calculated Fields
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Face Recognition Fields
    face_encoding = encrypt(models.BinaryField())
    FACE_MODEL_CHOICES = [
        ('cnn', 'CNN'),
        ('hog', 'HOG'),
        ('facenet', 'FaceNet'),
    ]
    face_encoding_model = models.CharField(max_length=10, choices=FACE_MODEL_CHOICES, default='cnn')
    
    # Timestamps
    registered_on = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['first_name', 'last_name']
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        # Update legacy name field for backward compatibility
        self.name = self.full_name
        # Set student_id if not provided
        if not self.student_id:
            self.student_id = self.matric_number
        super().save(*args, **kwargs)
    
    def auto_assign_courses(self):
        """Auto-assign courses based on department, specialization, and level"""
        courses = Course.objects.filter(
            department=self.department,
            specializations=self.specialization,
            level=self.level,
            status='active'
        )
        self.enrolled_courses.set(courses)
    
    def calculate_attendance_rate(self):
        """Calculate attendance rate for this student"""
        total_records = self.attendance_records.count()
        if total_records == 0:
            return 0.00
        
        present_records = self.attendance_records.filter(status='present').count()
        rate = (present_records / total_records) * 100
        self.attendance_rate = round(rate, 2)
        self.save(update_fields=['attendance_rate'])
        return self.attendance_rate
    
    def __str__(self):
        return f"{self.full_name} ({self.matric_number})"

# --------------------------
# Updated Attendance Record Model
# --------------------------
class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance_records')
    
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    attendance_date = models.DateField(auto_now_add=True)  # Add this field for unique constraint
    
    RECOGNITION_MODEL_CHOICES = [
        ('cnn', 'CNN'),
        ('hog', 'HOG'),
        ('facenet', 'FaceNet'),
    ]
    recognition_model = models.CharField(max_length=10, choices=RECOGNITION_MODEL_CHOICES, default='cnn')
    
    # Legacy fields for compatibility
    timestamp = models.DateTimeField(auto_now_add=True)  # Alias for check_in_time
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-check_in_time']
        unique_together = ['student', 'course', 'attendance_date']
    
    def save(self, *args, **kwargs):
        # Automatically set attendance_date from check_in_time
        if self.check_in_time and not self.attendance_date:
            self.attendance_date = self.check_in_time.date()
        elif not self.attendance_date:
            self.attendance_date = timezone.now().date()
        super().save(*args, **kwargs)
    
    @property
    def date(self):
        return self.attendance_date or self.check_in_time.date()
    
    def __str__(self):
        return f"{self.student.full_name} - {self.course.course_code} - {self.check_in_time.strftime('%Y-%m-%d %H:%M')}"

# Keep alias for backward compatibility
class Attendance(AttendanceRecord):
    class Meta:
        proxy = True

# --------------------------
# Supporting System Models (Existing)
# --------------------------

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
        ('MANAGE_DEPARTMENTS', 'Manage Departments'),
        ('MANAGE_SPECIALIZATIONS', 'Manage Specializations'),
        ('MANAGE_LEVELS', 'Manage Levels'),
        ('MANAGE_COURSES', 'Manage Courses'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    resource = models.CharField(max_length=100)
    resource_id = models.IntegerField(null=True, blank=True)
    details = models.TextField()
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
    location = models.CharField(max_length=100, blank=True)
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
    session_key = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=100, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.username} - {self.session_key[:10]}..."

class SecuritySettings(models.Model):
    """Global security configuration"""
    # Password Policy
    min_password_length = models.IntegerField(default=8, validators=[MinValueValidator(6), MaxValueValidator(20)])
    require_uppercase = models.BooleanField(default=True)
    require_lowercase = models.BooleanField(default=True)
    require_numbers = models.BooleanField(default=True)
    require_special_chars = models.BooleanField(default=False)
    password_expiry_days = models.IntegerField(default=90, validators=[MinValueValidator(30), MaxValueValidator(365)])
    
    # Session Management
    session_timeout_minutes = models.IntegerField(default=60, validators=[MinValueValidator(15), MaxValueValidator(480)])
    max_concurrent_sessions = models.IntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    
    # Login Security
    max_failed_attempts = models.IntegerField(default=5, validators=[MinValueValidator(3), MaxValueValidator(10)])
    lockout_duration_minutes = models.IntegerField(default=15, validators=[MinValueValidator(5), MaxValueValidator(120)])
    
    # Two-Factor Authentication
    enable_2fa = models.BooleanField(default=False)
    force_2fa_for_admins = models.BooleanField(default=False)
    
    # IP Restrictions
    enable_ip_whitelist = models.BooleanField(default=False)
    allowed_ip_ranges = models.TextField(blank=True, help_text="One IP/range per line")
    
    # Audit Settings
    log_all_activities = models.BooleanField(default=True)
    log_retention_days = models.IntegerField(default=90, validators=[MinValueValidator(30), MaxValueValidator(365)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "Security Settings"
        verbose_name_plural = "Security Settings"
    
    def __str__(self):
        return "Security Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create security settings (singleton pattern)"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

class SystemSettings(models.Model):
    """Global system configuration"""
    # School Information
    school_name = models.CharField(max_length=200, default="FACE.IT School")
    school_address = models.TextField(blank=True)
    school_phone = models.CharField(max_length=20, blank=True)
    school_email = models.EmailField(blank=True)
    academic_year = models.CharField(max_length=20, default="2024-2025")
    
    # Time and Localization
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
    file_size = models.BigIntegerField()
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

# --------------------------
# Signals for Auto-Assignment
# --------------------------
@receiver(post_save, sender=Student)
def auto_assign_courses_signal(sender, instance, created, **kwargs):
    """Auto-assign courses when a new student is created"""
    if created:
        instance.auto_assign_courses()

@receiver(post_save, sender=AttendanceRecord)
def update_attendance_rate_signal(sender, instance, created, **kwargs):
    """Update student attendance rate when attendance is recorded"""
    if created:
        instance.student.calculate_attendance_rate()
class AttendanceSession(models.Model):
    """Session-based attendance management for real-time attendance tracking"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Session Information - FIXED UUID default
    session_id = models.CharField(max_length=100, unique=True, default=generate_session_id)
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='attendance_sessions')
    teacher = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='attendance_sessions')
    
    # Session Timing
    start_time = models.DateTimeField(auto_now_add=True)
    expected_end_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    
    # Session Configuration
    session_duration_minutes = models.IntegerField(default=120)
    grace_period_minutes = models.IntegerField(default=15)
    
    # Session Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_auto_closed = models.BooleanField(default=False)
    
    # Room/Location Info
    room = models.CharField(max_length=100, blank=True)
    location_notes = models.TextField(blank=True)
    
    # Statistics
    total_students_expected = models.IntegerField(default=0)
    present_count = models.IntegerField(default=0)
    late_count = models.IntegerField(default=0)
    absent_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.course.course_code} ({self.status})"
    
    def save(self, *args, **kwargs):
        if not self.expected_end_time and self.start_time:
            self.expected_end_time = self.start_time + timezone.timedelta(minutes=self.session_duration_minutes)
        
        if not self.total_students_expected:
            self.total_students_expected = self.course.enrolled_students.filter(status='active').count()
        
        super().save(*args, **kwargs)
    
    def end_session(self, auto_closed=False):
        """End the attendance session"""
        self.status = 'completed'
        self.actual_end_time = timezone.now()
        self.is_auto_closed = auto_closed
        self.save()
        self.mark_remaining_as_absent()
    
    def mark_remaining_as_absent(self):
        """Mark students who haven't checked in as absent"""
        checked_in_students = self.session_checkins.values_list('student_id', flat=True)
        enrolled_students = self.course.enrolled_students.filter(status='active').exclude(id__in=checked_in_students)
        
        for student in enrolled_students:
            SessionCheckIn.objects.create(
                session=self,
                student=student,
                status='absent',
                check_in_time=self.actual_end_time or timezone.now(),
                is_auto_generated=True
            )
        
        self.update_statistics()
    
    def update_statistics(self):
        """Update session statistics"""
        checkins = self.session_checkins.all()
        self.present_count = checkins.filter(status='present').count()
        self.late_count = checkins.filter(status='present_late').count()
        self.absent_count = checkins.filter(status='absent').count()
        self.save(update_fields=['present_count', 'late_count', 'absent_count'])
    
    @property
    def should_auto_close(self):
        """Check if session should be auto-closed"""
        if self.status != 'active':
            return False
        return timezone.now() >= self.expected_end_time


class SessionCheckIn(models.Model):
    """Individual student check-ins within an attendance session"""
    
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('present_late', 'Present (Late)'),
        ('absent', 'Absent'),
    ]
    
    # Basic Information
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='session_checkins')
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='session_checkins')
    
    # Check-in Details
    check_in_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Recognition Details
    recognition_confidence = models.FloatField(null=True, blank=True)
    recognition_model = models.CharField(max_length=20, default='cnn')
    
    # Additional Fields
    is_auto_generated = models.BooleanField(default=False)  # For marking absent students
    is_manual_override = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['session', 'student']]
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['session', '-check_in_time']),
            models.Index(fields=['student', '-check_in_time']),
            models.Index(fields=['status', '-check_in_time']),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.session.session_id} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Determine status based on timing if not set
        if not self.status and not self.is_auto_generated:
            session_start = self.session.start_time
            grace_end = session_start + timezone.timedelta(minutes=self.session.grace_period_minutes)
            session_end = self.session.expected_end_time
            
            if self.check_in_time <= grace_end:
                self.status = 'present'
            elif self.check_in_time <= session_end:
                self.status = 'present_late'
            else:
                self.status = 'absent'
        
        super().save(*args, **kwargs)
        
        # Update session statistics
        self.session.update_statistics()
        
        # Create traditional attendance record for backward compatibility
        self.create_attendance_record()
    
    def create_attendance_record(self):
        """Create a traditional AttendanceRecord for backward compatibility"""
        from .models import AttendanceRecord
        
        # Map session status to traditional status
        status_mapping = {
            'present': 'present',
            'present_late': 'late',
            'absent': 'absent'
        }
        
        attendance_status = status_mapping.get(self.status, 'present')
        
        # Check if record already exists
        existing_record = AttendanceRecord.objects.filter(
            student=self.student,
            course=self.session.course,
            attendance_date=self.check_in_time.date()
        ).first()
        
        if not existing_record:
            AttendanceRecord.objects.create(
                student=self.student,
                course=self.session.course,
                status=attendance_status,
                check_in_time=self.check_in_time,
                attendance_date=self.check_in_time.date(),
                recognition_model=self.recognition_model
            )