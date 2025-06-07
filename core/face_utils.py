import face_recognition
import numpy as np
from keras_facenet import FaceNet
from mtcnn.mtcnn import MTCNN
import cv2

# Initialize models only once
FACENET_EMBEDDER = None
MTCNN_DETECTOR = None


def get_dlib_encoding(image, model='cnn'):
    """
    Gets a face encoding using the dlib-based model (HOG or CNN).
    """
    encodings = face_recognition.face_encodings(image, num_jitters=2, model=model)
    if not encodings:
        return None
    return np.asarray(encodings[0], dtype=np.float64)


def get_facenet_encoding(image):
    """
    Gets a face embedding using the MTCNN + Keras-FaceNet model.
    """
    global MTCNN_DETECTOR, FACENET_EMBEDDER

    if MTCNN_DETECTOR is None:
        MTCNN_DETECTOR = MTCNN()
    if FACENET_EMBEDDER is None:
        FACENET_EMBEDDER = FaceNet()

    image_rgb = image  # Already in RGB if loaded with face_recognition

    detections = MTCNN_DETECTOR.detect_faces(image_rgb)
    if not detections:
        return None

    # Take the first face detected
    x, y, width, height = detections[0]['box']
    
    # Sanitize coordinates
    h, w, _ = image_rgb.shape
    x, y = max(x, 0), max(y, 0)
    x2, y2 = min(x + width, w), min(y + height, h)

    face = image_rgb[y:y2, x:x2]

    # Resize to FaceNet expected size
    try:
        face_resized = cv2.resize(face, (160, 160))
    except Exception as e:
        print("❌ Failed to resize face:", str(e))
        return None

    # Generate embedding
    try:
        embedding = FACENET_EMBEDDER.embeddings([face_resized])
        return np.asarray(embedding[0], dtype=np.float64)
    except Exception as e:
        print("❌ Failed to extract FaceNet embedding:", str(e))
        return None


def get_encoding(image, model_name):
    """
    Unified interface to get face encodings using the specified model.
    """
    if model_name in ['cnn', 'hog']:
        return get_dlib_encoding(image, model=model_name)
    elif model_name == 'facenet':
        return get_facenet_encoding(image)
    else:
        raise ValueError(f"Unknown model: {model_name}")


def compare_faces(known_encoding, unknown_encoding, model_name='cnn'):
    """
    Compares two encodings and determines if they match.
    """
    if model_name in ['cnn', 'hog']:
        return face_recognition.compare_faces([known_encoding], unknown_encoding)[0]
    elif model_name == 'facenet':
        distance = np.linalg.norm(known_encoding - unknown_encoding)
        return distance < 1.2  # Can be fine-tuned
    return False
