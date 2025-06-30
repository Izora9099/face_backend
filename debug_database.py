#!/usr/bin/env python3
"""
Quick script to check what's already in your database
Run this first to see existing data
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.models import Department, Level, Specialization, Course, AdminUser

def check_database():
    print("🔍 FACE.IT Database Status Check")
    print("=" * 50)
    
    # Check Departments
    departments = Department.objects.all()
    print(f"\n📁 Departments ({departments.count()}):")
    for dept in departments:
        print(f"  - {dept.department_name} ({dept.department_code})")
    
    # Check Levels
    levels = Level.objects.all()
    print(f"\n📊 Levels ({levels.count()}):")
    for level in levels:
        print(f"  - {level.level_name} ({level.level_code}) - Active: {level.is_active}")
    
    # Check Specializations
    specializations = Specialization.objects.all()
    print(f"\n🎯 Specializations ({specializations.count()}):")
    for spec in specializations:
        print(f"  - {spec.specialization_name} ({spec.specialization_code}) - Dept: {spec.department.department_name}")
    
    # Check Teachers
    teachers = AdminUser.objects.filter(role='teacher')
    print(f"\n👨‍🏫 Teachers ({teachers.count()}):")
    for teacher in teachers:
        dept_name = teacher.department.department_name if teacher.department else "No Department"
        spec_name = teacher.specialization.specialization_name if teacher.specialization else "No Specialization"
        print(f"  - {teacher.first_name} {teacher.last_name} ({teacher.username}) - {dept_name} / {spec_name}")
    
    # Check Courses
    courses = Course.objects.all()
    print(f"\n📚 Courses ({courses.count()}):")
    for course in courses[:10]:  # Show first 10
        print(f"  - {course.course_code}: {course.course_name} (Level {course.level.level_code})")
    if courses.count() > 10:
        print(f"  ... and {courses.count() - 10} more courses")
    
    print("\n" + "=" * 50)
    print("✅ Database check complete!")

if __name__ == "__main__":
    check_database()