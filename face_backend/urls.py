from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.urls import ANDROID_ROUTES

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/', include('core.urls')),
    # Backward compatibility: older Android builds call the session routes
    # without the /api/ prefix.
    path('', include((ANDROID_ROUTES, 'android'), namespace='android')),
]
