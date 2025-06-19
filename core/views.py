# core/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from .models import Student, AttendanceRecord, AdminUser
import numpy as np
import face_recognition
import json
import datetime
from . import face_utils
from datetime import timedelta

@csrf_exempt
def register_student(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'fail', 'message': 'Only POST requests allowed.'}, status=405)

    name = request.POST.get('name')
    matric_number = request.POST.get('matric_number')
    image_file = request.FILES.get('image')

    if not name or not matric_number or not image_file:
        return JsonResponse({'status': 'fail', 'message': 'Missing name, matric_number, or image.'}, status=400)

    try:
        with open(f'debug_{matric_number}.jpg', 'wb') as f:
            for chunk in image_file.chunks():
                f.write(chunk)

        image = face_recognition.load_image_file(image_file)

        models_to_try = ['cnn', 'hog', 'facenet']
        face_encoding = None
        successful_model = None

        for model in models_to_try:
            encoding = face_utils.get_encoding(image, model)
            if encoding is not None:
                face_encoding = encoding.tobytes()
                successful_model = model
                break

        if face_encoding is None:
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
        return JsonResponse({'status': 'fail', 'message': f'Server error: {str(e)}'}, status=500)

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
                unknown_encoding = face_utils.get_encoding(unknown_image, model_name)

                if unknown_encoding is None:
                    continue

                known_encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                is_match = face_utils.compare_faces(known_encoding, unknown_encoding, model_name)

                if is_match:
                    AttendanceRecord.objects.create(student=student, timestamp=timezone.now(), recognition_model=model_name)
                    return JsonResponse({'status': 'success', 'message': f'Attendance recorded for {student.name} using {model_name} model.'})

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

@csrf_exempt
def admin_users_view(request):
    if request.method == 'GET':
        users = AdminUser.objects.all()
        data = [{
            "id": user.id,
            "name": user.first_name or user.username,  # ✅ Make sure name is defined
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "status": "Active" if user.is_active else "Inactive",
            "permissions": user.permissions,
            "lastLogin": user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else ""
        } for user in users]
        return JsonResponse(data, safe=False)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)

            user = AdminUser.objects.create(
                username=data['email'],
                email=data['email'],
                first_name=data.get('name', ''),  # ✅ Save name in first_name field
                phone=data.get('phone', ''),
                role=data.get('role', 'Staff'),
                permissions=data.get('permissions', []),
                password=make_password('default1234')
            )
            return JsonResponse({'status': 'success', 'id': user.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

def user_list(request):
    users = AdminUser.objects.all()
    return render(request, 'user_list.html', {'users': users})

@csrf_exempt
def get_students(request):
    if request.method == 'GET':
        students = Student.objects.all()
        data = [
            {
                "id": student.id,
                "name": student.name,
                "matric_number": student.matric_number,
                "face_encoding_model": student.face_encoding_model,
                "registered_on": student.registered_on.strftime("%Y-%m-%d %H:%M")
            }
            for student in students
        ]
        return JsonResponse(data, safe=False)

    return JsonResponse({"error": "Only GET allowed"}, status=405)
@csrf_exempt
def update_student(request, id):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Only PUT allowed'}, status=405)

    try:
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)

        student = Student.objects.get(id=id)

        student.name = data.get('name', student.name)
        student.matric_number = data.get('matric_number', student.matric_number)
        student.face_encoding_model = data.get('face_encoding_model', student.face_encoding_model)
        student.save()

        return JsonResponse({'status': 'success', 'message': 'Student updated'})
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def get_attendance_records(request):
    date = request.GET.get('date')
    student_name = request.GET.get('name')
    matric_number = request.GET.get('matric_number')

    queryset = AttendanceRecord.objects.select_related('student').all()

    if date:
        queryset = queryset.filter(timestamp__date=date)
    if student_name:
        queryset = queryset.filter(student__name__icontains=student_name)
    if matric_number:
        queryset = queryset.filter(student__matric_number__icontains=matric_number)

    records = [{
        "id": record.id,
        "student_id": record.student.id,
        "student_name": record.student.name,
        "matric_number": record.student.matric_number,
        "status": record.status,
        "check_in": record.timestamp.strftime("%H:%M"),
        "date": record.timestamp.strftime("%Y-%m-%d"),
    } for record in queryset]

    # ✅ FIX: Don't pass `cls` twice — JsonResponse already uses DjangoJSONEncoder by default.
    return JsonResponse(
        records,
        safe=False,
        json_dumps_params={"ensure_ascii": False}
    )

@csrf_exempt
@require_http_methods(["PUT"])
def update_attendance_record(request, record_id):
    try:
        data = json.loads(request.body)
        record = AttendanceRecord.objects.select_related('student').get(id=record_id)

        new_status = data.get('status')
        new_time = data.get('check_in')

        if new_status:
            record.status = new_status

        if new_time:
            date_part = record.timestamp.strftime("%Y-%m-%d")
            updated_timestamp = datetime.datetime.strptime(f"{date_part} {new_time}", "%Y-%m-%d %H:%M")
            record.timestamp = timezone.make_aware(updated_timestamp)

        record.save()
        return JsonResponse({"status": "success", "message": "Attendance updated"})

    except AttendanceRecord.DoesNotExist:
        return JsonResponse({'error': 'Attendance record not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@require_http_methods(["GET"])
def get_weekly_attendance_summary(request):
    today = timezone.now().date()
    summary = []

    for i in range(7):
        day = today - timedelta(days=i)
        records = AttendanceRecord.objects.filter(timestamp__date=day)
        present_count = records.filter(status='Present').count()
        absent_count = records.filter(status='Absent').count()

        summary.append({
            "date": day.strftime("%a"),  # 'Mon', 'Tue', etc.
            "present": present_count,
            "absent": absent_count,
        })

    return JsonResponse(list(reversed(summary)), safe=False)