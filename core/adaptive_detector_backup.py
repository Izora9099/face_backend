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
