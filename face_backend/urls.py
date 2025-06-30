from django.contrib import admin
from django.urls import path, include
from core.views import get_students


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('students/', get_students, name='get_students'),
    path('', include('core.urls')),
]
