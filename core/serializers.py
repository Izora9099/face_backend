# core/serializers.py
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
    SecuritySettings
)
from django.contrib.auth.models import User

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
    
    class Meta:
        model = AdminUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 
                 'phone', 'role', 'permissions', 'is_active', 'is_superuser', 
                 'last_login', 'date_joined', 'taught_courses']
        read_only_fields = ['last_login', 'date_joined']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = AdminUser.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance

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
    """Serializer for creating attendance records"""
    class Meta:
        model = AttendanceRecord
        fields = ['student', 'course', 'status', 'recognition_model']
    
    def validate(self, data):
        student = data.get('student')
        course = data.get('course')
        
        # Check if student is enrolled in the course
        if course and student and not student.enrolled_courses.filter(id=course.id).exists():
            raise serializers.ValidationError(
                "Student is not enrolled in this course."
            )
        
        return data

# Backward compatibility alias
AttendanceSerializer = AttendanceRecordSerializer

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