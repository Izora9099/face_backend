# core/face_utils.py
import face_recognition
import numpy as np
from keras_facenet import FaceNet
from mtcnn.mtcnn import MTCNN
import cv2
from PIL import Image
from .adaptive_detector import AdaptiveFaceDetector

# Initialize models only once
FACENET_EMBEDDER = None
MTCNN_DETECTOR = None


def get_mtcnn_detector():
    """Initialize MTCNN detector with default settings"""
    global MTCNN_DETECTOR
    if MTCNN_DETECTOR is None:
        # Use default MTCNN initialization - most versions support this
        MTCNN_DETECTOR = MTCNN()
    return MTCNN_DETECTOR


def get_facenet_embedder():
    """Initialize FaceNet embedder"""
    global FACENET_EMBEDDER
    if FACENET_EMBEDDER is None:
        FACENET_EMBEDDER = FaceNet()
    return FACENET_EMBEDDER


def detect_and_align_face(image):
    """
    Use MTCNN to detect and align face from image.
    Returns aligned face crop or None if no face detected.
    """
    try:
        detector = get_mtcnn_detector()
        
        # Convert image to RGB if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Already RGB
            image_rgb = image
        else:
            # Convert BGR to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        print(f"🔍 Image shape for MTCNN: {image_rgb.shape}")
        
        # Detect faces
        detections = detector.detect_faces(image_rgb)
        
        if not detections:
            print("❌ No face detected by MTCNN")
            return None
            
        print(f"✅ MTCNN detected {len(detections)} face(s)")
        
        # Get the face with highest confidence
        best_detection = max(detections, key=lambda x: x['confidence'])
        
        print(f"🎯 Best detection confidence: {best_detection['confidence']:.3f}")
        
        if best_detection['confidence'] < 0.9:
            print(f"⚠️ Low confidence detection: {best_detection['confidence']:.3f}")
        
        # Extract bounding box
        x, y, width, height = best_detection['box']
        
        # Ensure coordinates are within image bounds
        h, w = image_rgb.shape[:2]
        x = max(0, x)
        y = max(0, y)
        x2 = min(w, x + width)
        y2 = min(h, y + height)
        
        print(f"📦 Face bounding box: x={x}, y={y}, w={width}, h={height}")
        
        # Extract face region with some padding
        padding = 20
        x_pad = max(0, x - padding)
        y_pad = max(0, y - padding)
        x2_pad = min(w, x2 + padding)
        y2_pad = min(h, y2 + padding)
        
        face_crop = image_rgb[y_pad:y2_pad, x_pad:x2_pad]
        
        if face_crop.size == 0:
            print("❌ Empty face crop")
            return None
            
        print(f"✅ Face crop extracted, shape: {face_crop.shape}")
        return face_crop
        
    except Exception as e:
        print(f"❌ Error in face detection: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return None


def get_facenet_encoding(face_crop):
    """
    Generate FaceNet encoding from aligned face crop.
    """
    try:
        embedder = get_facenet_embedder()
        
        # Resize to FaceNet input size (160x160)
        face_resized = cv2.resize(face_crop, (160, 160))
        
        # Normalize pixel values to [0, 1]
        face_normalized = face_resized.astype(np.float32) / 255.0
        
        # Get embedding
        embedding = embedder.embeddings([face_normalized])
        
        if embedding is None or len(embedding) == 0:
            print("❌ Failed to generate FaceNet embedding")
            return None
            
        return np.asarray(embedding[0], dtype=np.float64)
        
    except Exception as e:
        print(f"❌ Error generating FaceNet embedding: {str(e)}")
        return None


def get_dlib_encoding(face_crop):
    """
    Generate dlib encoding from aligned face crop using face_recognition library.
    """
    try:
        # face_recognition expects RGB format
        encodings = face_recognition.face_encodings(face_crop, num_jitters=2, model='cnn')
        
        if not encodings:
            print("❌ No face encodings found by dlib")
            return None
            
        return np.asarray(encodings[0], dtype=np.float64)
        
    except Exception as e:
        print(f"❌ Error generating dlib encoding: {str(e)}")
        return None


def get_encoding(image, model_name='facenet'):
    """
    Main function: Detect face with MTCNN, then encode with specified model.
    
    Args:
        image: Input image (numpy array)
        model_name: 'facenet' or 'dlib' for encoding
    
    Returns:
        (encoding, 'mtcnn+{model_name}') or (None, None)
    """
    print(f"🔍 Starting face detection and encoding with MTCNN + {model_name}")
    
    # Step 1: Detect and align face using MTCNN
    face_crop = detect_and_align_face(image)
    
    if face_crop is None:
        print("❌ Face detection failed")
        return None, None
    
    # Step 2: Generate encoding using specified model
    if model_name == 'facenet':
        encoding = get_facenet_encoding(face_crop)
        used_model = 'mtcnn+facenet'
    elif model_name == 'dlib':
        encoding = get_dlib_encoding(face_crop)
        used_model = 'mtcnn+dlib'
    else:
        print(f"❌ Unknown model: {model_name}")
        return None, None
    
    if encoding is not None:
        print(f"✅ Face encoding successful using: {used_model}")
        return encoding, used_model
    else:
        print(f"❌ Encoding failed with {used_model}")
        return None, None


def compare_faces(known_encoding, unknown_encoding, model_name='mtcnn+facenet', threshold=None):
    """
    Compare two face encodings.
    
    Args:
        known_encoding: Reference encoding
        unknown_encoding: Encoding to compare
        model_name: Model used for encoding
        threshold: Custom threshold (optional)
    
    Returns:
        Boolean indicating if faces match
    """
    try:
        if 'facenet' in model_name:
            # Use cosine similarity for FaceNet
            # Normalize vectors
            known_norm = known_encoding / np.linalg.norm(known_encoding)
            unknown_norm = unknown_encoding / np.linalg.norm(unknown_encoding)
            
            # Calculate cosine similarity
            similarity = np.dot(known_norm, unknown_norm)
            
            # Convert to distance (1 - similarity)
            distance = 1 - similarity
            
            # Default threshold for FaceNet cosine distance
            threshold = threshold or 0.4
            
            print(f"🔍 FaceNet distance: {distance:.3f}, threshold: {threshold}")
            return distance < threshold
            
        elif 'dlib' in model_name:
            # Use euclidean distance for dlib
            distance = np.linalg.norm(known_encoding - unknown_encoding)
            threshold = threshold or 0.6
            
            print(f"🔍 Dlib distance: {distance:.3f}, threshold: {threshold}")
            return distance < threshold
            
        else:
            print(f"❌ Unknown model for comparison: {model_name}")
            return False
            
    except Exception as e:
        print(f"❌ Error comparing faces: {str(e)}")
        return False


# Utility functions for image preprocessing
def preprocess_image(image_file_or_path):
    """
    Load and preprocess image from file or path.
    Returns RGB numpy array.
    """
    try:
        if isinstance(image_file_or_path, str):
            # Load from file path
            image = cv2.imread(image_file_or_path)
            if image is None:
                raise ValueError(f"Could not load image from path: {image_file_or_path}")
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            # Load from uploaded file
            image = face_recognition.load_image_file(image_file_or_path)
            
        print(f"✅ Image loaded successfully, shape: {image.shape}")
        return image
        
    except Exception as e:
        print(f"❌ Error loading image: {str(e)}")
        return None


def validate_image_quality(image):
    """
    Basic image quality validation.
    """
    if image is None:
        return False, "Image is None"
        
    if len(image.shape) != 3:
        return False, "Image must be color (3 channels)"
        
    h, w = image.shape[:2]
    if h < 100 or w < 100:
        return False, f"Image too small: {w}x{h}, minimum 100x100"
        
    if h > 4000 or w > 4000:
        return False, f"Image too large: {w}x{h}, maximum 4000x4000"
        
    return True, "Image quality OK"

# Add new function to your existing face_utils.py
def detect_faces_hof_adaptive(image_file_or_path, return_metrics=False):
    """
    Hall of Faces adaptive face detection
    Integrates with existing FACE.IT system
    """
    detector = AdaptiveFaceDetector()
    return detector.detect_faces_adaptive(image_file_or_path, return_metrics)

def validate_image_quality_enhanced(image):
    """
    Enhanced image quality validation using Hall of Faces enhancer
    """
    enhancer = ImageEnhancer()
    quality_score = enhancer.assess_image_quality(image)
    
    if quality_score >= 70:
        return True, f"Image quality excellent: {quality_score:.1f}/100"
    elif quality_score >= 50:
        return True, f"Image quality acceptable: {quality_score:.1f}/100"
    elif quality_score >= 30:
        return True, f"Image quality poor but usable: {quality_score:.1f}/100"
    else:
        return False, f"Image quality too poor: {quality_score:.1f}/100. Please retake photo."
