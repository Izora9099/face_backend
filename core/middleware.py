# This middleware automatically logs user activities

from django.utils import timezone
from .models import UserActivity, ActiveSession, SecuritySettings

class ActivityLoggingMiddleware:
    """Middleware to automatically log user activities"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        
        # Process the request
        response = self.get_response(request)
        
        self.process_response(request, response)
        return response

    def process_request(self, request):
        # Update session activity if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            self.update_session_activity(request)
        return None

    def process_response(self, request, response):
        # Log activities based on the request
        if hasattr(request, 'user') and request.user.is_authenticated:
            settings = SecuritySettings.get_settings()
            if settings.log_all_activities:  # Fixed: changed from track_user_activities
                self.log_activity_from_request(request, response)
        return response

    def update_session_activity(self, request):
        """Update or create active session tracking"""
        try:
            session_key = request.session.session_key
            if session_key:
                session, created = ActiveSession.objects.get_or_create(
                    session_key=session_key,
                    defaults={
                        'user': request.user,
                        'ip_address': get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'location': self.get_location_from_ip(get_client_ip(request)),
                    }
                )
                
                if not created:
                    session.last_activity = timezone.now()
                    # Removed activity_count since it doesn't exist in the model
                    session.save(update_fields=['last_activity'])
                    
        except Exception as e:
            print(f"Error updating session activity: {e}")

    def log_activity_from_request(self, request, response):
        """Log activities based on request path and method"""
        try:
            path = request.path
            method = request.method
            
            # Only log successful requests (200-299 status codes)
            if not (200 <= response.status_code < 300):
                return
            
            action = None
            resource = ''
            details = ''
            resource_id = None
            
            # Map URL patterns to activities
            if '/students/' in path:
                if method == 'GET':
                    action = 'VIEW_STUDENTS'
                    resource = 'students'
                    details = 'Viewed student list or details'
                elif method == 'POST':
                    action = 'CREATE_STUDENT'
                    resource = 'students'
                    details = 'Created new student'
                elif method == 'PUT':
                    action = 'UPDATE_STUDENT'
                    resource = 'students'
                    details = 'Updated student information'
                    # Extract student ID from path
                    try:
                        resource_id = int(path.split('/')[-2])
                    except (ValueError, IndexError):
                        pass
                        
            elif '/attendance' in path:
                if method == 'POST':
                    action = 'MARK_ATTENDANCE'
                    resource = 'attendance'
                    details = 'Marked student attendance'
                elif method == 'GET' and 'records' in path:
                    action = 'VIEW_STUDENTS'  # Changed to match model choices
                    resource = 'attendance'
                    details = 'Viewed attendance records'
                elif method == 'PUT':
                    action = 'UPDATE_STUDENT'  # Changed to match model choices
                    resource = 'attendance'
                    details = 'Updated attendance record'
                    
            elif '/face-recognition' in path or '/recognize-face' in path:
                action = 'USE_FACE_RECOGNITION'
                resource = 'face_recognition'
                if method == 'POST':
                    if 'upload' in path:
                        details = 'Uploaded face image for recognition'
                    elif 'recognize' in path:
                        details = 'Attempted face recognition'
                        
            elif '/reports/' in path:
                action = 'GENERATE_REPORT'
                resource = 'reports'
                details = 'Generated system report'
                
            elif '/admin-users/' in path:
                if method == 'GET':
                    action = 'VIEW_ADMIN_USERS'
                    resource = 'admin_users'
                    details = 'Viewed admin users list'
                elif method == 'POST':
                    action = 'CREATE_ADMIN_USER'
                    resource = 'admin_users'
                    details = 'Created new admin user'
                elif method == 'PUT':
                    action = 'UPDATE_ADMIN_USER'
                    resource = 'admin_users'
                    details = 'Updated admin user'
                elif method == 'DELETE':
                    action = 'DELETE_ADMIN_USER'
                    resource = 'admin_users'
                    details = 'Deleted admin user'
                    
            elif '/security/' in path:
                if 'settings' in path:
                    action = 'CHANGE_SECURITY_SETTINGS'
                    resource = 'security_settings'
                    details = 'Accessed security settings'
                elif 'export' in path:
                    action = 'GENERATE_REPORT'
                    resource = 'security_export'
                    details = 'Exported security data'
            
            # Log the activity if we identified one
            if action:
                log_user_activity(
                    user=request.user,
                    action=action,
                    resource=resource,
                    details=details,
                    request=request,
                    resource_id=resource_id,
                    status='success'  # Fixed: changed from status_type
                )
                
        except Exception as e:
            print(f"Error logging activity: {e}")

    def get_location_from_ip(self, ip_address):
        """Get location from IP address (implement with geolocation service)"""
        # You can implement this with a service like GeoIP2 or ipapi
        # For now, return a placeholder
        if ip_address and (ip_address.startswith('192.168.') or ip_address.startswith('127.')):
            return 'Local Network'
        return 'Unknown Location'

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

from .views import log_user_activity

class APICSRFExemptMiddleware:
    """
    Middleware to exempt API endpoints from CSRF protection
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # List of API endpoints to exempt from CSRF
        exempt_paths = [
            '/admin-users/',
            '/admin-users/create/',
            '/sessions/start/',
            '/sessions/end/',
            '/attendance/checkin/',
            '/register-student/',
            '/recognize-face/',
            '/api/',
        ]
        
        # Check if the request path starts with any exempt path
        for path in exempt_paths:
            if request.path.startswith(path):
                setattr(request, '_dont_enforce_csrf_checks', True)
                break
        
        # Also exempt any path that contains 'api' or common API patterns
        if ('/api/' in request.path or 
            request.path.startswith('/students/') or
            request.path.startswith('/courses/') or
            request.path.startswith('/departments/') or
            request.path.startswith('/specializations/') or
            request.path.startswith('/attendance/') or
            request.path.startswith('/security/') or
            request.path.startswith('/system/') or
            request.path.startswith('/enrollment/')):
            setattr(request, '_dont_enforce_csrf_checks', True)
        
        response = self.get_response(request)
        return response