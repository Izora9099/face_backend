from core.models import Department, Level

from .base import APITestBase


class StudentCrudTests(APITestBase):
    def test_round_trip(self):
        self.login(self.staff)
        dept = Department.objects.get(department_code='CSC')
        level = Level.objects.get(level_code='L100')
        payload = {
            'first_name': 'Kim', 'last_name': 'Ade', 'matric_number': 'CSC99001',
            'email': 'kim.ade@example.com', 'department': dept.pk, 'level': level.pk,
        }
        created = self.client.post('/api/students/', payload, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        self.assertNotIn('face_encoding', created.data)
        self.assertFalse(created.data['face_enrolled'])
        pk = created.data['id']

        listed = self.client.get('/api/students/', {'search': 'CSC99001'})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(set(listed.data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(listed.data['count'], 1)

        updated = self.client.patch(f'/api/students/{pk}/', {'phone': '+237600000000'}, format='json')
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.data['phone'], '+237600000000')

        self.assertEqual(self.client.delete(f'/api/students/{pk}/').status_code, 204)
        self.assertEqual(self.client.get(f'/api/students/{pk}/').status_code, 404)

    def test_level_must_belong_to_department(self):
        self.login(self.staff)
        orphan = Level.objects.create(level_name='900', level_code='L900')
        response = self.client.post('/api/students/', {
            'first_name': 'A', 'last_name': 'B', 'matric_number': 'X1', 'email': 'x1@example.com',
            'department': Department.objects.first().pk, 'level': orphan.pk,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('level', response.data)

    def test_teacher_sees_only_students_of_own_courses_and_cannot_write(self):
        self.login(self.teacher)
        response = self.client.get('/api/students/', {'page_size': 100})
        matrics = {s['matric_number'] for s in response.data['results']}
        self.assertTrue(matrics)
        self.assertTrue(all(m.startswith('CSC') for m in matrics))
        self.assertEqual(self.client.post('/api/students/', {}, format='json').status_code, 403)


class CourseCrudTests(APITestBase):
    def test_round_trip(self):
        self.login(self.admin)
        dept = Department.objects.get(department_code='CSC')
        level = Level.objects.get(level_code='L200')
        created = self.client.post('/api/courses/', {
            'course_code': 'CSC299', 'course_name': 'Research Methods', 'credits': 2,
            'department': dept.pk, 'level': level.pk, 'teachers': [self.teacher.pk],
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        pk = created.data['id']

        self.assertEqual(self.client.get(f'/api/courses/{pk}/').data['course_name'], 'Research Methods')
        updated = self.client.patch(f'/api/courses/{pk}/', {'credits': 4}, format='json')
        self.assertEqual(updated.data['credits'], 4)

        enrolled = self.client.post(f'/api/courses/{pk}/enroll-students/',
                                    {'student_ids': [s.pk for s in self.students]}, format='json')
        self.assertEqual(enrolled.data['enrolled'], len(self.students))
        self.assertEqual(len(self.client.get(f'/api/courses/{pk}/students/').data), len(self.students))

        self.assertEqual(self.client.delete(f'/api/courses/{pk}/').status_code, 204)

    def test_teacher_only_sees_own_courses(self):
        self.login(self.teacher)
        codes = {c['course_code'] for c in self.client.get('/api/courses/').data}
        self.assertIn('CSC101', codes)
        self.assertNotIn('EEE101', codes)
        self.assertEqual(self.client.get(f'/api/courses/{self.foreign_course.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/courses/{self.course.pk}/', {'credits': 1},
                                           format='json').status_code, 403)

    def test_schema_and_docs(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)
