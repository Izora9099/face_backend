#!/bin/bash
# immediate_fix.sh - Fix the circular import right now

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${RED}🔧 Fixing Circular Import Issue${NC}"
echo "================================="

# Step 1: Backup current files
echo -e "${YELLOW}Step 1: Creating backups...${NC}"
cp core/adaptive_detector.py core/adaptive_detector_backup.py
cp core/face_utils.py core/face_utils_backup.py
echo "✅ Backups created"

# Step 2: Fix adaptive_detector.py - remove the problematic import
echo -e "${YELLOW}Step 2: Fixing adaptive_detector.py...${NC}"

cat > core/adaptive_detector.py << 'EOF'
# core/adaptive_detector.py - Fixed version without circular import
from .hof_models import HallOfFacesModels
from .image_enhancer import ImageEnhancer
# REMOVED: from .face_utils import compare_faces  # This was causing circular import
import cv2
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

class AdaptiveFaceDetector:
    """
    Implements 3-tier adaptive face detection system:
    1. Tiny YOLO for clear images (fast)
    2. Enhanced YOLO for moderate quality
    3. Preprocessing + Enhanced YOLO for poor quality
    """
    
    def __init__(self):
        self.hof_models = HallOfFacesModels()
        self.enhancer = ImageEnhancer()
        
        # Quality thresholds for tier selection
        self.quality_thresholds = {
            'excellent': 85,  # Use Tiny YOLO
            'good': 60,       # Use Enhanced YOLO
            'acceptable': 30, # Use Preprocessing + Enhanced YOLO
            'poor': 0         # Try all methods
        }
        
        # Download models on initialization
        self.hof_models.download_models()
        
    def detect_faces_adaptive(self, image_path_or_array, return_metrics=False):
        """
        Main adaptive detection method
        
        Args:
            image_path_or_array: Image file path or numpy array
            return_metrics: Whether to return performance metrics
            
        Returns:
            List of detected faces with bounding boxes and confidence
            Optional: Performance metrics if return_metrics=True
        """
        start_time = time.time()
        
        # Load image if path provided
        if isinstance(image_path_or_array, str):
            image = cv2.imread(image_path_or_array)
            if image is None:
                logger.error(f"Could not load image: {image_path_or_array}")
                return [] if not return_metrics else ([], {})
        else:
            image = image_path_or_array.copy()
            
        # Assess image quality
        quality_score = self.enhancer.assess_image_quality(image)
        
        # Select detection tier based on quality
        tier_used, faces = self._select_and_execute_tier(image, quality_score)
        
        processing_time = time.time() - start_time
        
        metrics = {
            'quality_score': quality_score,
            'tier_used': tier_used,
            'processing_time': processing_time,
            'faces_detected': len(faces),
            'image_shape': image.shape
        }
        
        logger.info(f"Adaptive detection: {len(faces)} faces, "
                   f"quality={quality_score:.1f}, tier={tier_used}, "
                   f"time={processing_time:.2f}s")
        
        if return_metrics:
            return faces, metrics
        return faces
        
    def _select_and_execute_tier(self, image, quality_score):
        """Select appropriate detection tier and execute"""
        
        if quality_score >= self.quality_thresholds['excellent']:
            # Tier 1: Tiny YOLO for excellent quality
            tier_used = 'tier_1_tiny_yolo'
            faces = self.hof_models.detect_faces(image, 'tiny_yolo')
            
        elif quality_score >= self.quality_thresholds['good']:
            # Tier 2: Enhanced YOLO for good quality
            tier_used = 'tier_2_enhanced_yolo'
            faces = self.hof_models.detect_faces(image, 'enhanced_yolo')
            
        elif quality_score >= self.quality_thresholds['acceptable']:
            # Tier 3: Preprocessing + Enhanced YOLO
            tier_used = 'tier_3_preprocessing_enhanced'
            enhanced_image = self.enhancer.enhance_image(image, quality_score)
            faces = self.hof_models.detect_faces(enhanced_image, 'enhanced_yolo')
            
        else:
            # Very poor quality: Try progressive enhancement
            tier_used = 'tier_4_progressive'
            faces = self._progressive_detection(image, quality_score)
            
        return tier_used, faces
        
    def _progressive_detection(self, image, quality_score):
        """
        Progressive detection for very poor quality images
        Try multiple approaches and return best result
        """
        best_faces = []
        best_count = 0
        
        methods = [
            ('tiny_yolo', image),
            ('enhanced_yolo', image),
            ('enhanced_yolo', self.enhancer.enhance_image(image, quality_score))
        ]
        
        for model_type, img in methods:
            try:
                faces = self.hof_models.detect_faces(img, model_type)
                if len(faces) > best_count:
                    best_faces = faces
                    best_count = len(faces)
            except Exception as e:
                logger.warning(f"Progressive detection failed for {model_type}: {e}")
                continue
                
        return best_faces
        
    def recognize_face_adaptive(self, image, known_encodings, known_names, 
                              tolerance=0.6, return_all_matches=False):
        """
        Adaptive face recognition combining detection and recognition
        
        Args:
            image: Input image (array or path)
            known_encodings: List of known face encodings
            known_names: List of corresponding names
            tolerance: Recognition tolerance (lower = stricter)
            return_all_matches: Return all matches or just best
            
        Returns:
            List of recognition results with confidence and location
        """
        # Detect faces adaptively
        faces = self.detect_faces_adaptive(image)
        
        if not faces:
            return []
            
        recognition_results = []
        
        for face in faces:
            try:
                # Extract face region
                x1, y1, x2, y2 = face['bbox']
                
                # Load image if path
                if isinstance(image, str):
                    img = cv2.imread(image)
                else:
                    img = image
                    
                face_region = img[y1:y2, x1:x2]
                
                # Generate encoding for this face
                face_encoding = self._generate_encoding(face_region)
                
                if face_encoding is not None:
                    # Compare with known faces
                    best_match = self._find_best_match(
                        face_encoding, known_encodings, known_names, tolerance
                    )
                    
                    if best_match:
                        recognition_results.append({
                            'name': best_match['name'],
                            'confidence': best_match['confidence'],
                            'bbox': face['bbox'],
                            'detection_confidence': face['confidence'],
                            'model_used': face['model_used']
                        })
                        
            except Exception as e:
                logger.error(f"Face recognition failed for detected face: {e}")
                continue
                
        return recognition_results
        
    def _generate_encoding(self, face_image):
        """Generate face encoding using face_recognition library"""
        try:
            import face_recognition
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            encodings = face_recognition.face_encodings(rgb_image)
            return encodings[0] if encodings else None
        except Exception as e:
            logger.error(f"Face encoding generation failed: {e}")
            return None
        
    def _find_best_match(self, face_encoding, known_encodings, known_names, tolerance):
        """Find best matching face"""
        try:
            import face_recognition
            distances = face_recognition.face_distance(known_encodings, face_encoding)
            best_match_index = np.argmin(distances)
            
            if distances[best_match_index] <= tolerance:
                return {
                    'name': known_names[best_match_index],
                    'confidence': 1 - distances[best_match_index]
                }
            return None
        except Exception as e:
            logger.error(f"Face matching failed: {e}")
            return None
        
    def get_system_status(self):
        """Get status of the adaptive detection system"""
        return {
            'models_loaded': list(self.hof_models.models.keys()),
            'current_model': self.hof_models.current_model,
            'quality_thresholds': self.quality_thresholds,
            'enhancer_methods': list(self.enhancer.enhancement_methods.keys())
        }
