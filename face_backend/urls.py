from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from core.views import get_students

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include core API endpoints (CSRF exemption will be handled in settings or individual views)
    path('api/', include('core.urls')),
    path('students/', csrf_exempt(get_students), name='get_students'),
    path('', include('core.urls')),
]