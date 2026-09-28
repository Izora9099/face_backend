from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    ActiveSession, AdminUser, AttendanceRecord, AttendanceSession, Course,
    Department, Level, LoginAttempt, Room, SecuritySettings, SessionCheckIn,
    Specialization, Student, SystemBackup, SystemSettings, TimeSlot,
    TimetableEntry, UserActivity,
)
from .permissions import user_role

ATTENDANCE_STATUS_CHOICES = AttendanceRecord.STATUS_CHOICES
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

ROLE_PERMISSIONS = {
    'superadmin': [
        'view_students', 'manage_students', 'enroll_students',
        'view_attendance', 'edit_attendance', 'start_sessions',
        'view_reports', 'generate_reports', 'system_reports',
        'view_users', 'manage_users', 'system_settings',
        'view_timetable', 'manage_timetable',
    ],
    'teacher': [
        'view_student_roster', 'view_attendance', 'edit_attendance',
        'start_sessions', 'view_reports', 'generate_reports', 'view_timetable',
    ],
    'staff': [
        'view_students', 'manage_students', 'enroll_students',
        'view_attendance', 'view_reports', 'view_timetable', 'manage_timetable',
    ],
}


# --------------------------
# Auth
# --------------------------
class CurrentUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source='department.department_name', read_only=True, default=None)

    class Meta:
        model = AdminUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'role', 'permissions', 'is_superuser', 'is_active',
            'department', 'department_name', 'employee_id', 'job_title',
            'last_login', 'date_joined',
        ]
        read_only_fields = fields

    def get_role(self, obj) -> str:
        return user_role(obj)

    def get_permissions(self, obj) -> list[str]:
        return ROLE_PERMISSIONS.get(user_role(obj), [])


