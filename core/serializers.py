# core/serializers.py
from rest_framework import serializers
from .models import (
    SystemSettings, 
    SystemBackup, 
    Student, 
    AttendanceRecord, 
    Attendance,
    AdminUser
)
from django.contrib.auth.models import User

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
    database_size = serializers.CharField()
    storage_used = serializers.CharField()
    system_uptime = serializers.CharField()
    last_backup = serializers.CharField()
    system_version = serializers.CharField()

class SystemBackupSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemBackup
        fields = ['id', 'filename', 'file_size', 'file_size_mb', 'backup_type', 'created_at', 'created_by']
    
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__'

class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    
    class Meta:
        model = AttendanceRecord
        fields = '__all__'