#!/usr/bin/env python3
"""
FACE.IT Timetable Generator Script (Fixed for Existing Database)
Generates comprehensive timetable data working with your existing structure

Usage:
    1. Place this script in your Django project root directory
    2. Run: python populate_timetable.py
"""

import os
import sys
import django
from datetime import datetime, timedelta, time, date
from django.utils import timezone
import random

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.models import (
    Department, Level, Specialization, Course, AdminUser, 
    TimeSlot, Room, TimetableEntry, Student
)

class TimetableGenerator:
    def __init__(self):
        self.academic_year = "2024-2025"
        self.semester = 2  # Second semester
        
        # Institution details
        self.institution_name = "FACE.IT Engineering & Technology Institute"
        
        # Working with your existing departments
        self.department_mappings = {
            'MECH': 'Mechanical Engineering',  # Use existing ME department
            'CIVIL': 'Civil Engineering and Architecture',  # Use existing 
            'ELEC': 'Electrical Engineering',  # Use existing EE
            'COMP': 'Computer Engineering',  # Use existing CE
            'CS': 'Computer Science'  # Use existing CS
        }
        
        # Working with existing levels (you have both L200/L300 and 200/300 formats)
        self.level_mappings = {
            '200': ['200', 'L200'],
            '300': ['300', 'L300'], 
            '400': ['400', 'L400'],
            '500': ['500', 'L500']
        }
        
        self.active_levels = ['200', '300', '400']  # 500 has no timetable
        
        # Halls configuration
        self.halls_config = [
            {'name': 'BGFL', 'capacity': 100, 'building': 'Main Building'},
            {'name': 'Hall 1', 'capacity': 80, 'building': 'Academic Block A'},
            {'name': 'Hall 2', 'capacity': 80, 'building': 'Academic Block B'}
        ]
        
        # Time slots (7:00 AM to 7:00 PM, 2-hour classes, 5 slots per day)
        self.time_slots_config = [
            {'start': time(7, 0), 'end': time(9, 0)},    # 7:00-9:00 AM
            {'start': time(9, 30), 'end': time(11, 30)}, # 9:30-11:30 AM
            {'start': time(12, 0), 'end': time(14, 0)},  # 12:00-2:00 PM
            {'start': time(14, 30), 'end': time(16, 30)}, # 2:30-4:30 PM
            {'start': time(17, 0), 'end': time(19, 0)},   # 5:00-7:00 PM
        ]
        
        # Working days (0=Monday, 4=Friday)
        self.working_days = [0, 1, 2, 3, 4]  # Monday to Friday
        
        # Course templates by department and level
        self.course_templates = self._generate_course_templates()
        
    def _generate_course_templates(self):
        """Generate realistic course templates for each department and level"""
        templates = {}
        
        # Mechanical Engineering
        templates['MECH'] = {
            '200': [
                {'code': 'MECH201', 'name': 'Engineering Mechanics', 'credits': 3},
                {'code': 'MECH202', 'name': 'Thermodynamics I', 'credits': 3},
                {'code': 'MECH203', 'name': 'Materials Science', 'credits': 3},
                {'code': 'MECH204', 'name': 'Manufacturing Processes', 'credits': 4},
                {'code': 'MECH205', 'name': 'Engineering Drawing II', 'credits': 2}
            ],
            '300': [
                {'code': 'MECH301', 'name': 'Fluid Mechanics', 'credits': 3},
                {'code': 'MECH302', 'name': 'Heat Transfer', 'credits': 3},
                {'code': 'MECH303', 'name': 'Machine Design I', 'credits': 4},
                {'code': 'MECH304', 'name': 'Dynamics of Machinery', 'credits': 3},
                {'code': 'MECH305', 'name': 'Control Systems', 'credits': 3}
            ],
            '400': [
                {'code': 'MECH401', 'name': 'Advanced Thermodynamics', 'credits': 3},
                {'code': 'MECH402', 'name': 'Machine Design II', 'credits': 4},
                {'code': 'MECH403', 'name': 'Automobile Engineering', 'credits': 3},
                {'code': 'MECH404', 'name': 'Refrigeration & AC', 'credits': 3}
            ]
        }
        
        # Civil Engineering and Architecture
        templates['CIVIL'] = {
            '200': [
                {'code': 'CIVIL201', 'name': 'Structural Analysis I', 'credits': 3},
                {'code': 'CIVIL202', 'name': 'Concrete Technology', 'credits': 3},
                {'code': 'CIVIL203', 'name': 'Surveying II', 'credits': 4},
                {'code': 'ARCH201', 'name': 'Architectural Design I', 'credits': 4},
                {'code': 'CIVIL204', 'name': 'Building Construction', 'credits': 3}
            ],
            '300': [
                {'code': 'CIVIL301', 'name': 'Structural Analysis II', 'credits': 3},
                {'code': 'CIVIL302', 'name': 'Geotechnical Engineering', 'credits': 3},
                {'code': 'CIVIL303', 'name': 'Transportation Engineering', 'credits': 3},
                {'code': 'ARCH301', 'name': 'Architectural Design II', 'credits': 4},
                {'code': 'CIVIL304', 'name': 'Environmental Engineering', 'credits': 3}
            ],
            '400': [
                {'code': 'CIVIL401', 'name': 'Advanced Structural Design', 'credits': 4},
                {'code': 'CIVIL402', 'name': 'Water Resources Engineering', 'credits': 3},
                {'code': 'ARCH401', 'name': 'Architectural Thesis', 'credits': 6},
                {'code': 'CIVIL403', 'name': 'Project Management', 'credits': 3}
            ]
        }
        
        # Electrical Engineering
        templates['ELEC'] = {
            '200': [
                {'code': 'ELEC201', 'name': 'Circuit Analysis II', 'credits': 3},
                {'code': 'ELEC202', 'name': 'Electronics I', 'credits': 3},
                {'code': 'ELEC203', 'name': 'Digital Logic Design', 'credits': 3},
                {'code': 'ELEC204', 'name': 'Electromagnetic Fields', 'credits': 3},
                {'code': 'ELEC205', 'name': 'Electrical Machines I', 'credits': 4}
            ],
            '300': [
                {'code': 'ELEC301', 'name': 'Power Systems I', 'credits': 3},
                {'code': 'ELEC302', 'name': 'Control Systems', 'credits': 3},
                {'code': 'ELEC303', 'name': 'Electronics II', 'credits': 3},
                {'code': 'ELEC304', 'name': 'Signal Processing', 'credits': 3},
                {'code': 'ELEC305', 'name': 'Electrical Machines II', 'credits': 4}
            ],
            '400': [
                {'code': 'ELEC401', 'name': 'Power Systems II', 'credits': 3},
                {'code': 'ELEC402', 'name': 'Advanced Control Systems', 'credits': 3},
                {'code': 'ELEC403', 'name': 'Renewable Energy Systems', 'credits': 3},
                {'code': 'ELEC404', 'name': 'Telecommunications', 'credits': 3}
            ]
        }
        
        # Computer Engineering
        templates['COMP'] = {
            '200': [
                {'code': 'COMP201', 'name': 'Data Structures & Algorithms', 'credits': 3},
                {'code': 'COMP202', 'name': 'Computer Architecture', 'credits': 3},
                {'code': 'COMP203', 'name': 'Database Systems', 'credits': 3},
                {'code': 'COMP204', 'name': 'Object Oriented Programming', 'credits': 3},
                {'code': 'COMP205', 'name': 'Digital Systems Design', 'credits': 4}
            ],
            '300': [
                {'code': 'COMP301', 'name': 'Operating Systems', 'credits': 3},
                {'code': 'COMP302', 'name': 'Computer Networks', 'credits': 3},
                {'code': 'COMP303', 'name': 'Software Engineering', 'credits': 3},
                {'code': 'COMP304', 'name': 'Embedded Systems', 'credits': 4},
                {'code': 'COMP305', 'name': 'Web Development', 'credits': 3}
            ],
            '400': [
                {'code': 'COMP401', 'name': 'Advanced Computer Networks', 'credits': 3},
                {'code': 'COMP402', 'name': 'Cybersecurity', 'credits': 3},
                {'code': 'COMP403', 'name': 'Machine Learning', 'credits': 3},
                {'code': 'COMP404', 'name': 'Software Project Management', 'credits': 3}
            ]
        }
        
        # Computer Science
        templates['CS'] = {
            '200': [
                {'code': 'CS202', 'name': 'Advanced Programming', 'credits': 3},
                {'code': 'CS203', 'name': 'Discrete Mathematics', 'credits': 3},
                {'code': 'CS204', 'name': 'Database Management', 'credits': 3},
                {'code': 'CS205', 'name': 'Web Programming', 'credits': 3},
                {'code': 'CS206', 'name': 'Human Computer Interaction', 'credits': 3}
            ],
            '300': [
                {'code': 'CS301', 'name': 'Algorithms Analysis', 'credits': 3},
                {'code': 'CS302', 'name': 'Artificial Intelligence', 'credits': 3},
                {'code': 'CS303', 'name': 'Software Architecture', 'credits': 3},
                {'code': 'CS304', 'name': 'Computer Graphics', 'credits': 3},
                {'code': 'CS305', 'name': 'Mobile App Development', 'credits': 3}
            ],
            '400': [
                {'code': 'CS401', 'name': 'Advanced Software Engineering', 'credits': 3},
                {'code': 'CS402', 'name': 'Data Science', 'credits': 3},
                {'code': 'CS403', 'name': 'Cloud Computing', 'credits': 3},
                {'code': 'CS404', 'name': 'Information Security', 'credits': 3}
            ]
        }
        
        return templates

    def get_existing_data(self):
        """Get existing departments and levels from database"""
        print("Getting existing departments and levels...")
        
        # Map existing departments
        departments = {}
        for dept_code, dept_name in self.department_mappings.items():
            # Try to find by name first
            dept = Department.objects.filter(department_name=dept_name).first()
            if not dept:
                # Try alternative mappings
                if dept_code == 'MECH':
                    dept = Department.objects.filter(department_name='Mechanical Engineering').first()
                elif dept_code == 'ELEC':
                    dept = Department.objects.filter(department_name='Electrical Engineering').first()
                elif dept_code == 'COMP':
                    dept = Department.objects.filter(department_name='Computer Engineering').first()
            
            if dept:
                departments[dept_code] = dept
                print(f"Found department: {dept.department_name}")
            else:
                print(f"⚠️  Department {dept_name} not found")
        
        # Map existing levels
        levels = {}
        for level_code, level_variants in self.level_mappings.items():
            level = None
            for variant in level_variants:
                level = Level.objects.filter(level_code=variant).first()
                if level:
                    break
            
            if level:
                levels[level_code] = level
                print(f"Found level: {level.level_name} ({level.level_code})")
            else:
                print(f"⚠️  Level {level_code} not found")
        
        return departments, levels

    def create_time_slots(self):
        """Create TimeSlot objects for the timetable"""
        print("Creating time slots...")
        
        time_slots = []
        for day_idx in self.working_days:
            for slot_config in self.time_slots_config:
                start_time = slot_config['start']
                end_time = slot_config['end']
                
                # Calculate duration in minutes
                start_datetime = datetime.combine(datetime.today(), start_time)
                end_datetime = datetime.combine(datetime.today(), end_time)
                duration = int((end_datetime - start_datetime).total_seconds() / 60)
                
                time_slot, created = TimeSlot.objects.get_or_create(
                    day_of_week=day_idx,
                    start_time=start_time,
                    defaults={
                        'end_time': end_time,
                        'duration_minutes': duration
                    }
                )
                
                if created:
                    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                    print(f"Created time slot: {days[day_idx]} {start_time} - {end_time}")
                
                time_slots.append(time_slot)
        
        return time_slots

    def create_rooms(self):
        """Create Room objects for the timetable"""
        print("Creating rooms...")
        
        rooms = []
        for hall_config in self.halls_config:
            room, created = Room.objects.get_or_create(
                name=hall_config['name'],
                defaults={
                    'capacity': hall_config['capacity'],
                    'building': hall_config['building'],
                    'equipment': ['Projector', 'Sound System', 'Whiteboard', 'Air Conditioning'],
                    'is_available': True
                }
            )
            
            if created:
                print(f"Created room: {hall_config['name']} (Capacity: {hall_config['capacity']})")
            
            rooms.append(room)
        
        return rooms

    def manage_teachers(self, departments):
        """Manage teachers - update existing and create needed ones"""
        print("Managing teachers...")
        
        # Get existing teachers
        existing_teachers = list(AdminUser.objects.filter(role='teacher'))
        print(f"Found {len(existing_teachers)} existing teachers")
        
        # Update existing teachers with missing information
        updated_count = 0
        for teacher in existing_teachers:
            updated = False
            
            # Ensure they have proper fields
            if not teacher.phone:
                teacher.phone = f"+237 123 45{random.randint(6000, 9999)}"
                updated = True
            
            if not teacher.job_title:
                teacher.job_title = random.choice(['Lecturer', 'Assistant Professor', 'Associate Professor', 'Professor'])
                updated = True
            
            if not teacher.hire_date:
                years_ago = random.randint(1, 5)
                teacher.hire_date = date(2025 - years_ago, random.randint(1, 12), random.randint(1, 28))
                updated = True
            
            if updated:
                teacher.save()
                updated_count += 1
                print(f"Updated teacher: {teacher.first_name} {teacher.last_name}")
        
        # Check if we need more teachers for any department
        dept_teacher_count = {}
        for teacher in existing_teachers:
            dept = teacher.department
            if dept:
                dept_teacher_count[dept] = dept_teacher_count.get(dept, 0) + 1
        
        # Create additional teachers if needed
        created_count = 0
        for dept_code, dept in departments.items():
            current_count = dept_teacher_count.get(dept, 0)
            if current_count < 2:  # Ensure at least 2 teachers per department
                needed = 2 - current_count
                for i in range(needed):
                    # Generate teacher data
                    first_names = ['Alex', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Avery', 'Quinn']
                    last_names = ['Johnson', 'Williams', 'Brown', 'Davis', 'Miller', 'Wilson', 'Moore', 'Anderson']
                    
                    first_name = random.choice(first_names)
                    last_name = random.choice(last_names)
                    username = f"{first_name.lower()}.{last_name.lower()}.{dept_code.lower()}"
                    
                    # Ensure uniqueness
                    counter = 1
                    original_username = username
                    while AdminUser.objects.filter(username=username).exists():
                        username = f"{original_username}{counter}"
                        counter += 1
                    
                    # Get appropriate specialization
                    specialization = Specialization.objects.filter(department=dept).first()
                    
                    try:
                        teacher = AdminUser.objects.create(
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            email=f"{username}@faceit.edu",
                            phone=f"+237 123 45{random.randint(6000, 9999)}",
                            role='teacher',
                            department=dept,
                            specialization=specialization,
                            job_title=random.choice(['Lecturer', 'Assistant Professor', 'Associate Professor']),
                            hire_date=date(2025 - random.randint(1, 3), random.randint(1, 12), random.randint(1, 28)),
                            is_active=True,
                            is_staff=True
                        )
                        
                        teacher.set_password('teacher123')
                        teacher.save()
                        
                        existing_teachers.append(teacher)
                        created_count += 1
                        print(f"Created teacher for {dept.department_name}: {first_name} {last_name}")
                        
                    except Exception as e:
                        print(f"Error creating teacher: {str(e)}")
        
        print(f"Teachers summary: {created_count} created, {updated_count} updated")
        return existing_teachers

    def create_courses(self, departments, levels):
        """Create courses for each department and level"""
        print("Creating courses...")
        
        courses = []
        created_count = 0
        
        for dept_code, course_templates in self.course_templates.items():
            if dept_code not in departments:
                print(f"Skipping {dept_code} - department not found")
                continue
                
            dept = departments[dept_code]
            
            for level_code, course_list in course_templates.items():
                if level_code not in levels:
                    print(f"Skipping level {level_code} - not found")
                    continue
                    
                level = levels[level_code]
                
                for course_data in course_list:
                    # Check if course already exists
                    existing_course = Course.objects.filter(course_code=course_data['code']).first()
                    
                    if existing_course:
                        courses.append(existing_course)
                        print(f"Found existing course: {course_data['code']}")
                    else:
                        try:
                            course = Course.objects.create(
                                course_code=course_data['code'],
                                course_name=course_data['name'],
                                credits=course_data['credits'],
                                department=dept,
                                level=level,
                                semester=self.semester,
                                description=f"{course_data['name']} for Level {level_code}",
                                status='active'
                            )
                            courses.append(course)
                            created_count += 1
                            print(f"Created course: {course_data['code']} - {course_data['name']}")
                        except Exception as e:
                            print(f"Error creating course {course_data['code']}: {str(e)}")
        
        print(f"Courses summary: {created_count} created, {len(courses)} total")
        return courses

    def assign_teachers_to_courses(self, courses, teachers):
        """Assign teachers to courses based on department"""
        print("Assigning teachers to courses...")
        
        # Group teachers by department
        dept_teachers = {}
        for teacher in teachers:
            dept = teacher.department
            if dept:
                if dept not in dept_teachers:
                    dept_teachers[dept] = []
                dept_teachers[dept].append(teacher)
        
        assigned_count = 0
        for course in courses:
            dept = course.department
            if dept in dept_teachers and dept_teachers[dept]:
                # Assign 1-2 teachers per course
                available_teachers = dept_teachers[dept]
                num_to_assign = min(random.randint(1, 2), len(available_teachers))
                assigned_teachers = random.sample(available_teachers, num_to_assign)
                course.teachers.set(assigned_teachers)
                assigned_count += 1
        
        print(f"Assigned teachers to {assigned_count} courses")

    def create_timetable_entries(self, courses, teachers, time_slots, rooms):
        """Create TimetableEntry objects for the complete timetable"""
        print("Creating timetable entries...")
        
        # Filter active courses
        active_courses = [c for c in courses if c.level.level_code in ['200', '300', '400', 'L200', 'L300', 'L400']]
        print(f"Working with {len(active_courses)} active courses")
        
        # Track assignments to avoid conflicts
        slot_room_assignments = {}
        slot_teacher_assignments = {}
        entries_created = 0
        
        for course in active_courses:
            # Get teachers for this course
            course_teachers = list(course.teachers.all())
            if not course_teachers:
                continue
            
            # Try to create 2 sessions per course
            sessions_created = 0
            attempts = 0
            max_attempts = 50
            
            while sessions_created < 2 and attempts < max_attempts:
                attempts += 1
                
                # Random selections
                time_slot = random.choice(time_slots)
                room = random.choice(rooms)
                teacher = random.choice(course_teachers)
                
                # Check for conflicts
                slot_room_key = (time_slot.id, room.id)
                slot_teacher_key = (time_slot.id, teacher.id)
                
                if (slot_room_key not in slot_room_assignments and 
                    slot_teacher_key not in slot_teacher_assignments):
                    
                    # Check if entry already exists
                    existing_entry = TimetableEntry.objects.filter(
                        course=course,
                        time_slot=time_slot,
                        room=room,
                        academic_year=self.academic_year,
                        semester=self.semester
                    ).first()
                    
                    if not existing_entry:
                        try:
                            entry = TimetableEntry.objects.create(
                                course=course,
                                teacher=teacher,
                                time_slot=time_slot,
                                room=room,
                                academic_year=self.academic_year,
                                semester=self.semester,
                                is_active=True,
                                notes=f"Regular class session for {course.course_code}"
                            )
                            
                            # Track assignments
                            slot_room_assignments[slot_room_key] = course.id
                            slot_teacher_assignments[slot_teacher_key] = course.id
                            sessions_created += 1
                            entries_created += 1
                            
                            if entries_created % 20 == 0:
                                print(f"Created {entries_created} timetable entries...")
                                
                        except Exception as e:
                            print(f"Error creating entry for {course.course_code}: {str(e)}")
                            continue
        
        print(f"Total timetable entries created: {entries_created}")
        return entries_created

    def generate_summary_report(self):
        """Generate a summary report of created data"""
        print("\n" + "="*70)
        print("FACE.IT TIMETABLE GENERATION SUMMARY REPORT")
        print("="*70)
        
        print(f"Institution: {self.institution_name}")
        print(f"Academic Year: {self.academic_year}")
        print(f"Semester: {self.semester}")
        
        print(f"\nDepartments Used: {Department.objects.count()}")
        for dept in Department.objects.all():
            courses_count = Course.objects.filter(department=dept, status='active').count()
            print(f"  - {dept.department_name}: {courses_count} courses")
        
        print(f"\nTeachers: {AdminUser.objects.filter(role='teacher').count()}")
        
        print(f"\nCourses: {Course.objects.filter(status='active').count()}")
        
        print(f"\nTime Slots: {TimeSlot.objects.count()}")
        
        print(f"\nRooms: {Room.objects.count()}")
        for room in Room.objects.all():
            print(f"  - {room.name} (Capacity: {room.capacity})")
        
        entries_count = TimetableEntry.objects.filter(
            academic_year=self.academic_year, 
            semester=self.semester
        ).count()
        print(f"\nTimetable Entries: {entries_count}")
        
        print("\n" + "="*70)
        print("✅ Timetable generation completed successfully!")
        print("🔗 You can now access the timetable via the API endpoints:")
        print("   - GET /api/timetable/entries/")
        print("   - GET /api/timetable/timeslots/")
        print("   - GET /api/timetable/rooms/")
        print("   - GET /api/timetable/teachers/")
        print("   - GET /api/timetable/courses/")
        print("\n📱 Your React frontend can now fetch this data!")
        print("="*70)

    def run(self):
        """Execute the complete timetable generation process"""
        print(f"🚀 Starting FACE.IT Timetable Generation for {self.institution_name}")
        print(f"📅 Academic Year: {self.academic_year}, Semester: {self.semester}")
        print("-" * 70)
        
        try:
            # Step 1: Get existing data
            print("📋 Step 1: Getting existing departments and levels...")
            departments, levels = self.get_existing_data()
            
            if not departments or not levels:
                print("❌ Required departments or levels not found. Please check your database.")
                return
            
            # Step 2: Create time slots
            print("\n⏰ Step 2: Creating time slots...")
            time_slots = self.create_time_slots()
            
            # Step 3: Create rooms
            print("\n🏢 Step 3: Creating rooms...")
            rooms = self.create_rooms()
            
            # Step 4: Manage teachers
            print("\n👨‍🏫 Step 4: Managing teachers...")
            teachers = self.manage_teachers(departments)
            
            # Step 5: Create courses
            print("\n📚 Step 5: Creating courses...")
            courses = self.create_courses(departments, levels)
            
            # Step 6: Assign teachers to courses
            print("\n🔗 Step 6: Assigning teachers to courses...")
            self.assign_teachers_to_courses(courses, teachers)
            
            # Step 7: Create timetable entries
            print("\n📅 Step 7: Creating timetable entries...")
            self.create_timetable_entries(courses, teachers, time_slots, rooms)
            
            # Step 8: Generate summary report
            print("\n📊 Step 8: Generating summary report...")
            self.generate_summary_report()
            
        except Exception as e:
            print(f"❌ Error during timetable generation: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    print("🎓 FACE.IT Timetable Generator (Fixed for Existing Database)")
    print("=" * 60)
    
    # Confirm before running
    response = input("⚠️  This will create/update timetable data. Continue? (y/N): ")
    if response.lower() != 'y':
        print("❌ Operation cancelled.")
        exit()
    
    generator = TimetableGenerator()
    generator.run()
    
    print("\n🎉 All done! Your FACE.IT timetable is ready.")
    print("💡 Next steps:")
    print("   1. Run your Django server: python manage.py runserver")
    print("   2. Access the timetable API endpoints")
    print("   3. Test the React frontend timetable components")