class LoginSerializer(TokenObtainPairSerializer):
    """JWT pair plus the user profile, so the client needs one round-trip."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = CurrentUserSerializer(self.user).data
        return data


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = CurrentUserSerializer()


class AdminUserSerializer(serializers.ModelSerializer):
    """Shape used by the admin-users screens."""
    name = serializers.SerializerMethodField()
    department_id = serializers.IntegerField(source='department.id', read_only=True, default=None)
    department = serializers.CharField(source='department.department_name', read_only=True, default=None)
    specialization_id = serializers.IntegerField(source='specialization.id', read_only=True, default=None)
    specialization = serializers.CharField(
        source='specialization.specialization_name', read_only=True, default=None)
    status = serializers.SerializerMethodField()

    class Meta:
        model = AdminUser
        fields = [
            'id', 'name', 'username', 'first_name', 'last_name', 'email', 'phone',
            'role', 'employee_id', 'department_id', 'department',
            'specialization_id', 'specialization', 'job_title', 'status',
            'is_active', 'last_login', 'date_joined',
        ]
        read_only_fields = fields

    def get_name(self, obj) -> str:
        return obj.full_name or obj.username

    def get_status(self, obj) -> str:
        return 'Active' if obj.is_active else 'Inactive'


class AdminUserWriteSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=AdminUser.ROLE_CHOICES, required=False)
    password = serializers.CharField(required=False, write_only=True, min_length=8)
    employee_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    specialization_id = serializers.IntegerField(required=False, allow_null=True)
    job_title = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        # Accept the legacy display roles the old UI sent ("Super Admin", "Teacher").
        if hasattr(data, 'copy'):
            data = data.copy()
        if isinstance(data.get('role'), str):
            data['role'] = data['role'].lower().replace(' ', '')
        return super().to_internal_value(data)


# --------------------------
# Academic structure
# --------------------------
class DepartmentSerializer(serializers.ModelSerializer):
    teachers_count = serializers.IntegerField(read_only=True)
    students_count = serializers.IntegerField(read_only=True)
    courses_count = serializers.IntegerField(read_only=True)

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
        extra_kwargs = {
            'departments': {'required': False},
            'specializations': {'required': False},
        }


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
        extra_kwargs = {
            'specializations': {'required': False},
            'teachers': {'required': False},
        }

    def get_enrolled_students_count(self, obj) -> int:
        return obj.enrolled_students.count()


class CourseListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    level_name = serializers.CharField(source='level.level_name', read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'course_code', 'course_name', 'credits', 'department_name', 'level_name', 'status']


# --------------------------
# Students
# --------------------------
class _StudentFaceMixin(serializers.Serializer):
    face_enrolled = serializers.SerializerMethodField()

    def get_face_enrolled(self, obj) -> bool:
        # Only reports presence; the encoding itself never leaves the server.
        return bool(obj.face_images_count)


class StudentSerializer(_StudentFaceMixin, serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    specialization_name = serializers.CharField(
        source='specialization.specialization_name', read_only=True, default=None)
    level_name = serializers.CharField(source='level.level_name', read_only=True)
    enrolled_courses = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    enrolled_courses_detail = CourseListSerializer(source='enrolled_courses', many=True, read_only=True)
    enrolled_courses_count = serializers.SerializerMethodField()

    class Meta:
        model = Student
        exclude = ['face_encoding']
        read_only_fields = [
            'created_at', 'updated_at', 'registered_on', 'attendance_rate', 'name',
            'student_id', 'face_encoding_model', 'face_images_count', 'last_attendance',
        ]

    def get_enrolled_courses_count(self, obj) -> int:
        return obj.enrolled_courses.count()

    def validate(self, data):
        department = data.get('department', getattr(self.instance, 'department', None))
        specialization = data.get('specialization', getattr(self.instance, 'specialization', None))
        level = data.get('level', getattr(self.instance, 'level', None))
        if specialization and department and specialization.department_id != department.id:
            raise serializers.ValidationError(
                {'specialization': 'Specialization must belong to the selected department.'})
        if level and department and not level.departments.filter(id=department.id).exists():
            raise serializers.ValidationError(
                {'level': 'Level must be available for the selected department.'})
        return data


class StudentListSerializer(_StudentFaceMixin, serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    specialization_name = serializers.CharField(
        source='specialization.specialization_name', read_only=True, default=None)
    level_name = serializers.CharField(source='level.level_name', read_only=True)
    enrolled_courses = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'matric_number', 'email', 'phone',
            'department', 'department_name', 'specialization', 'specialization_name',
            'level', 'level_name', 'status', 'attendance_rate', 'enrolled_courses',
            'face_enrolled', 'face_images_count', 'last_attendance', 'created_at',
        ]


# Kept for imports elsewhere; creation uses the full serializer.
StudentCreateSerializer = StudentSerializer


class StudentEnrollmentSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    course_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    def validate_student_id(self, value):
        if not Student.objects.filter(id=value).exists():
            raise serializers.ValidationError('Student not found.')
        return value

    def validate_course_ids(self, value):
        if Course.objects.filter(id__in=value, status='active').count() != len(set(value)):
            raise serializers.ValidationError('One or more courses not found or inactive.')
        return value


class BulkEnrollmentSerializer(serializers.Serializer):
    department_id = serializers.IntegerField(required=False)
    specialization_id = serializers.IntegerField(required=False)
    level_id = serializers.IntegerField(required=False)
    course_ids = serializers.ListField(child=serializers.IntegerField())

    def validate(self, data):
        if not any([data.get('department_id'), data.get('specialization_id'), data.get('level_id')]):
            raise serializers.ValidationError(
                'At least one of department, specialization, or level must be specified.')
        return data


class IdListSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    course_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


# --------------------------
# Attendance
# --------------------------
class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_matric = serializers.CharField(source='student.matric_number', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    date = serializers.DateField(read_only=True)
    status = serializers.ChoiceField(choices=ATTENDANCE_STATUS_CHOICES)

    class Meta:
        model = AttendanceRecord
        fields = '__all__'
        read_only_fields = [
            'created_at', 'updated_at', 'timestamp', 'attendance_date',
            'recognition_confidence', 'recognition_model',
        ]


class AttendanceListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_matric = serializers.CharField(source='student.matric_number', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    date = serializers.DateField(read_only=True)
    status = serializers.ChoiceField(choices=ATTENDANCE_STATUS_CHOICES, read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'student', 'student_name', 'student_matric', 'course', 'course_code',
            'course_name', 'status', 'check_in_time', 'check_out_time', 'date',
            'recognition_confidence', 'notes',
        ]


class AttendanceCreateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=ATTENDANCE_STATUS_CHOICES, default='present')

    class Meta:
        model = AttendanceRecord
        fields = ['student', 'course', 'status', 'notes']

    def validate(self, data):
        today = timezone.localdate()
        if AttendanceRecord.objects.filter(
                student=data['student'], course=data['course'], attendance_date=today).exists():
            raise serializers.ValidationError(
                'Attendance for this student and course is already recorded today; update it instead.')
        return data

    def create(self, validated_data):
        student, course = validated_data['student'], validated_data['course']
        # Manual marking implies enrolment (matches previous behaviour).
        course.enrolled_students.add(student)
        return super().create(validated_data)


AttendanceSerializer = AttendanceRecordSerializer


# --------------------------
# Sessions (Android contract)
# --------------------------
class AttendanceSessionSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'session_id', 'course', 'course_name', 'course_code',
            'teacher', 'teacher_name', 'start_time', 'expected_end_time',
            'actual_end_time', 'session_duration_minutes', 'grace_period_minutes',
            'status', 'room', 'total_students_expected', 'present_count',
            'late_count', 'absent_count', 'attendance_rate', 'created_at',
        ]
        read_only_fields = fields


class SessionCheckInSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_matric = serializers.CharField(source='student.matric_number', read_only=True)

    class Meta:
        model = SessionCheckIn
        fields = [
            'id', 'student', 'student_name', 'student_matric',
            'check_in_time', 'status', 'recognition_confidence',
            'is_manual_override', 'notes', 'created_at',
        ]
        read_only_fields = fields


class SessionStatsSerializer(serializers.ModelSerializer):
    recent_checkins = SessionCheckInSerializer(source='session_checkins', many=True, read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)
    time_remaining = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'session_id', 'status', 'total_students_expected',
            'present_count', 'late_count', 'absent_count',
            'attendance_rate', 'time_remaining', 'recent_checkins',
        ]

    def get_time_remaining(self, obj) -> int:
        if obj.status == 'active' and obj.expected_end_time:
            return max(0, int((obj.expected_end_time - timezone.now()).total_seconds()))
        return 0


class SessionStartRequestSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    duration_minutes = serializers.IntegerField(required=False, default=120, min_value=5, max_value=600)
    grace_period_minutes = serializers.IntegerField(required=False, default=15, min_value=0, max_value=120)
    room = serializers.CharField(required=False, allow_blank=True, default='')


class SessionEndRequestSerializer(serializers.Serializer):
    session_id = serializers.CharField()


class SessionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    session_id = serializers.CharField(required=False)
    session = AttendanceSessionSerializer(required=False)


class SessionStatsResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    stats = SessionStatsSerializer()


class CheckInRequestSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    image = serializers.ImageField()


class CheckInResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    student_id = serializers.IntegerField(required=False)
    student_name = serializers.CharField(required=False)
    matric_number = serializers.CharField(required=False)
    status = serializers.ChoiceField(choices=SessionCheckIn.STATUS_CHOICES, required=False)
    check_in_time = serializers.DateTimeField(required=False)
    confidence = serializers.FloatField(required=False)
    distance = serializers.FloatField(required=False, allow_null=True)
    threshold = serializers.FloatField(required=False)


class ManualMarkRequestSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=SessionCheckIn.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# --------------------------
# Recognition
# --------------------------
class RegisterStudentRequestSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    matric_number = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    department_id = serializers.IntegerField()
    specialization_id = serializers.IntegerField()
    level_id = serializers.IntegerField()
    image = serializers.ImageField()


class EnrollFaceRequestSerializer(serializers.Serializer):
    image = serializers.ImageField()


class RecognizeRequestSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    image = serializers.ImageField()


class RecognizedStudentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    matric_number = serializers.CharField()
    department = serializers.CharField()
    course = serializers.CharField()
    confidence = serializers.FloatField()
    attendance_rate = serializers.FloatField(required=False)
    existing_status = serializers.CharField(required=False)


RECOGNITION_STATUSES = [('success', 'Success'), ('info', 'Info'), ('fail', 'Fail')]


class RecognitionResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RECOGNITION_STATUSES)
    message = serializers.CharField()
    confidence = serializers.FloatField(required=False)
    distance = serializers.FloatField(required=False, allow_null=True)
    threshold = serializers.FloatField(required=False)
    student = RecognizedStudentSerializer(required=False)


# --------------------------
# Security / system
# --------------------------
class UserActivitySerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = UserActivity
        fields = ['id', 'user', 'user_full_name', 'user_role', 'action', 'resource', 'resource_id',
                  'details', 'ip_address', 'status', 'timestamp']

    def get_user_role(self, obj) -> str:
        return user_role(obj.user)


class LoginAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAttempt
        fields = ['id', 'username', 'success', 'ip_address', 'user_agent', 'failure_reason', 'timestamp']


class ActiveSessionSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ActiveSession
        fields = ['id', 'user', 'session_key', 'ip_address', 'user_agent', 'location',
                  'last_activity', 'created_at', 'is_active']


class SecuritySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecuritySettings
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'updated_by']


class SecurityStatisticsSerializer(serializers.Serializer):
    total_activities = serializers.IntegerField()
    failed_activities = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_login_attempts = serializers.IntegerField()
    successful_logins = serializers.IntegerField()
    failed_logins = serializers.IntegerField()
    unique_users = serializers.IntegerField()
    suspicious_activities = serializers.IntegerField()
    active_sessions = serializers.IntegerField()


SMTP_PASSWORD_MASK = '***HIDDEN***'


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        exclude = ['updated_by']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {'smtp_password': {'required': False}}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('smtp_password'):
            data['smtp_password'] = SMTP_PASSWORD_MASK
        return data

    def update(self, instance, validated_data):
        # The UI echoes the mask back; don't overwrite the real password with it.
        if validated_data.get('smtp_password') == SMTP_PASSWORD_MASK:
            validated_data.pop('smtp_password')
        return super().update(instance, validated_data)


SystemSettingsUpdateSerializer = SystemSettingsSerializer


class SystemBackupSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default=None)

    class Meta:
        model = SystemBackup
        fields = ['id', 'filename', 'file_size', 'file_size_mb', 'backup_type',
                  'created_at', 'created_by', 'created_by_name']

    def get_file_size_mb(self, obj) -> float:
        return round(obj.file_size / (1024 * 1024), 2)


class SystemStatsSerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    total_departments = serializers.IntegerField()
    total_specializations = serializers.IntegerField()
    total_levels = serializers.IntegerField()
    enrolled_faces = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    database_size = serializers.CharField()
    storage_used = serializers.CharField()
    cpu_usage = serializers.FloatField()
    memory_usage = serializers.FloatField()
    disk_usage = serializers.FloatField()
    system_uptime = serializers.CharField()
    last_backup = serializers.CharField()
    system_version = serializers.CharField()
    face_engine = serializers.CharField()
    face_match_threshold = serializers.FloatField()


class DashboardStatsSerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    total_departments = serializers.IntegerField()
    total_specializations = serializers.IntegerField()
    total_levels = serializers.IntegerField()
    total_teachers = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()
    todays_attendance_count = serializers.IntegerField()
    todays_attendance_rate = serializers.FloatField()
    weekly_attendance_trend = serializers.ListField(child=serializers.DictField())
    recent_activities = UserActivitySerializer(many=True)


class DepartmentStatsSerializer(serializers.Serializer):
    department_name = serializers.CharField()
    total_students = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    total_specializations = serializers.IntegerField()
    average_attendance_rate = serializers.FloatField()


class CourseStatsSerializer(serializers.Serializer):
    course_code = serializers.CharField()
    course_name = serializers.CharField()
    enrolled_students = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()
    average_attendance_rate = serializers.FloatField()


class TeacherStatsSerializer(serializers.Serializer):
    teacher_name = serializers.CharField()
    total_courses = serializers.IntegerField()
    total_students = serializers.IntegerField()
    total_attendance_records = serializers.IntegerField()


# --------------------------
# Timetable
# --------------------------
class TimeSlotSerializer(serializers.ModelSerializer):
    day_name = serializers.SerializerMethodField()

    class Meta:
        model = TimeSlot
        fields = ['id', 'day_of_week', 'day_name', 'start_time', 'end_time', 'duration_minutes']

    def get_day_name(self, obj) -> str:
        return DAY_NAMES[obj.day_of_week]


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity', 'building', 'floor', 'equipment', 'is_available']


class TeacherBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = AdminUser
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email']

    def get_full_name(self, obj) -> str:
        return obj.full_name or obj.username


class CourseBasicSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    level_name = serializers.CharField(source='level.level_name', read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'course_code', 'course_name', 'credits', 'level', 'level_name',
                  'department', 'department_name']


class TimetableEntrySerializer(serializers.ModelSerializer):
    course = CourseBasicSerializer(read_only=True)
    teacher = TeacherBasicSerializer(read_only=True)
    time_slot = TimeSlotSerializer(read_only=True)
    room = RoomSerializer(read_only=True)

    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(), source='course', write_only=True)
    teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=AdminUser.objects.filter(role='teacher'), source='teacher', write_only=True)
    time_slot_id = serializers.PrimaryKeyRelatedField(
        queryset=TimeSlot.objects.all(), source='time_slot', write_only=True)
    room_id = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(), source='room', write_only=True)

    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'course', 'teacher', 'time_slot', 'room',
            'academic_year', 'semester', 'is_active', 'notes',
            'created_at', 'updated_at',
            'course_id', 'teacher_id', 'time_slot_id', 'room_id',
        ]
        read_only_fields = ['created_at', 'updated_at']
