import os
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class HallOfFacesModels:
    """
    Manages Hall of Faces YOLO models for face detection
    Implements 3-tier quality-based detection system
    """
    
    def __init__(self, models_path=None):
        self.models_path = models_path or Path("media/models")
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        # Model configurations for your 9GB constraint
        self.model_configs = {
            'tiny_yolo': {
                'model_name': 'yolov8n-face.pt',  # ~6MB
                'url': 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n-face.pt',
                'threshold': 0.25,
                'size': 640
            },
            'enhanced_yolo': {
                'model_name': 'yolov8s-face.pt',  # ~22MB
                'url': 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s-face.pt',
                'threshold': 0.4,
                'size': 640
            }
        }
        
        self.models = {}
        self.current_model = None
        
    def download_models(self):
        """Download required YOLO models if not present"""
        for model_type, config in self.model_configs.items():
            model_path = self.models_path / config['model_name']
            
            if not model_path.exists():
                logger.info(f"Downloading {model_type} model...")
                try:
                    # Download using ultralytics
                    model = YOLO(config['model_name'])
                    # Save to our models directory
                    model.save(str(model_path))
                    logger.info(f"Downloaded {model_type} model successfully")
                except Exception as e:
                    logger.error(f"Failed to download {model_type}: {e}")
                    
    def load_model(self, model_type='tiny_yolo'):
        """Load specified YOLO model"""
        if model_type not in self.model_configs:
            raise ValueError(f"Unknown model type: {model_type}")
            
        config = self.model_configs[model_type]
        model_path = self.models_path / config['model_name']
        
        if not model_path.exists():
            self.download_models()
            
        try:
            if model_type not in self.models:
                self.models[model_type] = YOLO(str(model_path))
                logger.info(f"Loaded {model_type} model")
            
            self.current_model = model_type
            return self.models[model_type]
            
        except Exception as e:
            logger.error(f"Failed to load {model_type}: {e}")
            return None
            
    def detect_faces(self, image, model_type='tiny_yolo', confidence_threshold=None):
        """
        Detect faces using specified YOLO model
        
        Args:
            image: numpy array (BGR format)
            model_type: 'tiny_yolo' or 'enhanced_yolo'
            confidence_threshold: override default threshold
            
        Returns:
            List of face detections with bounding boxes and confidence scores
        """
        model = self.load_model(model_type)
        if model is None:
            return []
            
        config = self.model_configs[model_type]
        threshold = confidence_threshold or config['threshold']
        
        try:
            # Run inference
            results = model(image, conf=threshold, imgsz=config['size'])
            
            faces = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Extract bounding box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        
                        faces.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': float(confidence),
                            'model_used': model_type
                        })
                        
            logger.info(f"Detected {len(faces)} faces using {model_type}")
            return faces
            
        except Exception as e:
            logger.error(f"Face detection failed with {model_type}: {e}")
            return []
            
    def get_model_info(self):
        """Get information about available models"""
        return {
            'loaded_models': list(self.models.keys()),
            'current_model': self.current_model,
            'model_configs': self.model_configs
        }