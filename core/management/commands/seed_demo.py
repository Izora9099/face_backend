"""
Seed a small, realistic dataset for demos, frontend development and smoke tests.

    python manage.py seed_demo                   # idempotent
    python manage.py seed_demo --password S3cret!pass

Creates users `admin` (superadmin), `staff1` (staff) and `teacher1` (teacher),
two departments with levels/specializations/courses, students enrolled in
those courses, and a weekly timetable. Faces are not enrolled: use
POST /api/students/<id>/enroll-face/ with a photo.
"""

from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    AdminUser, Course, Department, Level, Room, Specialization, Student, TimeSlot,
    TimetableEntry,
)

DEPARTMENTS = [
    ('Computer Science', 'CSC', [('Software Engineering', 'SWE'), ('Artificial Intelligence', 'AIN')]),
    ('Electrical Engineering', 'EEE', [('Power Systems', 'PWS'), ('Telecommunications', 'TEL')]),
]
LEVELS = [('100', 'L100', 1), ('200', 'L200', 2), ('300', 'L300', 3), ('400', 'L400', 4)]
COURSES = {
    'CSC': [('CSC101', 'Introduction to Programming', 'L100'), ('CSC201', 'Data Structures', 'L200'),
            ('CSC301', 'Machine Learning', 'L300'), ('CSC401', 'Computer Vision', 'L400')],
    'EEE': [('EEE101', 'Circuit Theory', 'L100'), ('EEE201', 'Signals and Systems', 'L200'),
            ('EEE301', 'Power Electronics', 'L300'), ('EEE401', 'Digital Communications', 'L400')],
}
STUDENTS = [
    ('Amara', 'Nkem', 'CSC', 'L100'), ('Brian', 'Tabi', 'CSC', 'L100'), ('Chioma', 'Eze', 'CSC', 'L200'),
    ('Daniel', 'Fon', 'CSC', 'L300'), ('Esther', 'Mbah', 'CSC', 'L400'), ('Felix', 'Ngu', 'EEE', 'L100'),
    ('Grace', 'Ashu', 'EEE', 'L200'), ('Henry', 'Ebai', 'EEE', 'L300'), ('Irene', 'Tanyi', 'EEE', 'L400'),
    ('James', 'Ayuk', 'CSC', 'L100'),
]


class Command(BaseCommand):
    help = 'Seed demo data (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='FaceIt!2026',
                            help='Password for the demo users (default: FaceIt!2026)')

    @transaction.atomic
    def handle(self, *args, password, **options):
        levels = {}
        for name, code, order in LEVELS:
            levels[code], _ = Level.objects.get_or_create(
                level_code=code, defaults={'level_name': name, 'level_order': order})

        departments, specs = {}, {}
        for dept_name, dept_code, spec_list in DEPARTMENTS:
            dept, _ = Department.objects.get_or_create(
                department_code=dept_code, defaults={'department_name': dept_name})
            departments[dept_code] = dept
            for level in levels.values():
                level.departments.add(dept)
            for spec_name, spec_code in spec_list:
                spec, _ = Specialization.objects.get_or_create(
                    specialization_code=spec_code,
                    defaults={'specialization_name': spec_name, 'department': dept})
                specs.setdefault(dept_code, []).append(spec)
                for level in levels.values():
                    level.specializations.add(spec)

        users = {}
        for username, role, first, last, dept in [
            ('admin', 'superadmin', 'System', 'Admin', None),
            ('staff1', 'staff', 'Sarah', 'Registry', None),
            ('teacher1', 'teacher', 'Paul', 'Ndifor', 'CSC'),
            ('teacher2', 'teacher', 'Linda', 'Achu', 'EEE'),
        ]:
            user, created = AdminUser.objects.get_or_create(username=username, defaults={
                'role': role, 'first_name': first, 'last_name': last,
                'email': f'{username}@faceit.local',
                'department': departments.get(dept),
                'is_superuser': role == 'superadmin', 'is_staff': role == 'superadmin',
            })
            if created:
                user.set_password(password)
                user.save()
            users[username] = user

        courses = []
        for dept_code, course_list in COURSES.items():
            teacher = users['teacher1'] if dept_code == 'CSC' else users['teacher2']
            for code, name, level_code in course_list:
                course, _ = Course.objects.get_or_create(course_code=code, defaults={
                    'course_name': name, 'department': departments[dept_code], 'level': levels[level_code]})
                course.specializations.add(*specs[dept_code])
                course.teachers.add(teacher)
                courses.append(course)

        for i, (first, last, dept_code, level_code) in enumerate(STUDENTS, start=1):
            student, created = Student.objects.get_or_create(
                matric_number=f'{dept_code}26{i:03d}', defaults={
                    'first_name': first, 'last_name': last,
                    'email': f'{first.lower()}.{last.lower()}@student.faceit.local',
                    'department': departments[dept_code], 'level': levels[level_code],
                    'specialization': specs[dept_code][i % 2],
                })
            if created:
                # Specialization-filtered auto-assignment can miss; enrol by department + level.
                student.enrolled_courses.add(*Course.objects.filter(
                    department=student.department, level=student.level))

        slots = []
        for day in range(5):
            for start, end in [(time(8), time(10)), (time(10), time(12)), (time(13), time(15))]:
                slot, _ = TimeSlot.objects.get_or_create(
                    day_of_week=day, start_time=start, defaults={'end_time': end, 'duration_minutes': 120})
                slots.append(slot)
        rooms = [Room.objects.get_or_create(name=name, defaults={'capacity': cap, 'building': bld})[0]
                 for name, cap, bld in [('Hall A', 120, 'Main'), ('Lab 1', 40, 'Engineering')]]
        for i, course in enumerate(courses):
            teacher = course.teachers.first()
            slot = slots[i * 2 % len(slots)]
            room = rooms[i % len(rooms)]
            if not TimetableEntry.objects.filter(time_slot=slot, room=room).exists() and \
                    not TimetableEntry.objects.filter(time_slot=slot, teacher=teacher).exists():
                TimetableEntry.objects.get_or_create(course=course, teacher=teacher, time_slot=slot, room=room)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded: {Department.objects.count()} departments, {Course.objects.count()} courses, '
            f'{Student.objects.count()} students, {TimetableEntry.objects.count()} timetable entries.\n'
            f'Users admin / staff1 / teacher1 / teacher2 (password for newly created users: {password})'))
