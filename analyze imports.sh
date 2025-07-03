#!/bin/bash
# analyze_imports.sh - Check what imports what in your core files

echo "🔍 Analyzing Import Dependencies"
echo "================================"

echo -e "\n📄 Checking core/adaptive_detector.py imports:"
grep -n "^from \|^import " core/adaptive_detector.py 2>/dev/null || echo "File not found"

echo -e "\n📄 Checking core/face_utils.py imports:"
grep -n "^from \|^import " core/face_utils.py 2>/dev/null || echo "File not found"

echo -e "\n📄 Checking core/hof_models.py imports:"
grep -n "^from \|^import " core/hof_models.py 2>/dev/null || echo "File not found"

echo -e "\n📄 Checking core/image_enhancer.py imports:"
grep -n "^from \|^import " core/image_enhancer.py 2>/dev/null || echo "File not found"

echo -e "\n🔄 Looking for circular import patterns:"
echo "Files importing from each other:"

if grep -q "adaptive_detector" core/face_utils.py 2>/dev/null; then
    echo "  ❌ face_utils.py imports from adaptive_detector.py"
fi

if grep -q "face_utils" core/adaptive_detector.py 2>/dev/null; then
    echo "  ❌ adaptive_detector.py imports from face_utils.py"
fi

if grep -q "hof_models" core/adaptive_detector.py 2>/dev/null; then
    echo "  ✅ adaptive_detector.py imports from hof_models.py"
fi

if grep -q "image_enhancer" core/adaptive_detector.py 2>/dev/null; then
    echo "  ✅ adaptive_detector.py imports from image_enhancer.py"
fi
