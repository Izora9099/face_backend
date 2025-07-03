# core/face_utils.py - Fixed version without circular import
import face_recognition
import numpy as np
from keras_facenet import FaceNet
from mtcnn.mtcnn import MTCNN
import cv2
from PIL import Image
# REMOVED: from .adaptive_detector import AdaptiveFaceDetector  # This was causing circular import

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
        result = detector.detect_faces(image)
        
        if result:
            # Get the face with highest confidence
            face = max(result, key=lambda x: x['confidence'])
            x, y, w, h = face['box']
            face_crop = image[y:y+h, x:x+w]
            return face_crop
        return None
    except Exception as e:
        print(f"Face detection failed: {e}")
        return None


def preprocess_image(image_file):
    """
    Preprocess uploaded image for face recognition
    """
    try:
        if hasattr(image_file, 'read'):
            # File upload object
            image_data = image_file.read()
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            # File path
            image = cv2.imread(str(image_file))
            
        if image is None:
            return None
            
        # Convert to RGB for face_recognition compatibility
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return image_rgb
        
    except Exception as e:
        print(f"Image preprocessing failed: {e}")
        return None


def compare_faces(known_encodings, face_encoding, tolerance=0.6):
    """
    Compare a face encoding against a list of known encodings
    """
    try:
        distances = face_recognition.face_distance(known_encodings, face_encoding)
        return distances <= tolerance
    except Exception as e:
        print(f"Face comparison failed: {e}")
        return []


def validate_image_quality(image):
    """
    Basic image quality validation
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


# HOF integration functions - using local imports to avoid circular imports
def detect_faces_hof_adaptive(image_file_or_path, return_metrics=False):
    """
    Hall of Faces adaptive face detection
    Integrates with existing FACE.IT system
    """
    try:
        # Import locally to avoid circular import
        from .adaptive_detector import AdaptiveFaceDetector
        detector = AdaptiveFaceDetector()
        return detector.detect_faces_adaptive(image_file_or_path, return_metrics)
    except Exception as e:
        print(f"HOF adaptive detection failed: {e}")
        return [] if not return_metrics else ([], {})


def validate_image_quality_enhanced(image):
    """
    Enhanced image quality validation using Hall of Faces enhancer
    """
    try:
        # Import locally to avoid circular import
        from .image_enhancer import ImageEnhancer
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
    except Exception as e:
        # Fallback to basic validation
        return validate_image_quality(image)


def recognize_faces_with_hof(image_file_or_path, known_encodings, known_names, tolerance=0.6):
    """
    Complete face recognition using HOF detection + face_recognition
    """
    try:
        # Import locally to avoid circular import
        from .adaptive_detector import AdaptiveFaceDetector
        
        detector = AdaptiveFaceDetector()
        
        # Load image
        if isinstance(image_file_or_path, str):
            image = cv2.imread(image_file_or_path)
        else:
            image = image_file_or_path
            
        if image is None:
            return []
            
        # Get face detections
        faces, metrics = detector.detect_faces_adaptive(image, return_metrics=True)
        
        if not faces:
            return []
            
        # Convert to RGB for face_recognition
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        recognition_results = []
        
        # Process each detected face
        for i, face in enumerate(faces):
            try:
                # Extract face region
                x1, y1, x2, y2 = face['bbox']
                
                # Add padding
                height, width = image.shape[:2]
                padding = 20
                x1 = max(0, x1 - padding)
                y1 = max(0, y1 - padding)
                x2 = min(width, x2 + padding)
                y2 = min(height, y2 + padding)
                
                # Extract and encode face
                face_region = rgb_image[y1:y2, x1:x2]
                face_encodings = face_recognition.face_encodings(face_region)
                
                if face_encodings:
                    face_encoding = face_encodings[0]
                    
                    # Compare with known faces
                    distances = face_recognition.face_distance(known_encodings, face_encoding)
                    best_match_index = np.argmin(distances)
                    
                    if distances[best_match_index] <= tolerance:
                        recognition_results.append({
                            'name': known_names[best_match_index],
                            'confidence': float(1 - distances[best_match_index]),
                            'bbox': face['bbox'],
                            'detection_confidence': face['confidence'],
                            'model_used': face['model_used'],
                            'quality_score': metrics['quality_score'],
                            'tier_used': metrics['tier_used']
                        })
                    else:
                        recognition_results.append({
                            'name': 'Unknown',
                            'confidence': 0.0,
                            'bbox': face['bbox'],
                            'detection_confidence': face['confidence'],
                            'model_used': face['model_used'],
                            'quality_score': metrics['quality_score'],
                            'tier_used': metrics['tier_used']
                        })
                        
            except Exception as e:
                print(f"Recognition failed for face {i}: {e}")
                continue
                
        return recognition_results
        
    except Exception as e:
        print(f"HOF recognition failed: {e}")
        return []
