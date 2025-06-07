from django.db import models

class Student(models.Model):
    name = models.CharField(max_length=255)
    matric_number = models.CharField(max_length=50, unique=True)
    face_encoding = models.BinaryField()
    face_encoding_model = models.CharField(max_length=10, default='cnn')
    registered_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.matric_number})"

class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default='Present')
    recognition_model = models.CharField(max_length=10, default='cnn')

    def __str__(self):
        return f"{self.student.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

