# core/adaptive_detector.py - Universal intelligent face detection
from .hof_models import HallOfFacesModels
from .image_enhancer import ImageEnhancer
from .intelligent_face_detector import IntelligentFaceDetector  # NEW UNIVERSAL SYSTEM
import cv2
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

class AdaptiveFaceDetector:
    """
    Universal adaptive face detection system
    Correctly detects any number of faces: 1, 2, 5, 10, 20+ people
    Works for portraits, couples, groups, classrooms - any scenario
    """
    
    def __init__(self):
        self.hof_models = HallOfFacesModels()
        self.enhancer = ImageEnhancer()
        self.intelligent_detector = IntelligentFaceDetector()  # NEW UNIVERSAL SYSTEM
        
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
        Universal adaptive detection - works for ANY number of faces
        
        Args:
            image_path_or_array: Image file path or numpy array
            return_metrics: Whether to return performance metrics
            
        Returns:
            Correctly detected faces regardless of count (1, 2, 5, 10, etc.)
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
        
        # NEW: Apply universal intelligent detection
        final_faces, intelligent_debug = self.intelligent_detector.detect_optimal_faces(
            raw_faces, image, return_debug_info=True
        )
        
        processing_time = time.time() - start_time
        
        # Determine scenario based on results
        scenario = self._determine_scenario(final_faces, image, intelligent_debug)
        
        metrics = {
            'quality_score': quality_score,
            'tier_used': tier_used,
            'processing_time': processing_time,
            'raw_detections': len(raw_faces),
            'faces_detected': len(final_faces),
            'detection_scenario': scenario,
            'intelligent_debug': intelligent_debug,
            'image_shape': image.shape,
            'strategy_used': intelligent_debug.get('final_strategy', 'unknown'),
            'image_context': intelligent_debug.get('image_context', {})
        }
        
        logger.info(f"Universal detection: {len(raw_faces)} raw → {len(final_faces)} final faces "
                   f"({scenario} scenario, {intelligent_debug.get('final_strategy', 'unknown')} strategy), "
                   f"quality={quality_score:.1f}, time={processing_time:.2f}s")
        
        if return_metrics:
            return final_faces, metrics
        return final_faces
        
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
        
    def _determine_scenario(self, faces, image, debug_info):
        """Determine what type of scenario was detected"""
        face_count = len(faces)
        image_context = debug_info.get('image_context', {})
        likely_scenario = image_context.get('likely_scenario', 'unknown')
        
        if face_count == 0:
            return 'no_faces'
        elif face_count == 1:
            return 'single_person'
        elif face_count == 2:
            return 'pair'
        elif 3 <= face_count <= 5:
            return 'small_group'
        elif 6 <= face_count <= 15:
            return 'large_group'
        else:
            return 'crowd'
            
    def get_system_status(self):
        """Get status of the adaptive detection system"""
        return {
            'models_loaded': list(self.hof_models.models.keys()) if hasattr(self.hof_models, 'models') else [],
            'current_model': getattr(self.hof_models, 'current_model', 'opencv_haar'),
            'quality_thresholds': self.quality_thresholds,
            'enhancer_methods': list(self.enhancer.enhancement_methods.keys()),
            'detection_mode': 'universal_intelligent',
            'supports_scenarios': ['single_person', 'pair', 'small_group', 'large_group', 'crowd'],
            'strategies_available': ['conservative', 'balanced', 'aggressive']
        }
