#!/usr/bin/env python3
"""
Django script to create 5 sample students
Run this in your Django project directory with: python manage.py shell < create_students.py
"""

import os
import sys
import django
from datetime import date, datetime
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.models import Student, Department, Level, Specialization

def create_sample_students():
    """Create 5 sample students with realistic data"""
    
    print("🔄 Creating sample students...")
    
    # Get or create departments and levels
    try:
        # Create/get departments
        comp_sci = Department.objects.get_or_create(
            department_name="Computer Science",
            defaults={
                'department_code': 'CS',
                'description': 'Department of Computer Science and Information Technology'
            }
        )[0]
        
        engineering = Department.objects.get_or_create(
            department_name="Engineering",
            defaults={
                'department_code': 'ENG', 
                'description': 'Faculty of Engineering'
            }
        )[0]
        
        # Create/get levels
        level_100 = Level.objects.get_or_create(
            level_name="Level 100",
            defaults={
                'level_code': '100',
                'description': 'First Year'
            }
        )[0]
        
        level_200 = Level.objects.get_or_create(
            level_name="Level 200", 
            defaults={
                'level_code': '200',
                'description': 'Second Year'
            }
        )[0]
        
        level_300 = Level.objects.get_or_create(
            level_name="Level 300",
            defaults={
                'level_code': '300', 
                'description': 'Third Year'
            }
        )[0]
        
        # Create/get specializations
        software_eng = Specialization.objects.get_or_create(
            specialization_name="Software Engineering",
            defaults={
                'specialization_code': 'SE',
                'description': 'Software Engineering Specialization',
                'department': comp_sci
            }
        )[0]
        
        print(f"✅ Academic structure ready")
        
    except Exception as e:
        print(f"❌ Error setting up academic structure: {e}")
        return
    
    # Sample student data
    students_data = [
        {
            'first_name': 'John',
            'last_name': 'Doe',
            'matric_number': 'CS2024001',
            'email': 'john.doe@student.edu',
            'phone': '+237650123456',
            'address': 'Buea, Southwest Region, Cameroon',
            'date_of_birth': date(2002, 5, 15),
            'gender': 'Male',
            'emergency_contact': 'Jane Doe (Mother)',
            'emergency_phone': '+237650654321',
            'department': comp_sci,
            'level': level_200,
            'specialization': software_eng,
            'status': 'active'
        },
        {
            'first_name': 'Sarah',
            'last_name': 'Johnson',
            'matric_number': 'CS2024002', 
            'email': 'sarah.johnson@student.edu',
            'phone': '+237651234567',
            'address': 'Douala, Littoral Region, Cameroon',
            'date_of_birth': date(2003, 8, 22),
            'gender': 'Female',
            'emergency_contact': 'Robert Johnson (Father)',
            'emergency_phone': '+237651765432',
            'department': comp_sci,
            'level': level_100,
            'specialization': None,  # First year, no specialization yet
            'status': 'active'
        },
        {
            'first_name': 'Michael',
            'last_name': 'Brown',
            'matric_number': 'ENG2024003',
            'email': 'michael.brown@student.edu', 
            'phone': '+237652345678',
            'address': 'Yaounde, Centre Region, Cameroon',
            'date_of_birth': date(2001, 12, 10),
            'gender': 'Male',
            'emergency_contact': 'Lisa Brown (Mother)',
            'emergency_phone': '+237652876543',
            'department': engineering,
            'level': level_300,
            'specialization': None,
            'status': 'active'
        },
        {
            'first_name': 'Emily',
            'last_name': 'Davis',
            'matric_number': 'CS2024004',
            'email': 'emily.davis@student.edu',
            'phone': '+237653456789',
            'address': 'Bamenda, Northwest Region, Cameroon', 
            'date_of_birth': date(2002, 3, 7),
            'gender': 'Female',
            'emergency_contact': 'David Davis (Father)',
            'emergency_phone': '+237653987654',
            'department': comp_sci,
            'level': level_200,
            'specialization': software_eng,
            'status': 'active'
        },
        {
            'first_name': 'James',
            'last_name': 'Wilson',
            'matric_number': 'CS2024005',
            'email': 'james.wilson@student.edu',
            'phone': '+237654567890',
            'address': 'Limbe, Southwest Region, Cameroon',
            'date_of_birth': date(2003, 1, 28),
            'gender': 'Male',
            'emergency_contact': 'Mary Wilson (Mother)', 
            'emergency_phone': '+237654098765',
            'department': comp_sci,
            'level': level_100,
            'specialization': None,
            'status': 'active'
        }
    ]
    
    created_students = []
    
    for student_data in students_data:
        try:
            # Check if student already exists
            if Student.objects.filter(matric_number=student_data['matric_number']).exists():
                print(f"⚠️  Student {student_data['matric_number']} already exists, skipping...")
                continue
                
            if Student.objects.filter(email=student_data['email']).exists():
                print(f"⚠️  Email {student_data['email']} already exists, skipping...")
                continue
            
            # Create the student
            student = Student.objects.create(**student_data)
            created_students.append(student)
            
            print(f"✅ Created student: {student.first_name} {student.last_name} ({student.matric_number})")
            
        except Exception as e:
            print(f"❌ Failed to create student {student_data['first_name']} {student_data['last_name']}: {e}")
    
    print(f"\n🎉 Successfully created {len(created_students)} students!")
    
    # Display summary
    if created_students:
        print("\n📋 Created Students Summary:")
        print("-" * 60)
        for student in created_students:
            print(f"Name: {student.first_name} {student.last_name}")
            print(f"Matric: {student.matric_number}")
            print(f"Email: {student.email}")
            print(f"Department: {student.department.department_name}")
            print(f"Level: {student.level.level_name}")
            print(f"Status: {student.status}")
            print("-" * 60)

if __name__ == "__main__":
    create_sample_students()