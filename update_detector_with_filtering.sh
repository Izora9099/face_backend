#!/bin/bash
# update_detector_with_filtering.sh - Add smart filtering to your detector

echo "🔧 Adding Smart Face Filtering to Your HOF System"
echo "================================================="

# Step 1: Create the smart face filter
echo "Creating smart_face_filter.py..."
# (The smart filter code above should be saved as core/smart_face_filter.py)

# Step 2: Update adaptive_detector.py to use filtering
echo "Updating adaptive_detector.py..."

# Backup current version
cp core/adaptive_detector.py core/adaptive_detector_backup_$(date +%Y%m%d_%H%M%S).py

# Create updated version with smart filtering
cat > core/adaptive_detector.py << 'EOF'
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
EOF

echo "✅ Updated adaptive_detector.py with smart filtering"

# Step 3: Test the updated system
echo "Testing updated system..."

python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

try:
    from core.adaptive_detector import AdaptiveFaceDetector
    from core.smart_face_filter import SmartFaceFilter
    
    print('✅ Updated components imported successfully')
    
    detector = AdaptiveFaceDetector()
    print('✅ AdaptiveFaceDetector with smart filtering initialized')
    
    # Test system status
    status = detector.get_system_status()
    print('✅ Smart filtering enabled:', status.get('smart_filtering_enabled', False))
    
    print('🎉 Smart filtering integration successful!')
    
except Exception as e:
    print('❌ Error:', e)
    import traceback
    traceback.print_exc()
"

echo ""
echo "✅ Smart Face Filtering Added!"
echo ""
echo "📋 What's new:"
echo "✅ Filters out faces that are too small/large"
echo "✅ Removes detections with wrong aspect ratios"  
echo "✅ Reduces confidence for edge detections"
echo "✅ Analyzes face region quality"
echo "✅ Removes overlapping detections"
echo "✅ Limits to top 2 most confident faces"
echo ""
echo "🧪 Test with your problematic image:"
echo "curl -X POST -F 'image=@/home/invictus/Pictures/Webcam/Test1.jpeg' http://localhost:8000/api/faces/detect-hof/"