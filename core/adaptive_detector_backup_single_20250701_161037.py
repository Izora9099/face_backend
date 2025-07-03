# core/adaptive_detector.py - Updated with smart filtering
from .hof_models import HallOfFacesModels
from .image_enhancer import ImageEnhancer
from .smart_face_filter import SmartFaceFilter  # NEW: Smart filtering
import cv2
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

class AdaptiveFaceDetector:
    """
    Adaptive face detection with smart filtering to reduce false positives
    """
    
    def __init__(self):
        self.hof_models = HallOfFacesModels()
        self.enhancer = ImageEnhancer()
        self.smart_filter = SmartFaceFilter()  # NEW: Smart filtering
        
        # Quality thresholds for tier selection
        self.quality_thresholds = {
            'excellent': 85,  
            'good': 60,       
            'acceptable': 30, 
            'poor': 0         
        }
        
        # Download models on initialization
        self.hof_models.download_models()
        
    def detect_faces_adaptive(self, image_path_or_array, return_metrics=False):
        """
        Main adaptive detection method with smart filtering
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
        tier_used, raw_faces = self._select_and_execute_tier(image, quality_score)
        
        # NEW: Apply smart filtering to reduce false positives
        filtered_faces, filter_debug = self.smart_filter.filter_faces(
            raw_faces, image, return_debug_info=True
        )
        
        processing_time = time.time() - start_time
        
        metrics = {
            'quality_score': quality_score,
            'tier_used': tier_used,
            'processing_time': processing_time,
            'raw_detections': len(raw_faces),           # NEW: Before filtering
            'faces_detected': len(filtered_faces),      # NEW: After filtering
            'false_positives_removed': len(raw_faces) - len(filtered_faces),  # NEW
            'filter_debug': filter_debug,               # NEW: Filtering details
            'image_shape': image.shape
        }
        
        logger.info(f"Adaptive detection: {len(raw_faces)} raw → {len(filtered_faces)} filtered faces, "
                   f"quality={quality_score:.1f}, tier={tier_used}, time={processing_time:.2f}s")
        
        if return_metrics:
            return filtered_faces, metrics
        return filtered_faces
        
    def _select_and_execute_tier(self, image, quality_score):
        """Select appropriate detection tier and execute (unchanged)"""
        
        if quality_score >= self.quality_thresholds['excellent']:
            tier_used = 'tier_1_tiny_yolo'
            faces = self.hof_models.detect_faces(image, 'tiny_yolo')
            
        elif quality_score >= self.quality_thresholds['good']:
            tier_used = 'tier_2_enhanced_yolo'
            faces = self.hof_models.detect_faces(image, 'enhanced_yolo')
            
        elif quality_score >= self.quality_thresholds['acceptable']:
            tier_used = 'tier_3_preprocessing_enhanced'
            enhanced_image = self.enhancer.enhance_image(image, quality_score)
            faces = self.hof_models.detect_faces(enhanced_image, 'enhanced_yolo')
            
        else:
            tier_used = 'tier_4_progressive'
            faces = self._progressive_detection(image, quality_score)
            
        return tier_used, faces
        
    def _progressive_detection(self, image, quality_score):
        """Progressive detection for very poor quality images (unchanged)"""
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
        
    def get_system_status(self):
        """Get status of the adaptive detection system"""
        return {
            'models_loaded': list(self.hof_models.models.keys()) if hasattr(self.hof_models, 'models') else [],
            'current_model': getattr(self.hof_models, 'current_model', 'opencv_haar'),
            'quality_thresholds': self.quality_thresholds,
            'enhancer_methods': list(self.enhancer.enhancement_methods.keys()),
            'smart_filtering_enabled': True  # NEW
        }
