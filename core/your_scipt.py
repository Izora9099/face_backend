from mtcnn.mtcnn import MTCNN
import cv2

# ✅ Correct file path without 'image=@'
img = cv2.imread("/home/invictus/face_backend/debug_0001.jpg")

# Check if image was loaded successfully
if img is None:
    print("Error: Could not load image. Check the file path.")
    exit()

# Optional: Resize if image is too large
if img.shape[0] > 800 or img.shape[1] > 800:
    img = cv2.resize(img, (640, 480))

# Initialize MTCNN detector
detector = MTCNN()

# Detect faces
result = detector.detect_faces(img)
print(result)