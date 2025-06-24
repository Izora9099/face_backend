# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet)
router.register(r'specializations', views.SpecializationViewSet)
router.register(r'levels', views.LevelViewSet)
router.register(r'courses', views.CourseViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'attendance', views.AttendanceViewSet)

urlpatterns = [
    # Include ViewSet routes
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Legacy student and attendance endpoints (backward compatibility)
    path('register-student/', views.register_student, name='register_student'),
    path('recognize-face/', views.recognize_face, name='recognize_face'),
    path('get-students/', views.get_students, name='get_students'),
    path('get-attendance/', views.get_attendance_records, name='get_attendance_records'),
    
    # Dashboard and Analytics endpoints
    path('dashboard/stats/', views.dashboard_stats, name='dashboard_stats'),
    path('analytics/departments/', views.department_stats, name='department_stats'),
    path('analytics/courses/', views.course_stats, name='course_stats'),
    path('analytics/teachers/', views.teacher_stats, name='teacher_stats'),
    
    # Enrollment management endpoints
    path('enrollment/student/', views.manage_student_enrollment, name='manage_student_enrollment'),
    path('enrollment/bulk/', views.bulk_enrollment, name='bulk_enrollment'),
    
    # System management endpoints
    path('system/stats/', views.system_stats, name='system_stats'),
    
    # Academic structure quick access endpoints
    path('quick/departments/', views.DepartmentViewSet.as_view({'get': 'list'}), name='quick_departments'),
    path('quick/specializations/', views.SpecializationViewSet.as_view({'get': 'list'}), name='quick_specializations'),
    path('quick/levels/', views.LevelViewSet.as_view({'get': 'list'}), name='quick_levels'),
    path('quick/courses/', views.CourseViewSet.as_view({'get': 'list'}), name='quick_courses'),
]

# Additional URL patterns for specific endpoints
department_detail = views.DepartmentViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

specialization_detail = views.SpecializationViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

level_detail = views.LevelViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

course_detail = views.CourseViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

student_detail = views.StudentViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

attendance_detail = views.AttendanceViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

# Add the detail URL patterns
urlpatterns += [
    # Department detail endpoints
    path('departments/<int:pk>/', department_detail, name='department-detail'),
    path('departments/<int:pk>/stats/', views.DepartmentViewSet.as_view({'get': 'stats'}), name='department-stats'),
    
    # Specialization detail endpoints
    path('specializations/<int:pk>/', specialization_detail, name='specialization-detail'),
    
    # Level detail endpoints
    path('levels/<int:pk>/', level_detail, name='level-detail'),
    
    # Course detail endpoints
    path('courses/<int:pk>/', course_detail, name='course-detail'),
    path('courses/<int:pk>/students/', views.CourseViewSet.as_view({'get': 'students'}), name='course-students'),
    path('courses/<int:pk>/attendance/', views.CourseViewSet.as_view({'get': 'attendance'}), name='course-attendance'),
    path('courses/<int:pk>/enroll-students/', views.CourseViewSet.as_view({'post': 'enroll_students'}), name='course-enroll-students'),
    
    # Student detail endpoints
    path('students/<int:pk>/', student_detail, name='student-detail'),
    path('students/<int:pk>/courses/', views.StudentViewSet.as_view({'get': 'courses'}), name='student-courses'),
    path('students/<int:pk>/enroll-courses/', views.StudentViewSet.as_view({'post': 'enroll_courses'}), name='student-enroll-courses'),
    path('students/<int:pk>/auto-assign-courses/', views.StudentViewSet.as_view({'post': 'auto_assign_courses'}), name='student-auto-assign-courses'),
    path('students/<int:pk>/attendance-summary/', views.StudentViewSet.as_view({'get': 'attendance_summary'}), name='student-attendance-summary'),
    
    # Attendance detail endpoints
    path('attendance/<int:pk>/', attendance_detail, name='attendance-detail'),
]