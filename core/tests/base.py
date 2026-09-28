"""
Shared fixtures. Face photos in fixtures/ are public-domain official
portraits from the face_recognition project's examples (not real students).
"""

import io
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APITestCase

from core.models import AdminUser, Course, Student

FIXTURES = Path(__file__).parent / 'fixtures'
PASSWORD = 'Test!pass2026'


def image(name):
    return SimpleUploadedFile(name, (FIXTURES / name).read_bytes(), content_type='image/jpeg')


class APITestBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', password=PASSWORD, stdout=io.StringIO())
        cls.admin = AdminUser.objects.get(username='admin')
        cls.staff = AdminUser.objects.get(username='staff1')
        cls.teacher = AdminUser.objects.get(username='teacher1')
        cls.other_teacher = AdminUser.objects.get(username='teacher2')
        cls.course = Course.objects.get(course_code='CSC101')  # taught by teacher1
        cls.foreign_course = Course.objects.get(course_code='EEE101')  # taught by teacher2
        cls.students = list(cls.course.enrolled_students.order_by('matric_number'))

    def login(self, user):
        response = self.client.post('/api/auth/login/', {'username': user.username, 'password': PASSWORD},
                                    format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response

    def logout(self):
        self.client.credentials()

    def enroll_face(self, student, filename):
        self.login(self.admin)
        response = self.client.post(f'/api/students/{student.pk}/enroll-face/', {'image': image(filename)},
                                    format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        return Student.objects.get(pk=student.pk)
