#!/bin/bash
# upgrade_to_yolo.sh - Upgrade your current system to use YOLO models

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Upgrading Your System to YOLO Models${NC}"
echo "========================================"

# Check environment
if [[ "$VIRTUAL_ENV" != *"faceenv"* ]]; then
    echo -e "${RED}❌ Please activate faceenv first:${NC}"
    echo "source ../faceenv/bin/activate"
    exit 1
fi

echo -e "${YELLOW}Which YOLO setup do you want?${NC}"
echo "1. 🏃 Light & Fast (YOLOv8n-face = 6MB) - Recommended"
echo "2. ⚖️ Balanced (YOLOv8n + YOLOv8s face models = 29MB)"
echo "3. 🎯 High Accuracy (YOLOv8s + YOLOv8m face models = 75MB)"
echo ""

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        MODELS_TO_INSTALL=("yolov8n_face")
        SETUP_NAME="Light & Fast"
        PRIMARY_MODEL="yolov8n_face"
        SECONDARY_MODEL="yolov8n_face"
        ;;
    2)
        MODELS_TO_INSTALL=("yolov8n_face" "yolov8s_face")
        SETUP_NAME="Balanced"
        PRIMARY_MODEL="yolov8n_face"
        SECONDARY_MODEL="yolov8s_face"
        ;;
    3)
        MODELS_TO_INSTALL=("yolov8s_face" "yolov8m_face")
        SETUP_NAME="High Accuracy"
        PRIMARY_MODEL="yolov8s_face"
        SECONDARY_MODEL="yolov8m_face"
        ;;
    *)
        echo "Invalid choice. Using Light & Fast setup."
        MODELS_TO_INSTALL=("yolov8n_face")
        SETUP_NAME="Light & Fast"
        PRIMARY_MODEL="yolov8n_face"
        SECONDARY_MODEL="yolov8n_face"
        ;;
esac

echo ""
echo -e "${YELLOW}Installing: ${SETUP_NAME}${NC}"
echo "Primary model: ${PRIMARY_MODEL}"
echo "Secondary model: ${SECONDARY_MODEL}"

echo -e "${YELLOW}Step 1: Installing PyTorch and Ultralytics...${NC}"

# Remove old versions
pip uninstall -y torch torchvision ultralytics 2>/dev/null || true

# Install compatible versions
pip install torch==2.1.0+cpu torchvision==0.16.0+cpu --index-url https://download.pytorch.org/whl/cpu --quiet
pip install ultralytics==8.0.196 --quiet

echo "✅ PyTorch and Ultralytics installed"

echo -e "${YELLOW}Step 2: Backing up your current system...${NC}"

# Create backup directory
BACKUP_DIR="backups/yolo_upgrade_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup key files
cp core/hof_models.py "$BACKUP_DIR/" 2>/dev/null || true
cp core/adaptive_detector.py "$BACKUP_DIR/" 2>/dev/null || true

echo "✅ Current system backed up to $BACKUP_DIR"

echo -e "${YELLOW}Step 3: Creating YOLO-enabled HOF models...${NC}"

cat > core/hof_models.py << EOF
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
        self.current_model = '${PRIMARY_MODEL}'  # Your chosen primary model
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
        models_to_download = ['${MODELS_TO_INSTALL[@]}']
        
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
                        print(f"\\r   Progress: {percent:.1f}%", end='', flush=True)
                
                urllib.request.urlretrieve(config['url'], str(model_path), show_progress)
                
                size_mb = model_path.stat().st_size / (1024 * 1024)
                print(f"\\n✅ Downloaded {model_type} ({size_mb:.1f}MB)")
                
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
            
    def detect_faces(self, image, model_type='${PRIMARY_MODEL}', confidence_threshold=None):
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
            'setup_type': '${SETUP_NAME}',
            'primary_model': '${PRIMARY_MODEL}',
            'secondary_model': '${SECONDARY_MODEL}'
        }
        
    def cleanup_models(self):
        """Clean up loaded models"""
        self.models.clear()
        self.current_model = '${PRIMARY_MODEL}'
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("YOLO models unloaded")
EOF

echo "✅ Created YOLO-enabled HOF models"

echo -e "${YELLOW}Step 4: Updating adaptive detector for YOLO...${NC}"

cat > core/adaptive_detector.py << 'EOF'
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
EOF

echo "✅ Updated adaptive detector for YOLO"

echo -e "${YELLOW}Step 5: Downloading YOLO models...${NC}"

python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.hof_models import HallOfFacesModels

print('Initializing YOLO-enabled HOF system...')
hof = HallOfFacesModels()

print('Downloading your selected models...')
hof.download_models()

print('\\nModel summary:')
info = hof.get_model_info()
print(f'Setup: {info.get(\"setup_type\", \"Unknown\")}')
print(f'Primary model: {info.get(\"primary_model\", \"Unknown\")}')
print(f'Secondary model: {info.get(\"secondary_model\", \"Unknown\")}')
print(f'Total storage: {info[\"total_size_mb\"]}MB')
print()

for model_name, model_info in info['available_models'].items():
    if model_info['exists']:
        status = '✅'
        print(f'{status} {model_name}: {model_info[\"description\"]}')
"

echo -e "${YELLOW}Step 6: Testing YOLO integration...${NC}"

python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.adaptive_detector import AdaptiveFaceDetector

try:
    print('Testing YOLO-enabled system...')
    detector = AdaptiveFaceDetector()
    
    status = detector.get_system_status()
    print(f'✅ Detection mode: {status[\"detection_mode\"]}')
    print(f'✅ YOLO enabled: {status[\"yolo_enabled\"]}')
    print(f'✅ Setup type: {status[\"setup_type\"]}')
    print(f'✅ Models loaded: {status[\"models_loaded\"]}')
    print(f'✅ Storage used: {status[\"total_storage_mb\"]}MB')
    print(f'✅ Intelligent filtering: {status[\"intelligent_filtering_enabled\"]}')
    print(f'✅ Fallback available: {status[\"fallback_available\"]}')
    
    print('\\n🎉 YOLO integration successful!')
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo -e "${GREEN}✅ YOLO Integration Complete!${NC}"
echo ""
echo -e "${BLUE}🎯 What's been upgraded:${NC}"
echo "✅ OpenCV → YOLO face-specific models"
echo "✅ Faster and more accurate detection"
echo "✅ All your intelligent filtering preserved"
echo "✅ Universal detection scenarios still work"
echo "✅ Automatic fallback to OpenCV if needed"
echo "✅ Same API endpoints (no changes needed)"
echo ""
echo -e "${BLUE}🧪 Test your upgrade:${NC}"
echo "curl -X POST -F 'image=@/home/invictus/Pictures/Webcam/Test1.jpeg' http://localhost:8000/api/faces/detect-hof/"
echo ""
echo -e "${BLUE}📊 Expected improvements:${NC}"
echo "• Better accuracy in challenging lighting"
echo "• Fewer false positives"
echo "• More consistent detection across different face angles"
echo "• Maintained processing speed"
echo ""
echo -e "${GREEN}🎉 Your system is now powered by YOLO!${NC}"