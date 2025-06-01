from django.contrib import admin
from .models import Student, AttendanceRecord

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'matric_number', 'registered_on')

@admin.register(AttendanceRecord)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'timestamp', 'status')

