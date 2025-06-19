from django.db import models
from django_cryptography.fields import encrypt
from django.contrib.auth.models import AbstractUser

# --------------------------
# Custom Admin User Model
# --------------------------
class AdminUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, default='Staff')
    permissions = models.JSONField(default=list)

    def __str__(self):
        return self.username

# --------------------------
# Student Model
# --------------------------
class Student(models.Model):
    name = models.CharField(max_length=255)
    matric_number = models.CharField(max_length=50, unique=True)

    # 🔐 Encrypted binary field
    face_encoding = encrypt(models.BinaryField())
    face_encoding_model = models.CharField(max_length=10, default='cnn')
    registered_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.matric_number})"

# --------------------------
# Attendance Record Model
# --------------------------
class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default='Present')
    recognition_model = models.CharField(max_length=10, default='cnn')

    def __str__(self):
        return f"{self.student.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
