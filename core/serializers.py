# ===================================================================
# FIXED core/serializers.py - Correct Order & Remove Duplicates
# ===================================================================

from rest_framework import serializers
from .models import (
    SystemSettings, 
    SystemBackup, 
    Student, 
    AttendanceRecord, 
    Attendance,
    AdminUser,
    Department,
    Specialization,
    Level,
    Course,
    UserActivity,
    LoginAttempt,
    ActiveSession,
    SecuritySettings,
    AttendanceSession, 
    SessionCheckIn, 
)
from django.utils import timezone
from django.contrib.auth.models import User

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import TimetableEntry, TimeSlot, Room, Course, AdminUser

# --------------------------
# Academic Structure Serializers
# --------------------------
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class SpecializationSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    
    class Meta:
        model = Specialization
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class LevelSerializer(serializers.ModelSerializer):
    department_names = serializers.StringRelatedField(source='departments', many=True, read_only=True)
    specialization_names = serializers.StringRelatedField(source='specializations', many=True, read_only=True)
    
    class Meta:
        model = Level
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    level_name = serializers.CharField(source='level.level_name', read_only=True)
    specialization_names = serializers.StringRelatedField(source='specializations', many=True, read_only=True)
    teacher_names = serializers.StringRelatedField(source='teachers', many=True, read_only=True)
    enrolled_students_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_enrolled_students_count(self, obj):
        return obj.enrolled_students.count()

class CourseListSerializer(serializers.ModelSerializer):
    """Simplified serializer for course lists"""
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    level_name = serializers.CharField(source='level.level_name', read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'course_code', 'course_name', 'credits', 'department_name', 'level_name', 'status']

# --------------------------
# Updated User and Student Serializers
# --------------------------
class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    taught_courses = CourseListSerializer(many=True, read_only=True)
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    specialization_name = serializers.CharField(source='specialization.specialization_name', read_only=True)
    
    class Meta:
        model = AdminUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name', 
            'phone', 'role', 'permissions', 'is_active', 'is_superuser', 
            'last_login', 'date_joined', 'taught_courses',
            'department', 'department_name', 'specialization', 'specialization_name', 
            'employee_id', 'job_title', 'hire_date', 'is_department_head'
        ]
        read_only_fields = ['last_login', 'date_joined', 'full_name', 'employee_id']
class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    specialization_name = serializers.CharField(source='specialization.specialization_name', read_only=True)
    level_name = serializers.CharField(source='level.level_name', read_only=True)
    enrolled_courses = CourseListSerializer(many=True, read_only=True)
    enrolled_courses_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'registered_on', 'attendance_rate', 'name', 'student_id']
        extra_kwargs = {
            'face_encoding': {'write_only': True}
        }
    
    def get_enrolled_courses_count(self, obj):
        return obj.enrolled_courses.count()

class StudentListSerializer(serializers.ModelSerializer):
    """Simplified serializer for student lists"""
    full_name = serializers.ReadOnlyField()
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    specialization_name = serializers.CharField(source='specialization.specialization_name', read_only=True)
    level_name = serializers.CharField(source='level.level_name', read_only=True)
    
    class Meta:
        model = Student
        fields = ['id', 'full_name', 'matric_number', 'email', 'department_name', 
                 'specialization_name', 'level_name', 'status', 'attendance_rate']

class StudentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating students"""
    class Meta:
        model = Student
        fields = ['first_name', 'last_name', 'matric_number', 'email', 'phone', 
                 'address', 'department', 'specialization', 'level', 'face_encoding', 
                 'face_encoding_model']
    
    def validate(self, data):
        # Ensure department, specialization, and level are compatible
        department = data.get('department')
        specialization = data.get('specialization')
        level = data.get('level')
        
        if specialization and specialization.department != department:
            raise serializers.ValidationError(
                "Specialization must belong to the selected department."
            )
        
        if level and not level.departments.filter(id=department.id).exists():
            raise serializers.ValidationError(
                "Level must be available for the selected department."
            )
        
        return data

# --------------------------
# Updated Attendance Serializers
# --------------------------
class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_matric = serializers.CharField(source='student.matric_number', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    date = serializers.ReadOnlyField()
    
    class Meta:
        model = AttendanceRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'timestamp']

class AttendanceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for attendance lists"""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_matric = serializers.CharField(source='student.matric_number', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    
    class Meta:
        model = AttendanceRecord
        fields = ['id', 'student_name', 'student_matric', 'course_code', 'status', 
                 'check_in_time', 'check_out_time', 'date']

class AttendanceCreateSerializer(serializers.ModelSerializer):
    """Enhanced serializer for creating attendance records with auto-enrollment"""
    
    class Meta:
        model = AttendanceRecord
        fields = ['student', 'course', 'status', 'notes', 'check_in_time']
    
    def validate(self, data):
        student = data.get('student')
        course = data.get('course')
        
        if student and course:
            # Check if student is enrolled in the course
            if not course.enrolled_students.filter(id=student.id).exists():
                # Auto-enroll the student
                course.enrolled_students.add(student)
                print(f"✅ Auto-enrolled student {student.full_name} in course {course.course_name}")
        
        return data

# Backward compatibility alias
AttendanceSerializer = AttendanceRecordSerializer

# --------------------------
# Session Serializers (CORRECT ORDER)
# --------------------------

# Define AttendanceSessionSerializer FIRST
class AttendanceSessionSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    attendance_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'session_id', 'course', 'course_name', 'course_code',
            'teacher', 'teacher_name', 'start_time', 'expected_end_time',
            'actual_end_time', 'session_duration_minutes', 'grace_period_minutes',
            'status', 'room', 'total_students_expected', 'present_count',
            'late_count', 'absent_count', 'attendance_rate', 'created_at'
        ]
        read_only_fields = [
            'id', 'session_id', 'start_time', 'present_count',
            'late_count', 'absent_count', 'created_at'
        ]
    
    def get_attendance_rate(self, obj):
        if obj.total_students_expected > 0:
            return round((obj.present_count + obj.late_count) / obj.total_students_expected * 100, 2)
        return 0.0


class SessionCheckInSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_matric = serializers.CharField(source='student.matric_number', read_only=True)
    
    class Meta:
        model = SessionCheckIn
        fields = [
            'id', 'student', 'student_name', 'student_matric',
            'check_in_time', 'status', 'recognition_confidence',
            'is_manual_override', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'check_in_time', 'created_at']


class SessionStatsSerializer(serializers.ModelSerializer):
    recent_checkins = SessionCheckInSerializer(source='session_checkins', many=True, read_only=True)
    attendance_rate = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceSession  # FIXED: Was SessionCheckIn, should be AttendanceSession
        fields = [
            'id', 'session_id', 'status', 'total_students_expected',
            'present_count', 'late_count', 'absent_count',
            'attendance_rate', 'time_remaining', 'recent_checkins'
        ]
    
    def get_attendance_rate(self, obj):
        if obj.total_students_expected > 0:
            return round((obj.present_count + obj.late_count) / obj.total_students_expected * 100, 2)
        return 0.0
    
    def get_time_remaining(self, obj):
        if obj.status == 'active':
            remaining = (obj.expected_end_time - timezone.now()).total_seconds()
            return max(0, int(remaining))
        return 0


# Response models for Android app (NOW AttendanceSessionSerializer is defined)
class SessionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    session_id = serializers.CharField(required=False)
    session = AttendanceSessionSerializer(required=False)  # This now works!


class AttendanceResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    student_name = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    check_in_time = serializers.DateTimeField(required=False)


# --------------------------
# System Management Serializers
# --------------------------
class UserActivitySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserActivity
        fields = '__all__'

class LoginAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAttempt
        fields = '__all__'

class ActiveSessionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = ActiveSession
        fields = '__all__'

class SecuritySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecuritySettings
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'updated_by']

class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        exclude = ['created_at', 'updated_at', 'updated_by']
    
    def validate_smtp_password(self, value):
        """Don't return the actual password for security"""
        if value:
            return '***HIDDEN***'
        return value

class SystemSettingsUpdateSerializer(serializers.ModelSerializer):
    """Separate serializer for updates to handle password properly"""
    class Meta:
        model = SystemSettings
        exclude = ['created_at', 'updated_at', 'updated_by']
    
    def update(self, instance, validated_data):
        # Handle password field specially
        if 'smtp_password' in validated_data:
            password = validated_data['smtp_password']
            if password != '***HIDDEN***':  # Only update if not the hidden placeholder
                instance.smtp_password = password
            validated_data.pop('smtp_password')
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

class SystemStatsSerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    total_departments = serializers.IntegerField()
    total_specializations = serializers.IntegerField()
    total_levels = serializers.IntegerField()
    database_size = serializers.CharField()
    storage_used = serializers.CharField()
    system_uptime = serializers.CharField()
    last_backup = serializers.CharField()
    system_version = serializers.CharField()

class SystemBackupSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = SystemBackup
        fields = ['id', 'filename', 'file_size', 'file_size_mb', 'backup_type', 
                 'created_at', 'created_by', 'created_by_name']
    
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)

# --------------------------
# Dashboard and Analytics Serializers
# --------------------------
class DepartmentStatsSerializer(serializers.Serializer):
    department_name = serializers.CharField()
    total_students = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    total_specializations = serializers.IntegerField()
    average_attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

class CourseStatsSerializer(serializers.Serializer):
    course_code = serializers.CharField()
    course_name = serializers.CharField()
    enrolled_students = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()
    average_attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

class TeacherStatsSerializer(serializers.Serializer):
    teacher_name = serializers.CharField()
    total_courses = serializers.IntegerField()
    total_students = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()

# --------------------------
# Enrollment Management Serializers
# --------------------------
class StudentEnrollmentSerializer(serializers.Serializer):
    """For managing student course enrollments"""
    student_id = serializers.IntegerField()
    course_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True
    )
    
    def validate_student_id(self, value):
        if not Student.objects.filter(id=value).exists():
            raise serializers.ValidationError("Student not found.")
        return value
    
    def validate_course_ids(self, value):
        existing_courses = Course.objects.filter(id__in=value, status='active')
        if len(existing_courses) != len(value):
            raise serializers.ValidationError("One or more courses not found or inactive.")
        return value

class BulkEnrollmentSerializer(serializers.Serializer):
    """For bulk enrollment operations"""
    department_id = serializers.IntegerField(required=False)
    specialization_id = serializers.IntegerField(required=False)
    level_id = serializers.IntegerField(required=False)
    course_ids = serializers.ListField(child=serializers.IntegerField())
    
    def validate(self, data):
        if not any([data.get('department_id'), data.get('specialization_id'), data.get('level_id')]):
            raise serializers.ValidationError(
                "At least one of department, specialization, or level must be specified."
            )
        return data
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer that includes user data in the token payload"""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims with user data
        token['username'] = user.username
        token['email'] = user.email
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        token['phone'] = getattr(user, 'phone', '')
        token['role'] = getattr(user, 'role', 'staff')
        token['permissions'] = getattr(user, 'permissions', [])
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        token['is_active'] = user.is_active
        token['last_login'] = user.last_login.isoformat() if user.last_login else ''
        token['date_joined'] = user.date_joined.isoformat() if user.date_joined else ''
        
        return token

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT view that uses our custom serializer"""
    serializer_class = CustomTokenObtainPairSerializer

class TimeSlotSerializer(serializers.ModelSerializer):
    day_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeSlot
        fields = ['id', 'day_of_week', 'day_name', 'start_time', 'end_time', 'duration_minutes']
    
    def get_day_name(self, obj):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[obj.day_of_week]

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity', 'building', 'floor', 'equipment', 'is_available']

class TeacherBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminUser
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

class CourseBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'course_code', 'course_name', 'credits', 'level', 'department']

class TimetableEntrySerializer(serializers.ModelSerializer):
    course = CourseBasicSerializer(read_only=True)
    teacher = TeacherBasicSerializer(read_only=True)
    time_slot = TimeSlotSerializer(read_only=True)
    room = RoomSerializer(read_only=True)
    
    # For creating/updating
    course_id = serializers.IntegerField(write_only=True)
    teacher_id = serializers.IntegerField(write_only=True)
    time_slot_id = serializers.IntegerField(write_only=True)
    room_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'course', 'teacher', 'time_slot', 'room',
            'academic_year', 'semester', 'is_active', 'notes',
            'created_at', 'updated_at',
            'course_id', 'teacher_id', 'time_slot_id', 'room_id'
        ]
    
    def create(self, validated_data):
        # Convert IDs to actual objects
        course = Course.objects.get(id=validated_data.pop('course_id'))
        teacher = AdminUser.objects.get(id=validated_data.pop('teacher_id'))
        time_slot = TimeSlot.objects.get(id=validated_data.pop('time_slot_id'))
        room = Room.objects.get(id=validated_data.pop('room_id'))
        
        return TimetableEntry.objects.create(
            course=course,
            teacher=teacher,
            time_slot=time_slot,
            room=room,
            **validated_data
        )