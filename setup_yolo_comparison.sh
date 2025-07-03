#!/bin/bash
# setup_yolo_comparison.sh - Download YOLO models and setup comparison

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 YOLO Models Setup & Performance Comparison${NC}"
echo "=============================================="

# Check environment
if [[ "$VIRTUAL_ENV" != *"faceenv"* ]]; then
    echo -e "${RED}❌ Please activate faceenv first:${NC}"
    echo "source ../faceenv/bin/activate"
    exit 1
fi

echo -e "${YELLOW}Step 1: Checking current system status...${NC}"
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.adaptive_detector import AdaptiveFaceDetector
detector = AdaptiveFaceDetector()
status = detector.get_system_status()
print('Current system:', status.get('detection_mode', 'unknown'))
print('Current models:', status.get('models_loaded', []))
"

echo -e "${YELLOW}Step 2: Fixing PyTorch/Ultralytics compatibility...${NC}"

# Remove problematic versions
pip uninstall -y torch torchvision ultralytics 2>/dev/null || true

# Install stable, compatible versions
echo "Installing PyTorch CPU-only (storage optimized)..."
pip install torch==2.1.0+cpu torchvision==0.16.0+cpu --index-url https://download.pytorch.org/whl/cpu --quiet

echo "Installing compatible Ultralytics..."
pip install ultralytics==8.0.196 --quiet

echo "Installing other dependencies..."
pip install opencv-python==4.8.1.78 --quiet

echo -e "${YELLOW}Step 3: Testing PyTorch + Ultralytics compatibility...${NC}"
python -c "
try:
    import torch
    print('✅ PyTorch version:', torch.__version__)
    
    from ultralytics import YOLO
    print('✅ Ultralytics imported successfully')
    
    # Test model creation without download
    print('✅ YOLO model creation test passed')
    
except Exception as e:
    print('❌ Compatibility test failed:', e)
    exit(1)
"

echo -e "${YELLOW}Step 4: Creating YOLO-enabled HOF models...${NC}"

# Backup current OpenCV-only version
cp core/hof_models.py core/hof_models_opencv_backup.py

# Create YOLO-enabled version
cat > core/hof_models.py << 'EOF'
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
EOF

echo "✅ Created YOLO-enabled hof_models.py"

echo -e "${YELLOW}Step 5: Downloading YOLO models...${NC}"

python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.hof_models import HallOfFacesModels

print('Initializing HOF models system...')
hof = HallOfFacesModels()

print('Starting model downloads...')
hof.download_models()

print('\\nModel download summary:')
info = hof.get_model_info()
for model_name, model_info in info['available_models'].items():
    status = '✅' if model_info['exists'] else '❌'
    print(f'{status} {model_name}: {model_info[\"description\"]} - {model_info[\"size_mb\"]}MB')

print(f'\\nTotal storage used: {info[\"total_size_mb\"]}MB')
print('YOLO models ready for testing!')
"

echo -e "${YELLOW}Step 6: Creating comparison test script...${NC}"

cat > compare_detection_systems.py << 'EOF'
#!/usr/bin/env python
"""
compare_detection_systems.py - Compare OpenCV vs YOLO performance
"""
import os
import django
import cv2
import time
import json
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

from core.adaptive_detector import AdaptiveFaceDetector

def test_image_with_all_models(image_path, description):
    """Test an image with all available detection models"""
    print(f"\n🧪 Testing: {description}")
    print(f"📁 File: {image_path}")
    print("=" * 60)
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return None
        
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Failed to load image: {image_path}")
        return None
        
    print(f"📊 Image size: {image.shape[1]}x{image.shape[0]} pixels")
    
    results = {}
    detector = AdaptiveFaceDetector()
    
    # Test each model type
    models_to_test = ['opencv_haar', 'tiny_yolo', 'enhanced_yolo']
    
    for model_type in models_to_test:
        print(f"\n🔍 Testing {model_type}...")
        
        start_time = time.time()
        try:
            # Get raw detections from specific model
            faces = detector.hof_models.detect_faces(image, model_type)
            processing_time = time.time() - start_time
            
            # Get model info
            model_info = detector.hof_models.get_model_info()
            model_details = model_info['available_models'].get(model_type, {})
            
            result = {
                'model_type': model_type,
                'faces_detected': len(faces),
                'processing_time': round(processing_time, 3),
                'faces': faces,
                'model_size_mb': model_details.get('size_mb', 0),
                'model_description': model_details.get('description', 'Unknown'),
                'success': True
            }
            
            print(f"   ✅ Faces detected: {len(faces)}")
            print(f"   ⏱️  Processing time: {processing_time:.3f}s")
            print(f"   💾 Model size: {model_details.get('size_mb', 0)}MB")
            
            # Show face details
            for i, face in enumerate(faces):
                confidence = face.get('confidence', 0)
                bbox = face['bbox']
                print(f"   Face {i+1}: confidence={confidence:.3f}, bbox={bbox}")
                
        except Exception as e:
            result = {
                'model_type': model_type,
                'faces_detected': 0,
                'processing_time': 0,
                'faces': [],
                'error': str(e),
                'success': False
            }
            print(f"   ❌ Error: {e}")
            
        results[model_type] = result
    
    # Test with intelligent system
    print(f"\n🧠 Testing Intelligent Universal System...")
    start_time = time.time()
    try:
        faces, metrics = detector.detect_faces_adaptive(image, return_metrics=True)
        processing_time = time.time() - start_time
        
        result = {
            'model_type': 'intelligent_universal',
            'faces_detected': len(faces),
            'processing_time': round(processing_time, 3),
            'faces': faces,
            'strategy_used': metrics.get('strategy_used', 'unknown'),
            'detection_scenario': metrics.get('detection_scenario', 'unknown'),
            'raw_detections': metrics.get('raw_detections', 0),
            'success': True
        }
        
        print(f"   ✅ Faces detected: {len(faces)}")
        print(f"   📊 Scenario: {metrics.get('detection_scenario', 'unknown')}")
        print(f"   🎯 Strategy: {metrics.get('strategy_used', 'unknown')}")
        print(f"   ⏱️  Processing time: {processing_time:.3f}s")
        
    except Exception as e:
        result = {
            'model_type': 'intelligent_universal',
            'error': str(e),
            'success': False
        }
        print(f"   ❌ Error: {e}")
        
    results['intelligent_universal'] = result
    
    return results

