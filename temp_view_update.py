# Add this to your core/views.py (replace the existing detect_faces_hof function)

@csrf_exempt
@require_http_methods(["POST"])
def detect_faces_hof(request):
    """
    Universal API endpoint for face detection
    Works correctly for any number of faces: 1, 2, 5, 10, 20+ people
    """
    try:
        if 'image' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No image file provided'
            }, status=400)
            
        image_file = request.FILES['image']
        
        if image_file.size > 10 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': 'Image file too large. Maximum size is 10MB.'
            }, status=400)
        
        import tempfile
        import uuid
        temp_filename = f"universal_detection_{uuid.uuid4()}.jpg"
        temp_dir = getattr(settings, 'HOF_TEMP_DIR', '/tmp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, temp_filename)
        
        try:
            with open(temp_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)
            
            # Universal detection
            from core.adaptive_detector import AdaptiveFaceDetector
            detector = AdaptiveFaceDetector()
            faces, metrics = detector.detect_faces_adaptive(temp_path, return_metrics=True)
            
            # Enhanced response for any scenario
            response_data = {
                'success': True,
                'faces_detected': len(faces),
                'faces': faces,
                'scenario': metrics['detection_scenario'],
                'strategy_used': metrics['strategy_used'],
                'image_context': metrics['image_context'],
                'metrics': {
                    'quality_score': metrics['quality_score'],
                    'tier_used': metrics['tier_used'],
                    'processing_time': round(metrics['processing_time'], 3),
                    'raw_detections': metrics['raw_detections'],
                    'image_shape': metrics['image_shape']
                },
                'analysis': _analyze_detection_result(faces, metrics),
                'recommendations': _get_universal_recommendations(faces, metrics)
            }
                
            return JsonResponse(response_data)
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
            
        return JsonResponse({
            'success': False,
            'error': f'Face detection failed: {str(e)}'
        }, status=500)

def _analyze_detection_result(faces, metrics):
    """Analyze the detection result and provide insights"""
    scenario = metrics['detection_scenario']
    face_count = len(faces)
    
    analysis = {
        'scenario': scenario,
        'face_count': face_count,
        'status': 'success',
        'confidence_level': 'high'
    }
    
    if face_count == 0:
        analysis.update({
            'status': 'no_faces_detected',
            'possible_reasons': ['poor lighting', 'no people in image', 'faces too small', 'faces not visible'],
            'confidence_level': 'certain'
        })
    elif scenario == 'single_person':
        face = faces[0]
        quality = face.get('region_quality', 50)
        if quality > 70:
            analysis['confidence_level'] = 'very_high'
        elif quality > 40:
            analysis['confidence_level'] = 'high'
        else:
            analysis['confidence_level'] = 'medium'
            
    elif scenario in ['pair', 'small_group']:
        avg_quality = sum(f.get('region_quality', 50) for f in faces) / len(faces)
        if avg_quality > 60:
            analysis['confidence_level'] = 'high'
        elif avg_quality > 40:
            analysis['confidence_level'] = 'medium'
        else:
            analysis['confidence_level'] = 'low'
            
    elif scenario in ['large_group', 'crowd']:
        analysis.update({
            'note': f'Large group detected with {face_count} people',
            'confidence_level': 'medium',
            'recommendation': 'Verify count manually for critical applications'
        })
    
    return analysis

def _get_universal_recommendations(faces, metrics):
    """Get recommendations based on the detection scenario"""
    scenario = metrics['detection_scenario']
    face_count = len(faces)
    quality_score = metrics['quality_score']
    
    recommendations = []
    
    if face_count == 0:
        if quality_score < 40:
            recommendations.append("Improve lighting conditions")
        recommendations.append("Ensure people are clearly visible")
        recommendations.append("Move closer to subjects if they appear too small")
        
    elif scenario == 'single_person':
        face = faces[0]
        if face.get('region_quality', 50) < 50:
            recommendations.append("Face quality could be improved with better lighting")
        recommendations.append("Perfect for individual identification/registration")
        
    elif scenario == 'pair':
        recommendations.append("Good for couple photos or pair identification")
        avg_quality = sum(f.get('region_quality', 50) for f in faces) / len(faces)
        if avg_quality < 50:
            recommendations.append("Consider better lighting for improved face quality")
            
    elif scenario in ['small_group', 'large_group']:
        recommendations.append(f"Group photo with {face_count} people detected")
        recommendations.append("Good for classroom attendance or group identification")
        if quality_score < 50:
            recommendations.append("Better lighting would improve individual face quality")
            
    elif scenario == 'crowd':
        recommendations.append(f"Large crowd with {face_count}+ people detected")
        recommendations.append("Suitable for event attendance or crowd analysis")
        recommendations.append("Individual face quality may vary in large groups")
        
    return recommendations
