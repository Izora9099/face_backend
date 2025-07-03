# core/adaptive_detector.py - Updated for YOLO models with intelligent filtering
from .hof_models import HallOfFacesModels
from .image_enhancer import ImageEnhancer
from .intelligent_face_detector import IntelligentFaceDetector
import cv2
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

class AdaptiveFaceDetector:
    """
    YOLO-powered adaptive face detection with intelligent filtering
    Seamlessly integrated with your existing smart systems
    """
    
    def __init__(self):
        self.hof_models = HallOfFacesModels()
        self.enhancer = ImageEnhancer()
        self.intelligent_detector = IntelligentFaceDetector()
        
        # Updated thresholds optimized for YOLO
        self.quality_thresholds = {
            'excellent': 85,  # Use fast YOLO model
            'good': 60,       # Use accurate YOLO model  
            'acceptable': 30, # Use preprocessing + YOLO
            'poor': 0         # Use all methods including fallback
        }
        
        # Download YOLO models
        self.hof_models.download_models()
        
    def detect_faces_adaptive(self, image_path_or_array, return_metrics=False):
        """
        YOLO-powered adaptive detection with your existing intelligence
        """
        start_time = time.time()
        
        # Load image
        if isinstance(image_path_or_array, str):
            image = cv2.imread(image_path_or_array)
            if image is None:
                logger.error(f"Could not load image: {image_path_or_array}")
                return [] if not return_metrics else ([], {})
        else:
            image = image_path_or_array.copy()
            
        # Assess image quality
        quality_score = self.enhancer.assess_image_quality(image)
        
        # Select YOLO tier based on quality
        tier_used, raw_faces = self._select_yolo_tier(image, quality_score)
        
        # Apply your existing intelligent filtering
        final_faces, intelligent_debug = self.intelligent_detector.detect_optimal_faces(
            raw_faces, image, return_debug_info=True
        )
        
        processing_time = time.time() - start_time
        
        # Determine scenario
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
            'yolo_enabled': True,
            'model_info': self.hof_models.get_model_info()
        }
        
        logger.info(f"YOLO adaptive detection: {len(raw_faces)} raw → {len(final_faces)} final faces "
                   f"({scenario}, {tier_used}), quality={quality_score:.1f}, time={processing_time:.2f}s")
        
        if return_metrics:
            return final_faces, metrics
        return final_faces
        
    def _select_yolo_tier(self, image, quality_score):
        """Select optimal YOLO model based on image quality"""
        
        model_info = self.hof_models.get_model_info()
        primary_model = model_info.get('primary_model', 'yolov8n_face')
        secondary_model = model_info.get('secondary_model', 'yolov8n_face')
        
        if quality_score >= self.quality_thresholds['excellent']:
            # Excellent quality: use fast model
            tier_used = f'tier_1_yolo_fast_{primary_model}'
            faces = self.hof_models.detect_faces(image, primary_model)
            
        elif quality_score >= self.quality_thresholds['good']:
            # Good quality: use accurate model
            tier_used = f'tier_2_yolo_accurate_{secondary_model}'
            faces = self.hof_models.detect_faces(image, secondary_model)
            
        elif quality_score >= self.quality_thresholds['acceptable']:
            # Acceptable quality: enhance then detect
            tier_used = f'tier_3_enhanced_yolo_{secondary_model}'
            enhanced_image = self.enhancer.enhance_image(image, quality_score)
            faces = self.hof_models.detect_faces(enhanced_image, secondary_model)
            
        else:
            # Poor quality: progressive detection with fallback
            tier_used = 'tier_4_progressive_yolo_fallback'
            faces = self._progressive_yolo_detection(image, quality_score, primary_model, secondary_model)
            
        return tier_used, faces
        
    def _progressive_yolo_detection(self, image, quality_score, primary_model, secondary_model):
        """Progressive detection: try YOLO models, fallback to OpenCV"""
        best_faces = []
        best_count = 0
        
        methods = [
            (primary_model, image),
            (secondary_model, image),
            (secondary_model, self.enhancer.enhance_image(image, quality_score)),
            ('opencv_haar', image)  # Final fallback
        ]
        
        for model_type, img in methods:
            try:
                faces = self.hof_models.detect_faces(img, model_type)
                if len(faces) > best_count:
                    best_faces = faces
                    best_count = len(faces)
                    if len(faces) > 0:  # Stop at first successful detection
                        break
            except Exception as e:
                logger.warning(f"Progressive detection failed for {model_type}: {e}")
                continue
                
        return best_faces
        
    def _determine_scenario(self, faces, image, debug_info):
        """Determine detection scenario (unchanged from your existing code)"""
        face_count = len(faces)
        
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
        """Get comprehensive system status"""
        model_info = self.hof_models.get_model_info()
        
        return {
            'detection_mode': 'yolo_intelligent_adaptive',
            'yolo_enabled': True,
            'models_loaded': model_info['loaded_models'],
            'current_model': model_info['current_model'],
            'setup_type': model_info.get('setup_type', 'Unknown'),
            'primary_model': model_info.get('primary_model', 'Unknown'),
            'secondary_model': model_info.get('secondary_model', 'Unknown'),
            'total_storage_mb': model_info['total_size_mb'],
            'quality_thresholds': self.quality_thresholds,
            'intelligent_filtering_enabled': True,
            'supports_scenarios': ['single_person', 'pair', 'small_group', 'large_group', 'crowd'],
            'fallback_available': model_info['available_models'].get('opencv_haar', {}).get('exists', False)
        }
