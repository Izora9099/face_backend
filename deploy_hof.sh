#!/bin/bash

# Quick Hall of Faces Setup for faceenv environment
# Specifically designed for your directory structure

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Hall of Faces Quick Setup${NC}"
echo -e "${BLUE}Environment: faceenv (parent directory)${NC}"
echo "============================================"

# Check we're in face_backend directory
if [ ! -f "manage.py" ]; then
    echo "❌ Please run this from your face_backend directory"
    exit 1
fi

# Activate faceenv
echo -e "${YELLOW}📦 Activating faceenv...${NC}"
if [ -d "../faceenv" ]; then
    source ../faceenv/bin/activate
    echo "✅ faceenv activated from parent directory"
    echo "📍 Using Python: $(which python)"
else
    echo "❌ faceenv not found in parent directory"
    exit 1
fi

# Quick dependency check and install
echo -e "${YELLOW}📦 Installing HOF dependencies...${NC}"
pip install ultralytics opencv-python torch torchvision scikit-image --quiet

# Verify key dependencies
echo -e "${YELLOW}🔍 Verifying installations...${NC}"
python -c "import ultralytics; print('✅ Ultralytics:', ultralytics.__version__)" 2>/dev/null || echo "⚠️  Ultralytics installation issue"
python -c "import cv2; print('✅ OpenCV:', cv2.__version__)" 2>/dev/null || echo "⚠️  OpenCV installation issue"
python -c "import torch; print('✅ PyTorch:', torch.__version__)" 2>/dev/null || echo "⚠️  PyTorch installation issue"

# Create directories
echo -e "${YELLOW}📁 Creating directories...${NC}"
mkdir -p media/models logs

# Quick settings update check
if grep -q "Hall of Faces Configuration" face_backend/settings.py 2>/dev/null; then
    echo "✅ HOF settings already configured"
else
    echo -e "${YELLOW}⚙️  Adding HOF settings...${NC}"
    cat >> face_backend/settings.py << 'EOF'

# Hall of Faces Configuration
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
HOF_MODELS_PATH = MEDIA_ROOT / 'models'
HOF_ENABLE_ADAPTIVE_DETECTION = True
EOF
    echo "✅ Basic HOF settings added"
fi

# Quick test
echo -e "${YELLOW}🧪 Quick integration test...${NC}"
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
django.setup()

try:
    from core.adaptive_detector import AdaptiveFaceDetector
    from core.hof_models import HallOfFacesModels
    from core.image_enhancer import ImageEnhancer
    print('✅ All HOF modules imported successfully')
    
    # Quick functionality test
    detector = AdaptiveFaceDetector()
    print('✅ AdaptiveFaceDetector initialized')
    
    enhancer = ImageEnhancer()
    print('✅ ImageEnhancer initialized')
    
    print('🎉 Hall of Faces integration is working!')
    
except ImportError as e:
    print(f'⚠️  Import issue: {e}')
    print('💡 Run the full deployment script for complete setup')
except Exception as e:
    print(f'⚠️  Setup issue: {e}')
    print('💡 Some components may need the full deployment script')
"

echo ""
echo -e "${GREEN}✅ Quick setup completed!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo "1. Run full deployment: ./deploy_hof.sh"
echo "2. Or run manual tests: python test_hof_integration.py"
echo "3. Add HOF URLs to core/urls.py"
echo ""
echo -e "${BLUE}🔧 For complete integration, run:${NC}"
echo "./deploy_hof.sh"
