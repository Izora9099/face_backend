from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Student, AttendanceRecord
import numpy as np
from . import face_utils
import face_recognition

# ----------------------------
# Register Student View
# ----------------------------
@csrf_exempt
def register_student(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'fail', 'message': 'Only POST requests allowed.'}, status=405)

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
        # Save image for debugging
        with open(f'debug_{matric_number}.jpg', 'wb') as f:
            for chunk in image_file.chunks():
                f.write(chunk)
        print("✅ Image saved as debug file.")

        # Load and encode face
        image = face_recognition.load_image_file(image_file)
        print("✅ Image shape:", image.shape)

        models_to_try = ['cnn', 'hog', 'facenet']
        face_encoding = None
        successful_model = None

        for model in models_to_try:
            print(f"Trying model: {model}")
            encoding = face_utils.get_encoding(image, model)
            if encoding is not None:
                face_encoding = encoding.tobytes()
                successful_model = model
                print(f"✅ Face found using {model} model.")
                break
        
        if face_encoding is None:
            print("❌ No face encodings detected. The image might not contain a recognizable face.")
            return JsonResponse({'status': 'fail', 'message': 'No face found in the image.'}, status=400)

        if Student.objects.filter(matric_number=matric_number).exists():
            return JsonResponse({'status': 'fail', 'message': 'Student already exists.'}, status=409)

        Student.objects.create(
            name=name,
            matric_number=matric_number,
            face_encoding=face_encoding,
            face_encoding_model=successful_model
        )

        return JsonResponse({'status': 'success', 'message': f'Student {name} registered successfully using {successful_model} model.'})

    except Exception as e:
        print("❌ Error during registration:", str(e))
        return JsonResponse({'status': 'fail', 'message': f'Server error: {str(e)}'}, status=500)

# ----------------------------
# Take Attendance View
# ----------------------------
@csrf_exempt
def take_attendance(request):
    if request.method == 'POST':
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'status': 'fail', 'message': 'No image provided.'}, status=400)

        try:
            unknown_image = face_recognition.load_image_file(image_file)
            
            students = Student.objects.all()
            for student in students:
                model_name = student.face_encoding_model
                print(f"Attempting to recognize {student.name} using model {model_name}")
                
                unknown_encoding = face_utils.get_encoding(unknown_image, model_name)

                if unknown_encoding is None:
                    print(f"No face found in image for student {student.name} using model {model_name}.")
                    continue

                known_encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                
                is_match = face_utils.compare_faces(known_encoding, unknown_encoding, model_name)

                if is_match:
                    AttendanceRecord.objects.create(student=student, timestamp=timezone.now(), recognition_model=model_name)
                    return JsonResponse({'status': 'success', 'message': f'Attendance recorded for {student.name} using {model_name} model.'})
            return JsonResponse({'status': 'fail', 'message': 'Face not recognized.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'fail', 'message': str(e)}, status=500)


# ----------------------------
# Save Student Info Without Face
# ----------------------------
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


# ----------------------------
# Notify View (Basic Message Echo)
# ----------------------------
@csrf_exempt
def notify(request):
    if request.method == 'GET':
        message = request.GET.get('message', 'Notification received.')
        return JsonResponse({'status': 'info', 'message': message})
