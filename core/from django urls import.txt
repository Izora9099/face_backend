from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_student),
    path('attendance/', views.take_attendance),
    path('post/', views.post_student_data),
    path('notify/', views.notify),
]

