# File: core/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Student, AttendanceRecord
import face_recognition
import numpy as np
import base64
import io
from PIL import Image
@csrf_exempt
def register_student(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'fail', 'message': 'Only POST allowed'}, status=405)

    print("🔁 Register endpoint called.")
    print("POST:", request.POST)
    print("FILES:", request.FILES)

    name = request.POST.get('name')
    matric_number = request.POST.get('matric_number')
    image_file = request.FILES.get('image')

    if not name or not matric_number or not image_file:
        return JsonResponse({
            'status': 'fail',
            'message': 'Missing name, matric_number, or image.'
        }, status=400)

    try:
        # Load and encode the face image
        image = face_recognition.load_image_file(image_file)
        encodings = face_recognition.face_encodings(image)
        print("🔍 Encoding result:", encodings)

        if not encodings:
            return JsonResponse({
                'status': 'fail',
                'message': 'No face found in the image.'
            }, status=400)

        face_encoding = encodings[0].tobytes()

        # Prevent duplicate matric numbers
        if Student.objects.filter(matric_number=matric_number).exists():
            return JsonResponse({
                'status': 'fail',
                'message': 'Student with this matric number already exists.'
            }, status=409)

        # Save to DB
        Student.objects.create(
            name=name,
            matric_number=matric_number,
            face_encoding=face_encoding
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Student {name} registered successfully.'
        })

    except Exception as e:
        print("⚠️ Exception:", str(e))
        return JsonResponse({
            'status': 'fail',
            'message': f'Server error: {str(e)}'
        }, status=500)
@csrf_exempt
def take_attendance(request):
    if request.method == 'POST':
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'status': 'fail', 'message': 'No image provided.'}, status=400)

        try:
            unknown_image = face_recognition.load_image_file(image_file)
            unknown_encoding = face_recognition.face_encodings(unknown_image)
            if not unknown_encoding:
                return JsonResponse({'status': 'fail', 'message': 'No face found.'}, status=404)

            unknown_encoding = unknown_encoding[0]
            students = Student.objects.all()
            for student in students:
                known_encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                matches = face_recognition.compare_faces([known_encoding], unknown_encoding)
                if matches[0]:
                    AttendanceRecord.objects.create(student=student, timestamp=timezone.now())
                    return JsonResponse({'status': 'success', 'message': f'Attendance recorded for {student.name}.'})
            return JsonResponse({'status': 'fail', 'message': 'Face not recognized.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'fail', 'message': str(e)}, status=500)

@csrf_exempt
def post_student_data(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        matric_number = request.POST.get('matric_number')

        if not name or not matric_number:
            return JsonResponse({'status': 'fail', 'message': 'Name and matric number required.'}, status=400)

        if Student.objects.filter(matric_number=matric_number).exists():
            return JsonResponse({'status': 'fail', 'message': 'Student already exists.'}, status=400)

        Student.objects.create(name=name, matric_number=matric_number, face_encoding=b'')
        return JsonResponse({'status': 'success', 'message': 'Student info saved. Awaiting face scan.'})

@csrf_exempt
def notify(request):
    if request.method == 'GET':
        message = request.GET.get('message', 'Notification received.')
        return JsonResponse({'status': 'info', 'message': message})

