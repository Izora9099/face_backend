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
        ('/home/invictus/Pictures/Webcam/Test1.jpeg', 'Test1'),
        ('/home/invictus/Pictures/Webcam/Test2.jpeg', 'Test2'),  
        ('/home/invictus/Pictures/Webcam/Test3.jpg', 'Test3'),
        ('/home/invictus/Pictures/Webcam/Test4.jpg', 'Test4'),
        ('/home/invictus/Pictures/Webcam/Test5.jpg', 'Test5'),
        ('/home/invictus/Pictures/Webcam/Test6.png', 'Test6'),  
        ('/home/invictus/Pictures/Webcam/Test7.JPG', 'Test7'),
        ('/home/invictus/Pictures/Webcam/Test8.png', 'Test8'),
        ('/home/invictus/Pictures/Webcam/Test9.png', 'Test9'),
        ('/home/invictus/Pictures/Webcam/Test10.png', 'Test10'),  
        ('/home/invictus/Pictures/Webcam/Test11.png', 'Test11'),
        ('/home/invictus/Pictures/Webcam/Test12.png', 'Test12'),
        ('/home/invictus/Pictures/Webcam/Test13.png', 'Test13'),
        ('/home/invictus/Pictures/Webcam/Test14.png', 'Test14'),  
        ('/home/invictus/Pictures/Webcam/Test15.png', 'Test15'),
        

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
