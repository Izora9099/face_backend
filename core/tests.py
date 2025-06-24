from django.test import TestCase

# Create your tests here.
import requests

# Replace with actual file path to a face photo
image_path = "/home/invictus/Pictures/Webcam/2025-06-24-123122.jpg"  

#/home/invictus/Pictures/Webcam/2025-06-24-123122.jpg

# Registration data
data = {
    "first_name": "Testi",
    "last_name": "Student", 
    "matric_number": "TEST2024002",
    "email": "test.student2@example.com",
    "department_id": "1",
    "specialization_id": "1", 
    "level_id": "1"
}

try:
    with open(image_path, 'rb') as img_file:
        files = {"image": img_file}
        response = requests.post(
            "http://127.0.0.1:8000/api/register-student/",
            data=data,
            files=files
        )
        
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
except FileNotFoundError:
    print("❌ Image file not found - update image_path variable")
except Exception as e:
    print(f"❌ Error: {e}")