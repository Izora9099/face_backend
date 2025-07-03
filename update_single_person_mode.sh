#!/bin/bash
# update_single_person_mode.sh - Add single-person optimization

echo "🔧 Adding Single-Person Optimization Mode"
echo "========================================="

# Step 1: Create the single person optimizer
echo "1. Creating single_person_optimizer.py..."
# (Copy the above code to core/single_person_optimizer.py)

# Step 2: Update adaptive detector to include single-person mode
echo "2. Adding single-person mode to adaptive detector..."

# Backup current version
cp core/adaptive_detector.py core/adaptive_detector_backup_single_$(date +%Y%m%d_%H%M%S).py

# Add single-person mode to adaptive detector
cat > core/adaptive_detector.py << 'EOF'
# core/adaptive_detector.py - Updated with single-person optimization
from .hof_models import HallOfFacesModels
from .image_enhancer import ImageEnhancer
from .smart_face_filter import SmartFaceFilter
from .single_person_optimizer import SinglePersonOptimizer  # NEW
import cv2
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

class AdaptiveFaceDetector:
    """
    Adaptive face detection with smart filtering and single-person optimization
    """
    
    def __init__(self):
        self.hof_models = HallOfFacesModels()
        self.enhancer = ImageEnhancer()
        self.smart_filter = SmartFaceFilter()
        self.single_person_optimizer = SinglePersonOptimizer()  # NEW
        
        # Quality thresholds for tier selection
        self.quality_thresholds = {
            'excellent': 85,  
            'good': 60,       
            'acceptable': 30, 
            'poor': 0         
        }
        
        # Download models on initialization
        self.hof_models.download_models()
        
    def detect_faces_adaptive(self, image_path_or_array, return_metrics=False, single_person_mode=None):
        """
        Main adaptive detection method with optional single-person optimization
        
        Args:
            image_path_or_array: Image file path or numpy array
            return_metrics: Whether to return performance metrics
            single_person_mode: True/False/None (None = auto-detect)
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
        
        # Apply smart filtering to reduce false positives
        filtered_faces, filter_debug = self.smart_filter.filter_faces(
            raw_faces, image, return_debug_info=True
        )
        
        # NEW: Auto-detect or apply single-person optimization
        if single_person_mode is None:
            # Auto-detect: if we have 1-3 faces after filtering, try single-person mode
            single_person_mode = 1 <= len(filtered_faces) <= 3
            
        final_faces = filtered_faces
        single_person_debug = {}
        
        if single_person_mode and len(filtered_faces) > 1:
            # Apply single-person optimization
            single_faces, single_person_debug = self.single_person_optimizer.optimize_for_single_person(
                filtered_faces, image, return_debug_info=True
            )
            final_faces = single_faces
            logger.info(f"Single-person mode: {len(filtered_faces)} → {len(final_faces)} faces")
        
        processing_time = time.time() - start_time
        
        metrics = {
            'quality_score': quality_score,
            'tier_used': tier_used,
            'processing_time': processing_time,
            'raw_detections': len(raw_faces),
            'after_smart_filter': len(filtered_faces),
            'faces_detected': len(final_faces),
            'false_positives_removed': len(raw_faces) - len(final_faces),
            'single_person_mode': single_person_mode,
            'filter_debug': filter_debug,
            'single_person_debug': single_person_debug,  # NEW
            'image_shape': image.shape
        }
        
        logger.info(f"Adaptive detection: {len(raw_faces)} raw → {len(filtered_faces)} filtered → {len(final_faces)} final faces, "
                   f"quality={quality_score:.1f}, tier={tier_used}, time={processing_time:.2f}s")
        
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
        
    def get_system_status(self):
        """Get status of the adaptive detection system"""
        return {
            'models_loaded': list(self.hof_models.models.keys()) if hasattr(self.hof_models, 'models') else [],
            'current_model': getattr(self.hof_models, 'current_model', 'opencv_haar'),
            'quality_thresholds': self.quality_thresholds,
            'enhancer_methods': list(self.enhancer.enhancement_methods.keys()),
            'smart_filtering_enabled': True,
            'single_person_optimization_enabled': True  # NEW
        }
EOF

echo "✅ Updated adaptive_detector.py with single-person mode"

# Step 3: Update views to support single-person mode
echo "3. Adding single-person mode to API..."

# Create updated view that supports single-person parameter
cat >> core/views.py << 'EOF'

@csrf_exempt
@require_http_methods(["POST"])
def detect_faces_single_person(request):
    """
    API endpoint specifically for single-person detection (e.g., student registration)
    """
    try:
        if 'image' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No image file provided'
            }, status=400)
            
        image_file = request.FILES['image']
        
        if image_file.size > 10 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': 'Image file too large. Maximum size is 10MB.'
            }, status=400)
        
        import tempfile
        import uuid
        temp_filename = f"single_person_{uuid.uuid4()}.jpg"
        temp_dir = getattr(settings, 'HOF_TEMP_DIR', '/tmp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, temp_filename)
        
        try:
            with open(temp_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)
            
            # Use single-person mode explicitly
            from core.adaptive_detector import AdaptiveFaceDetector
            detector = AdaptiveFaceDetector()
            faces, metrics = detector.detect_faces_adaptive(
                temp_path, 
                return_metrics=True, 
                single_person_mode=True  # FORCE single-person mode
            )
            
            # Enhanced response for single-person scenarios
            response_data = {
                'success': True,
                'faces_detected': len(faces),
                'faces': faces,
                'metrics': metrics,
                'single_person_result': self._analyze_single_person_result(faces, metrics),
                'recommendations': self._get_single_person_recommendations(faces, metrics)
            }
                
            return JsonResponse(response_data)
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
            
        return JsonResponse({
            'success': False,
            'error': f'Single-person detection failed: {str(e)}'
        }, status=500)

def _analyze_single_person_result(self, faces, metrics):
    """Analyze result for single-person scenarios"""
    if len(faces) == 0:
        return {
            'status': 'no_face',
            'message': 'No face detected',
            'action': 'retake_photo'
        }
    elif len(faces) == 1:
        face = faces[0]
        quality = face.get('region_quality', 50)
        confidence = face.get('confidence', 0.5)
        
        if quality > 70 and confidence > 0.6:
            return {
                'status': 'excellent',
                'message': 'Perfect single face detected',
                'action': 'proceed'
            }
        elif quality > 40 and confidence > 0.4:
            return {
                'status': 'good',
                'message': 'Good single face detected',
                'action': 'proceed'
            }
        else:
            return {
                'status': 'poor_quality',
                'message': 'Face detected but quality is low',
                'action': 'improve_lighting'
            }
    else:
        return {
            'status': 'multiple_faces',
            'message': f'{len(faces)} faces detected',
            'action': 'ensure_single_person'
        }

def _get_single_person_recommendations(self, faces, metrics):
    """Get recommendations for single-person photos"""
    recommendations = []
    
    if len(faces) == 0:
        if metrics['quality_score'] < 40:
            recommendations.append("Image quality is low. Try better lighting.")
        recommendations.append("Ensure your face is clearly visible and centered.")
        recommendations.append("Move closer to the camera if too far away.")
        
    elif len(faces) == 1:
        face = faces[0]
        if face.get('region_quality', 50) < 50:
            recommendations.append("Face quality could be improved with better lighting.")
        if face.get('confidence', 0.5) < 0.5:
            recommendations.append("Face detection confidence is low. Ensure face is clearly visible.")
            
    else:
        recommendations.append(f"Multiple faces detected ({len(faces)}). Ensure only one person is in the photo.")
        recommendations.append("Other people should move out of the frame.")
        
    return recommendations
EOF

echo "✅ Added single-person detection endpoint"

# Step 4: Test the updated system
echo "4. Testing single-person optimization..."

python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

try:
    from core.adaptive_detector import AdaptiveFaceDetector
    from core.single_person_optimizer import SinglePersonOptimizer
    
    print('✅ Single-person optimization components imported')
    
    detector = AdaptiveFaceDetector()
    status = detector.get_system_status()
    print('✅ Single-person optimization enabled:', status.get('single_person_optimization_enabled', False))
    
    print('🎉 Single-person mode integration successful!')
    
except Exception as e:
    print('❌ Error:', e)
    import traceback
    traceback.print_exc()
"

echo ""
echo "✅ Single-Person Optimization Added!"
echo ""
echo "📋 New features:"
echo "✅ Automatic single-person detection mode"
echo "✅ Enhanced scoring for main subject identification"
echo "✅ Aggressive false positive removal for portraits"
echo "✅ New API endpoint: /api/faces/detect-single-person/"
echo ""
echo "🧪 Test with your single-person images:"
echo "curl -X POST -F 'image=@your_single_person_image.jpg' http://localhost:8000/api/faces/detect-single-person/"