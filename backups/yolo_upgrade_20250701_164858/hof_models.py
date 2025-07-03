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
    Downloads real YOLO models for enhanced accuracy
    """
    
    def __init__(self, models_path=None):
        self.models_path = models_path or getattr(settings, 'HOF_MODELS_PATH', Path("media/models"))
        self.models_path = Path(self.models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        # Real YOLO model configurations
        self.model_configs = {
            'tiny_yolo': {
                'model_name': 'yolov8n.pt',
                'url': 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt',
                'threshold': 0.25,
                'size': 640,
                'description': 'Nano model - fastest, ~6MB'
            },
            'enhanced_yolo': {
                'model_name': 'yolov8s.pt', 
                'url': 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt',
                'threshold': 0.4,
                'size': 640,
                'description': 'Small model - balanced, ~22MB'
            },
            'opencv_haar': {
                'model_name': 'haarcascade_frontalface_default.xml',
                'threshold': 1.1,
                'size': None,
                'builtin': True,
                'description': 'OpenCV Haar - lightweight, 0MB'
            }
        }
        
        self.models = {}
        self.current_model = 'opencv_haar'  # Start with OpenCV
        
        # Initialize OpenCV as fallback
        self.opencv_cascade = None
        self._init_opencv()
        
        # Track download status
        self.download_status = {}
        
    def _init_opencv(self):
        """Initialize OpenCV Haar cascade"""
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.opencv_cascade = cv2.CascadeClassifier(cascade_path)
            if not self.opencv_cascade.empty():
                logger.info("✅ OpenCV cascade loaded successfully")
            else:
                logger.error("❌ Failed to load OpenCV cascade")
                self.opencv_cascade = None
        except Exception as e:
            logger.error(f"OpenCV initialization failed: {e}")
            self.opencv_cascade = None
            
    def download_models(self, force_download=False):
        """Download YOLO models with progress tracking"""
        for model_type, config in self.model_configs.items():
            if config.get('builtin', False):
                continue  # Skip OpenCV
                
            model_path = self.models_path / config['model_name']
            
            if model_path.exists() and not force_download:
                size_mb = model_path.stat().st_size / (1024 * 1024)
                logger.info(f"✅ {model_type} already exists ({size_mb:.1f}MB)")
                self.download_status[model_type] = 'exists'
                continue
                
            logger.info(f"📥 Downloading {model_type}: {config['description']}")
            try:
                self.download_status[model_type] = 'downloading'
                
                # Download with progress
                def show_progress(block_num, block_size, total_size):
                    downloaded = block_num * block_size
                    if total_size > 0:
                        percent = min(100, (downloaded / total_size) * 100)
                        print(f"\r   Progress: {percent:.1f}%", end='', flush=True)
                
                urllib.request.urlretrieve(config['url'], str(model_path), show_progress)
                
                size_mb = model_path.stat().st_size / (1024 * 1024)
                print(f"\n✅ Downloaded {model_type} successfully ({size_mb:.1f}MB)")
                self.download_status[model_type] = 'complete'
                
            except Exception as e:
                logger.error(f"❌ Failed to download {model_type}: {e}")
                self.download_status[model_type] = 'failed'
                if model_path.exists():
                    model_path.unlink()  # Remove partial download
                    
    def load_model(self, model_type):
        """Load specific model (YOLO or OpenCV)"""
        if model_type == 'opencv_haar':
            return self.opencv_cascade
            
        if model_type in self.models:
            return self.models[model_type]
            
        if model_type not in self.model_configs:
            logger.error(f"Unknown model type: {model_type}")
            return None
            
        config = self.model_configs[model_type]
        model_path = self.models_path / config['model_name']
        
        if not model_path.exists():
            logger.warning(f"Model not found: {model_path}")
            return None
            
        try:
            # Load YOLO model
            model = YOLO(str(model_path))
            self.models[model_type] = model
            self.current_model = model_type
            logger.info(f"✅ Loaded YOLO {model_type} successfully")
            return model
            
        except Exception as e:
            logger.error(f"❌ Failed to load YOLO {model_type}: {e}")
            return None
            
    def detect_faces(self, image, model_type='tiny_yolo', confidence_threshold=None):
        """Detect faces using specified model"""
        
        if model_type == 'opencv_haar':
            return self._detect_with_opencv(image)
        else:
            # Try YOLO detection
            faces = self._detect_with_yolo(image, model_type, confidence_threshold)
            
            # Fallback to OpenCV if YOLO fails
            if not faces and self.opencv_cascade is not None:
                logger.info(f"YOLO {model_type} found no faces, trying OpenCV fallback...")
                faces = self._detect_with_opencv(image)
                
            return faces
            
    def _detect_with_yolo(self, image, model_type, confidence_threshold):
        """YOLO face detection"""
        model = self.load_model(model_type)
        if model is None:
            return []
            
        config = self.model_configs[model_type]
        threshold = confidence_threshold or config['threshold']
        
        try:
            # Run YOLO inference on person class (0)
            results = model(image, conf=threshold, imgsz=config['size'], classes=[0], verbose=False)
            
            faces = []
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        
                        # Filter for face-like proportions within person detections
                        width = x2 - x1
                        height = y2 - y1
                        aspect_ratio = width / height if height > 0 else 0
                        
                        # More lenient filtering for YOLO (it's more accurate)
                        if 0.4 <= aspect_ratio <= 2.5 and width > 20 and height > 20:
                            faces.append({
                                'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                'confidence': float(confidence),
                                'model_used': f'YOLO_{model_type}'
                            })
                            
            logger.info(f"YOLO {model_type} detected {len(faces)} faces")
            return faces
            
        except Exception as e:
            logger.error(f"YOLO {model_type} detection failed: {e}")
            return []
            
    def _detect_with_opencv(self, image):
        """OpenCV Haar cascade detection"""
        if self.opencv_cascade is None:
            return []
            
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            # Detect faces
            faces_rect = self.opencv_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            
            faces = []
            for (x, y, w, h) in faces_rect:
                faces.append({
                    'bbox': [int(x), int(y), int(x + w), int(y + h)],
                    'confidence': 0.85,  # Default confidence for OpenCV
                    'model_used': 'opencv_haar'
                })
                
            logger.info(f"OpenCV detected {len(faces)} faces")
            return faces
            
        except Exception as e:
            logger.error(f"OpenCV detection failed: {e}")
            return []
            
    def get_model_info(self):
        """Get comprehensive model information"""
        available_models = {}
        total_size = 0
        
        for model_type, config in self.model_configs.items():
            if config.get('builtin', False):
                available_models[model_type] = {
                    'description': config['description'],
                    'path': 'Built-in OpenCV',
                    'exists': self.opencv_cascade is not None,
                    'loaded': model_type in self.models,
                    'size_mb': 0,
                    'download_status': 'builtin'
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
                    'size_mb': size_mb,
                    'download_status': self.download_status.get(model_type, 'not_downloaded')
                }
                
        return {
            'loaded_models': list(self.models.keys()) + (['opencv_haar'] if self.opencv_cascade else []),
            'current_model': self.current_model,
            'available_models': available_models,
            'total_size_mb': total_size,
            'storage_usage': f"{total_size:.1f}MB / 10GB constraint"
        }
        
    def cleanup_models(self):
        """Clean up loaded models to free memory"""
        self.models.clear()
        self.current_model = 'opencv_haar'
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("YOLO models unloaded, using OpenCV")
