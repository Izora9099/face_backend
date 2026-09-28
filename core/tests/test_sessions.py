"""Full attendance-session flow, including face recognition and manual override."""

from core.models import AttendanceRecord, SessionCheckIn

from .base import APITestBase, image


class SessionFlowTests(APITestBase):
    def setUp(self):
        self.amara, self.brian, self.third = self.students[:3]
        self.enroll_face(self.amara, 'obama.jpg')
        self.enroll_face(self.brian, 'biden.jpg')

    def start_session(self):
        self.login(self.teacher)
        response = self.client.post('/api/sessions/start/', {'course_id': self.course.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.data['success'])
        return response.data['session_id']

    def checkin(self, session_id, filename, path='/api/attendance/checkin/'):
        self.logout()  # the Android kiosk calls check-in without a token
        return self.client.post(path, {'session_id': session_id, 'image': image(filename)}, format='multipart')

    def test_full_flow(self):
        session_id = self.start_session()

        # A different photo of the enrolled student is recognised.
        response = self.checkin(session_id, 'obama2.jpg')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['student_id'], self.amara.pk)
        self.assertEqual(response.data['status'], 'present')
        self.assertLess(response.data['distance'], response.data['threshold'])
        self.assertGreater(response.data['confidence'], 0)

        # Second check-in of the same person is refused.
        again = self.checkin(session_id, 'obama.jpg')
        self.assertEqual(again.status_code, 400)

        # Legacy root path used by older Android builds.
        response = self.checkin(session_id, 'biden.jpg', path='/attendance/checkin/')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['student_id'], self.brian.pk)

        # Manual override for a student recognition could not handle.
        self.login(self.teacher)
        response = self.client.post(f'/api/sessions/{session_id}/mark/',
                                    {'student_id': self.third.pk, 'status': 'excused', 'notes': 'medical'},
                                    format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.data['is_manual_override'])

        stats = self.client.get(f'/api/sessions/{session_id}/stats/').data
        self.assertTrue(stats['success'])
        self.assertEqual(stats['stats']['present_count'], 2)

        ended = self.client.post('/api/sessions/end/', {'session_id': session_id}, format='json')
        self.assertEqual(ended.status_code, 200, ended.content)
        self.assertEqual(ended.data['session']['status'], 'completed')

        records = {r.student_id: r.status for r in AttendanceRecord.objects.filter(course=self.course)}
        self.assertEqual(records[self.amara.pk], 'present')
        self.assertEqual(records[self.brian.pk], 'present')
        self.assertEqual(records[self.third.pk], 'excused')
        # Everyone else enrolled was marked absent when the session ended.
        for student in self.students[3:]:
            self.assertEqual(records[student.pk], 'absent')

    def test_unknown_face_is_not_matched(self):
        session_id = self.start_session()
        # Enrolled faces only: Brian's face checked in against a course where he isn't enrolled.
        self.course.enrolled_students.remove(self.brian)
        response = self.checkin(session_id, 'biden.jpg')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertGreater(response.data['distance'], response.data['threshold'])
        self.assertFalse(SessionCheckIn.objects.exists())

    def test_image_without_face(self):
        session_id = self.start_session()
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        buf = BytesIO()
        Image.new('RGB', (200, 200), 'white').save(buf, 'JPEG')
        self.logout()
        response = self.client.post('/api/attendance/checkin/', {
            'session_id': session_id, 'image': SimpleUploadedFile('blank.jpg', buf.getvalue(), 'image/jpeg'),
        }, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'no_face')

    def test_teacher_cannot_run_sessions_for_other_courses(self):
        self.login(self.teacher)
        response = self.client.post('/api/sessions/start/', {'course_id': self.foreign_course.pk}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_only_one_active_session_per_course(self):
        session_id = self.start_session()
        response = self.client.post('/api/sessions/start/', {'course_id': self.course.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['session_id'], session_id)


class RecognitionTests(APITestBase):
    def setUp(self):
        self.amara = self.students[0]
        self.enroll_face(self.amara, 'obama.jpg')

    def test_recognize_face_marks_attendance_once(self):
        self.login(self.teacher)
        response = self.client.post('/api/recognize-face/', {'course_id': self.course.pk,
                                                             'image': image('obama2.jpg')}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['student']['id'], self.amara.pk)
        self.assertIn('threshold', response.data)
        self.assertIn('confidence', response.data)

        again = self.client.post('/api/recognize-face/', {'course_id': self.course.pk,
                                                          'image': image('obama.jpg')}, format='multipart')
        self.assertEqual(again.data['status'], 'info')

    def test_recognize_requires_login(self):
        self.logout()
        response = self.client.post('/api/recognize-face/', {'course_id': self.course.pk,
                                                             'image': image('obama.jpg')}, format='multipart')
        self.assertEqual(response.status_code, 401)

    def test_enrolment_rejects_duplicates_and_groups(self):
        self.login(self.admin)
        other = self.students[1]
        dup = self.client.post(f'/api/students/{other.pk}/enroll-face/', {'image': image('obama2.jpg')},
                               format='multipart')
        self.assertEqual(dup.status_code, 409)
        group = self.client.post(f'/api/students/{other.pk}/enroll-face/', {'image': image('two_people.jpg')},
                                 format='multipart')
        self.assertEqual(group.status_code, 400)
        self.assertEqual(group.data['code'], 'multiple_faces')

    def test_encoding_never_exposed(self):
        self.login(self.admin)
        detail = self.client.get(f'/api/students/{self.amara.pk}/')
        self.assertNotIn('face_encoding', detail.data)
        self.assertTrue(detail.data['face_enrolled'])
        self.assertNotIn(b' face_encoding:', self.client.get('/api/schema/').content)
