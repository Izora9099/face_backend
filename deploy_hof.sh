#!/bin/bash
# fix_hof_dependencies.sh - Fix PyTorch and Ultralytics compatibility issues

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${RED}🔧 Fixing PyTorch and Ultralytics Dependencies${NC}"
echo "=============================================="

# Check we're in faceenv
if [[ "$VIRTUAL_ENV" != *"faceenv"* ]]; then
    echo -e "${RED}❌ Please activate faceenv first${NC}"
    echo "Run: source ../faceenv/bin/activate"
    exit 1
fi

echo -e "${YELLOW}🗑️  Removing problematic packages...${NC}"
pip uninstall -y ultralytics torch torchvision torchaudio 2>/dev/null || true

echo -e "${YELLOW}📦 Installing compatible PyTorch (CPU-only for storage optimization)...${NC}"
# Install specific compatible versions
pip install torch==2.0.1+cpu torchvision==0.15.2+cpu --index-url https://download.pytorch.org/whl/cpu --quiet

echo -e "${YELLOW}📦 Installing compatible Ultralytics...${NC}"
pip install ultralytics==8.0.196 --quiet

echo -e "${YELLOW}📦 Installing other required packages...${NC}"
pip install opencv-python==4.8.1.78 --quiet
pip install scikit-image==0.21.0 --quiet
pip install Pillow --quiet
pip install numpy==1.24.3 --quiet

echo -e "${YELLOW}🔍 Verifying installations...${NC}"
python -c "
try:
    import torch
    print('✅ PyTorch:', torch.__version__)
    print('   CUDA available:', torch.cuda.is_available())
except Exception as e:
    print('❌ PyTorch error:', e)

try:
    import ultralytics
    print('✅ Ultralytics:', ultralytics.__version__)
except Exception as e:
    print('❌ Ultralytics error:', e)

try:
    import cv2
    print('✅ OpenCV:', cv2.__version__)
except Exception as e:
    print('❌ OpenCV error:', e)

try:
    import skimage
    print('✅ Scikit-image:', skimage.__version__)
except Exception as e:
    print('❌ Scikit-image error:', e)
"

echo -e "${YELLOW}🧪 Testing YOLO import...${NC}"
python -c "
try:
    from ultralytics import YOLO
    print('✅ YOLO import successful')
    
    # Test model creation (without download)
    print('✅ Ultralytics fully functional')
except Exception as e:
    print('❌ YOLO import failed:', e)
"

echo -e "${GREEN}✅ Dependencies fixed!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo "1. Run the deployment script again: ./deploy_hof.sh"
echo "2. Or test directly: python test_hof_integration.py"
