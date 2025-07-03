# core/hof_models.py - YOLO-enabled with OpenCV fallback
import os
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from pathlib import Path
import logging
import urllib.request
from django.conf import settings

logger = logging.getLogger(__name__)

class HallOfFacesModels:
    """
    YOLO-enabled face detection with OpenCV fallback
    Optimized for your current intelligent system
    """
    
    def __init__(self, models_path=None):
        self.models_path = models_path or getattr(settings, 'HOF_MODELS_PATH', Path("media/models"))
        self.models_path = Path(self.models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        # YOLO model configurations for your setup
        self.model_configs = {
            'yolov8n_face': {
                'model_name': 'yolov8n-face.pt',
                'url': 'https://github.com/derronqi/yolov8-face/releases/download/v0.0.0/yolov8n-face.pt',
                'threshold': 0.25,
                'size': 640,
                'description': 'YOLOv8 Nano Face (6MB) - Fast and accurate'
            },
            'yolov8s_face': {
                'model_name': 'yolov8s-face.pt',
                'url': 'https://github.com/derronqi/yolov8-face/releases/download/v0.0.0/yolov8s-face.pt',
                'threshold': 0.3,
                'size': 640,
                'description': 'YOLOv8 Small Face (23MB) - High accuracy'
            },
            'yolov8m_face': {
                'model_name': 'yolov8m-face.pt',
                'url': 'https://github.com/derronqi/yolov8-face/releases/download/v0.0.0/yolov8m-face.pt',
                'threshold': 0.35,
                'size': 640,
                'description': 'YOLOv8 Medium Face (52MB) - Maximum accuracy'
            },
            'opencv_haar': {
                'model_name': 'haarcascade_frontalface_default.xml',
                'threshold': 1.1,
                'size': None,
                'builtin': True,
                'description': 'OpenCV Haar (0MB) - Fallback method'
            }
        }
        
        self.models = {}
        self.current_model = 'yolov8n_face'  # Your chosen primary model
        self.download_status = {}
        
        # Keep OpenCV as fallback
        self.opencv_cascade = None
        self._init_opencv()
        
    def _init_opencv(self):
        """Initialize OpenCV as fallback"""
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.opencv_cascade = cv2.CascadeClassifier(cascade_path)
            if not self.opencv_cascade.empty():
                logger.info("✅ OpenCV fallback ready")
        except Exception as e:
            logger.warning(f"OpenCV fallback unavailable: {e}")
            self.opencv_cascade = None
            
    def download_models(self):
        """Download your selected YOLO models"""
        models_to_download = ['yolov8n_face']
        
        for model_type in models_to_download:
            if model_type not in self.model_configs:
                continue
                
            config = self.model_configs[model_type]
            model_path = self.models_path / config['model_name']
            
            if model_path.exists():
                size_mb = model_path.stat().st_size / (1024 * 1024)
                logger.info(f"✅ {model_type} already exists ({size_mb:.1f}MB)")
                continue
                
            logger.info(f"📥 Downloading {model_type}: {config['description']}")
            try:
                def show_progress(block_num, block_size, total_size):
                    if total_size > 0:
                        downloaded = block_num * block_size
                        percent = min(100, (downloaded / total_size) * 100)
                        print(f"\r   Progress: {percent:.1f}%", end='', flush=True)
                
                urllib.request.urlretrieve(config['url'], str(model_path), show_progress)
                
                size_mb = model_path.stat().st_size / (1024 * 1024)
                print(f"\n✅ Downloaded {model_type} ({size_mb:.1f}MB)")
                
            except Exception as e:
                logger.error(f"❌ Failed to download {model_type}: {e}")
                if model_path.exists():
                    model_path.unlink()
                    
    def load_model(self, model_type):
        """Load YOLO or OpenCV model"""
        if model_type == 'opencv_haar':
            return self.opencv_cascade
            
        if model_type in self.models:
            return self.models[model_type]
            
        if model_type not in self.model_configs:
            logger.error(f"Unknown model: {model_type}")
            return None
            
        config = self.model_configs[model_type]
        model_path = self.models_path / config['model_name']
        
        if not model_path.exists():
            logger.warning(f"Model not found: {model_path}")
            return None
            
        try:
            model = YOLO(str(model_path))
            self.models[model_type] = model
            self.current_model = model_type
            logger.info(f"✅ Loaded YOLO {model_type}")
            return model
        except Exception as e:
            logger.error(f"❌ Failed to load {model_type}: {e}")
            return None
            
    def detect_faces(self, image, model_type='yolov8n_face', confidence_threshold=None):
        """Detect faces with YOLO (fallback to OpenCV if needed)"""
        
        # Try YOLO first
        if model_type != 'opencv_haar':
            faces = self._detect_with_yolo(image, model_type, confidence_threshold)
            if faces:  # YOLO found faces
                return faces
                
        # Fallback to OpenCV if YOLO fails or finds nothing
        if self.opencv_cascade is not None:
            logger.info(f"Using OpenCV fallback for {model_type}")
            return self._detect_with_opencv(image)
        
        return []
        
    def _detect_with_yolo(self, image, model_type, confidence_threshold):
        """YOLO face detection"""
        model = self.load_model(model_type)
        if model is None:
            return []
            
        config = self.model_configs[model_type]
        threshold = confidence_threshold or config['threshold']
        
        try:
            # Run YOLO inference (face-specific models detect faces directly)
            results = model(image, conf=threshold, imgsz=config['size'], verbose=False)
            
            faces = []
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        
                        # Basic filtering for reasonable faces
                        width = x2 - x1
                        height = y2 - y1
                        aspect_ratio = width / height if height > 0 else 0
                        
                        if 0.3 <= aspect_ratio <= 3.0 and width > 15 and height > 15:
                            faces.append({
                                'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                'confidence': float(confidence),
                                'model_used': f'YOLO_{model_type}'
                            })
                            
            logger.info(f"YOLO {model_type} detected {len(faces)} faces")
            return faces
            
        except Exception as e:
            logger.error(f"YOLO {model_type} failed: {e}")
            return []
            
    def _detect_with_opencv(self, image):
        """OpenCV fallback detection"""
        if self.opencv_cascade is None:
            return []
            
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            faces_rect = self.opencv_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            
            faces = []
            for (x, y, w, h) in faces_rect:
                faces.append({
                    'bbox': [int(x), int(y), int(x + w), int(y + h)],
                    'confidence': 0.85,
                    'model_used': 'opencv_fallback'
                })
                
            logger.info(f"OpenCV fallback detected {len(faces)} faces")
            return faces
            
        except Exception as e:
            logger.error(f"OpenCV fallback failed: {e}")
            return []
            
    def get_model_info(self):
        """Get model information"""
        available_models = {}
        total_size = 0
        
        for model_type, config in self.model_configs.items():
            if config.get('builtin', False):
                available_models[model_type] = {
                    'description': config['description'],
                    'path': 'Built-in OpenCV',
                    'exists': self.opencv_cascade is not None,
                    'loaded': True,
                    'size_mb': 0
                }
            else:
                model_path = self.models_path / config['model_name']
                size_mb = round(model_path.stat().st_size / (1024*1024), 1) if model_path.exists() else 0
                total_size += size_mb
                
                available_models[model_type] = {
                    'description': config['description'],
                    'path': str(model_path),
                    'exists': model_path.exists(),
                    'loaded': model_type in self.models,
                    'size_mb': size_mb
                }
                
        return {
            'loaded_models': list(self.models.keys()) + (['opencv_haar'] if self.opencv_cascade else []),
            'current_model': self.current_model,
            'available_models': available_models,
            'total_size_mb': total_size,
            'setup_type': 'Light & Fast',
            'primary_model': 'yolov8n_face',
            'secondary_model': 'yolov8n_face'
        }
        
    def cleanup_models(self):
        """Clean up loaded models"""
        self.models.clear()
        self.current_model = 'yolov8n_face'
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("YOLO models unloaded")
