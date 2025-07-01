import cv2
import numpy as np
from core.adaptive_detector import AdaptiveFaceDetector

def test_integration():
    """Test Hall of Faces integration"""
    detector = AdaptiveFaceDetector()
    
    # Test with sample image (replace with actual test image)
    test_image_path = "path/to/test/image.jpg"
    
    print("Testing adaptive face detection...")
    faces, metrics = detector.detect_faces_adaptive(test_image_path, return_metrics=True)
    
    print(f"Results:")
    print(f"  Faces detected: {len(faces)}")
    print(f"  Quality score: {metrics['quality_score']:.1f}")
    print(f"  Tier used: {metrics['tier_used']}")
    print(f"  Processing time: {metrics['processing_time']:.2f}s")
    
    for i, face in enumerate(faces):
        print(f"  Face {i+1}: confidence={face['confidence']:.2f}, model={face['model_used']}")
    
    return len(faces) > 0

if __name__ == "__main__":
    success = test_integration()
    print(f"Integration test: {'PASSED' if success else 'FAILED'}")