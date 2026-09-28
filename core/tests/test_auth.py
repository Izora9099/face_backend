from core.models import LoginAttempt

from .base import PASSWORD, APITestBase


class AuthTests(APITestBase):
    def test_login_returns_tokens_and_user(self):
        response = self.login(self.teacher)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'teacher1')
        self.assertEqual(response.data['user']['role'], 'teacher')
        self.assertTrue(LoginAttempt.objects.filter(username='teacher1', success=True).exists())

    def test_bad_password_is_rejected_and_recorded(self):
        response = self.client.post('/api/auth/login/', {'username': 'teacher1', 'password': 'wrong'},
                                    format='json')
        self.assertEqual(response.status_code, 401)
        self.assertTrue(LoginAttempt.objects.filter(username='teacher1', success=False).exists())

    def test_current_user(self):
        self.login(self.admin)
        response = self.client.get('/api/auth/user/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['role'], 'superadmin')
        self.assertIn('manage_users', response.data['permissions'])

    def test_refresh(self):
        tokens = self.client.post('/api/auth/login/', {'username': 'staff1', 'password': PASSWORD},
                                  format='json').data
        response = self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

    def test_endpoints_require_auth(self):
        for url in ['/api/auth/user/', '/api/students/', '/api/courses/', '/api/dashboard/stats/']:
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_admin_user_management_is_superadmin_only(self):
        payload = {'username': 'newbie', 'email': 'newbie@x.io', 'password': 'Longenough1!', 'role': 'Teacher'}
        self.login(self.staff)
        self.assertEqual(self.client.post('/api/admin-users/create/', payload, format='json').status_code, 403)
        self.login(self.admin)
        response = self.client.post('/api/admin-users/create/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['role'], 'teacher')
        user_id = response.data['id']
        response = self.client.put(f'/api/admin-users/{user_id}/', {'job_title': 'Lecturer'}, format='json')
        self.assertEqual(response.data['job_title'], 'Lecturer')
        self.assertEqual(self.client.delete(f'/api/admin-users/{user_id}/').status_code, 200)