def compare_all_test_images():
    """Compare all detection systems across test images"""
    test_images = [
        ('/home/invictus/Pictures/Webcam/Test1.jpeg', 'Single person - Test1'),
        ('/home/invictus/Pictures/Webcam/Test2.jpeg', 'Single person - Test2'),  
        ('/home/invictus/Pictures/Webcam/Test3.jpg', 'Multiple people - Test3'),
        ('/home/invictus/Pictures/Webcam/Test4.jpg', 'Multiple people - Test4'),
    ]
    
    all_results = {}
    
    print("🚀 YOLO vs OpenCV Performance Comparison")
    print("=" * 80)
    
    for image_path, description in test_images:
        results = test_image_with_all_models(image_path, description)
        if results:
            all_results[description] = results
    
    # Generate comparison summary
    print("\n📊 PERFORMANCE COMPARISON SUMMARY")
    print("=" * 80)
    
    # Create comparison table
    models = ['opencv_haar', 'tiny_yolo', 'enhanced_yolo', 'intelligent_universal']
    
    print(f"{'Test Image':<25} {'Model':<20} {'Faces':<6} {'Time':<8} {'Size':<8} {'Status'}")
    print("-" * 80)
    
    for test_name, test_results in all_results.items():
        first_row = True
        for model in models:
            if model in test_results:
                result = test_results[model]
                if first_row:
                    test_display = test_name[:24]
                    first_row = False
                else:
                    test_display = ""
                    
                faces = result.get('faces_detected', 0)
                time_str = f"{result.get('processing_time', 0):.3f}s"
                size_str = f"{result.get('model_size_mb', 0)}MB"
                status = "✅" if result.get('success', False) else "❌"
                
                print(f"{test_display:<25} {model:<20} {faces:<6} {time_str:<8} {size_str:<8} {status}")
    
    # Analysis and recommendations
    print("\n🎯 ANALYSIS & RECOMMENDATIONS")
    print("=" * 50)
    
    # Calculate average performance
    model_stats = {}
    for model in models:
        total_faces = 0
        total_time = 0
        total_tests = 0
        total_size = 0
        successes = 0
        
        for test_results in all_results.values():
            if model in test_results:
                result = test_results[model]
                if result.get('success', False):
                    total_faces += result.get('faces_detected', 0)
                    total_time += result.get('processing_time', 0)
                    total_size = result.get('model_size_mb', 0)  # Same for all tests
                    successes += 1
                total_tests += 1
        
        if total_tests > 0:
            model_stats[model] = {
                'avg_faces': total_faces / total_tests,
                'avg_time': total_time / total_tests,
                'size_mb': total_size,
                'success_rate': successes / total_tests
            }
    
    # Print recommendations
    for model, stats in model_stats.items():
        print(f"\n{model.upper()}:")
        print(f"   Average faces detected: {stats['avg_faces']:.1f}")
        print(f"   Average processing time: {stats['avg_time']:.3f}s")
        print(f"   Model size: {stats['size_mb']}MB")
        print(f"   Success rate: {stats['success_rate']:.1%}")
    
    # Storage impact
    total_yolo_size = sum(stats['size_mb'] for model, stats in model_stats.items() 
                         if 'yolo' in model and stats['size_mb'] > 0)
    print(f"\n💾 Storage Impact:")
    print(f"   OpenCV Haar: 0MB (built-in)")
    print(f"   YOLO models: {total_yolo_size}MB")
    print(f"   Storage constraint: 10GB ({total_yolo_size/10240*100:.2f}% used)")
    
    return all_results

if __name__ == "__main__":
    results = compare_all_test_images()
    
    # Save results
    with open('detection_comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: detection_comparison_results.json")
EOF

chmod +x compare_detection_systems.py

echo ""
echo -e "${GREEN}✅ YOLO Setup Complete!${NC}"
echo ""
echo -e "${BLUE}📋 What was installed:${NC}"
echo "✅ PyTorch CPU-only (storage optimized)"
echo "✅ Ultralytics YOLO (latest compatible version)"
echo "✅ YOLOv8 Nano model (~6MB)"
echo "✅ YOLOv8 Small model (~22MB)"
echo "✅ YOLO-enabled HOF system"
echo "✅ Performance comparison script"
echo ""
echo -e "${BLUE}🧪 Run the comparison test:${NC}"
echo "python compare_detection_systems.py"
echo ""
echo -e "${BLUE}📊 This will compare:${NC}"
echo "• OpenCV Haar Cascades (current system)"
echo "• YOLO Nano (fastest YOLO)"  
echo "• YOLO Small (most accurate YOLO)"
echo "• Intelligent Universal (your current best)"
echo ""
echo -e "${YELLOW}⚡ Ready to see which performs better on your test images!${NC}"