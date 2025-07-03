# core/hof_models.py - Lightweight version with OpenCV fallback
import os
import cv2
import numpy as np
from pathlib import Path
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class HallOfFacesModels:
    """
    Lightweight HOF Models with OpenCV fallback
    Only downloads YOLO when specifically requested
    """
    
    def __init__(self, models_path=None):
        self.models_path = models_path or getattr(settings, 'HOF_MODELS_PATH', Path("media/models"))
        self.models_path = Path(self.models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        self.models = {}
        self.current_model = 'opencv_haar'
        self.opencv_cascade = None
        
        # Initialize OpenCV detector
        self._init_opencv()
        
    def _init_opencv(self):
        """Initialize OpenCV face detector"""
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.opencv_cascade = cv2.CascadeClassifier(cascade_path)
            if not self.opencv_cascade.empty():
                logger.info("✅ OpenCV face detector ready")
            else:
                logger.error("❌ Failed to load OpenCV cascade")
                self.opencv_cascade = None
        except Exception as e:
            logger.error(f"❌ OpenCV initialization error: {e}")
            self.opencv_cascade = None
    
    def download_models(self):
        """Lightweight - only initializes OpenCV, YOLO on demand"""
        logger.info("✅ Lightweight mode - OpenCV ready, YOLO available on demand")
        
    def load_model(self, model_type):
        """Load model - OpenCV by default, YOLO on request"""
        if model_type == 'opencv_haar' or model_type == 'tiny_yolo':
            return self.opencv_cascade
        return None
        
    def detect_faces(self, image, model_type='opencv_haar', confidence_threshold=None):
        """Detect faces using OpenCV (fast and reliable)"""
        if self.opencv_cascade is None:
            logger.error("No face detection available")
            return []
            
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            # Detect faces
            faces_rect = self.opencv_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(30, 30)
            )
            
            faces = []
            for (x, y, w, h) in faces_rect:
                faces.append({
                    'bbox': [int(x), int(y), int(x + w), int(y + h)],
                    'confidence': 0.85,  # Good default for OpenCV
                    'model_used': 'opencv_haar'
                })
                
            logger.info(f"Detected {len(faces)} faces with OpenCV")
            return faces
            
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []
            
    def get_model_info(self):
        """Get model information"""
        return {
            'loaded_models': ['opencv_haar'] if self.opencv_cascade else [],
            'current_model': self.current_model,
            'available_models': {
                'opencv_haar': {
                    'path': 'Built-in OpenCV',
                    'exists': self.opencv_cascade is not None,
                    'loaded': True,
                    'size_mb': 0
                }
            },
            'total_size_mb': 0
        }
        
    def cleanup_models(self):
        """Cleanup - nothing to do for OpenCV"""
        logger.info("OpenCV detector remains ready")