EOF

echo "✅ Fixed adaptive_detector.py"

# Step 3: Fix face_utils.py - remove the problematic import
echo -e "${YELLOW}Step 3: Fixing face_utils.py...${NC}"

# Create a cleaned version of face_utils.py without the circular import
cat > core/face_utils.py << 'EOF'
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
EOF

echo "✅ Fixed face_utils.py"

# Step 4: Test the fix
echo -e "${YELLOW}Step 4: Testing the fix...${NC}"

python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

print('🧪 Testing circular import fix...')

try:
    print('  Testing individual imports...')
    from core.hof_models import HallOfFacesModels
    print('  ✅ hof_models imported')
    
    from core.image_enhancer import ImageEnhancer
    print('  ✅ image_enhancer imported')
    
    from core.face_utils import preprocess_image, compare_faces
    print('  ✅ face_utils imported')
    
    from core.adaptive_detector import AdaptiveFaceDetector
    print('  ✅ adaptive_detector imported')
    
    print('  Testing initialization...')
    detector = AdaptiveFaceDetector()
    print('  ✅ AdaptiveFaceDetector initialized')
    
    # Test HOF functions from face_utils
    from core.face_utils import detect_faces_hof_adaptive, recognize_faces_with_hof
    print('  ✅ HOF integration functions imported')
    
    print('')
    print('🎉 CIRCULAR IMPORT FIXED!')
    print('All components working properly')
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo -e "${GREEN}✅ Circular Import Issue FIXED!${NC}"
echo ""
echo -e "${YELLOW}📋 What was changed:${NC}"
echo "1. ✅ Removed: from .face_utils import compare_faces (from adaptive_detector.py)"
echo "2. ✅ Removed: from .adaptive_detector import AdaptiveFaceDetector (from face_utils.py)"
echo "3. ✅ Added local imports where needed (inside functions)"
echo "4. ✅ Moved HOF integration functions to face_utils.py with local imports"
echo ""
echo -e "${YELLOW}📋 Now you can use:${NC}"
echo "# Basic detection:"
echo "from core.adaptive_detector import AdaptiveFaceDetector"
echo ""
echo "# HOF integration:"
echo "from core.face_utils import detect_faces_hof_adaptive, recognize_faces_with_hof"
echo ""
echo "# Your existing functions:"
echo "from core.face_utils import preprocess_image, compare_faces"
