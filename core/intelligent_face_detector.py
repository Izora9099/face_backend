# core/intelligent_face_detector.py - Universal smart face detection

import cv2
import numpy as np
import logging
from collections import Counter

logger = logging.getLogger(__name__)

class IntelligentFaceDetector:
    """
    Universal intelligent face detector that correctly identifies the actual number of faces
    Works for single person, couples, groups, classrooms - any scenario
    """
    
    def __init__(self):
        self.detection_strategies = {
            'conservative': {'overlap_threshold': 0.3, 'quality_threshold': 20},
            'balanced': {'overlap_threshold': 0.4, 'quality_threshold': 15},
            'aggressive': {'overlap_threshold': 0.5, 'quality_threshold': 10}
        }
        
    def detect_optimal_faces(self, raw_faces, image, return_debug_info=False):
        """
        Intelligently determine the correct number of faces and return them
        
        Args:
            raw_faces: Raw detections from OpenCV/YOLO
            image: Original image
            return_debug_info: Return detailed debugging information
            
        Returns:
            List of correctly identified faces
        """
        if not raw_faces:
            return raw_faces if not return_debug_info else (raw_faces, {})
            
        debug_info = {
            'original_count': len(raw_faces),
            'analysis_steps': [],
            'strategies_tested': {},
            'final_strategy': None,
            'removed_faces': [],
            'confidence_adjustments': []
        }
        
        # Step 1: Initial quality filtering (remove obvious junk)
        quality_filtered = self._initial_quality_filter(raw_faces, image, debug_info)
        
        # Step 2: Test different strategies and find the most consistent one
        strategy_results = {}
        for strategy_name, params in self.detection_strategies.items():
            result = self._test_detection_strategy(quality_filtered, image, strategy_name, params)
            strategy_results[strategy_name] = result
            debug_info['strategies_tested'][strategy_name] = {
                'faces_found': len(result['faces']),
                'avg_quality': result['avg_quality'],
                'consistency_score': result['consistency_score']
            }
        
        # Step 3: Choose the best strategy based on image context
        best_strategy, final_faces = self._choose_optimal_strategy(
            strategy_results, image, quality_filtered, debug_info
        )
        
        # Step 4: Final confidence adjustment based on context
        final_faces = self._adjust_final_confidence(final_faces, image, debug_info)
        
        debug_info['final_strategy'] = best_strategy
        debug_info['final_count'] = len(final_faces)
        debug_info['analysis_steps'].append(f"Final result: {len(final_faces)} faces using {best_strategy} strategy")
        
        logger.info(f"Intelligent detection: {len(raw_faces)} raw → {len(final_faces)} final faces (strategy: {best_strategy})")
        
        if return_debug_info:
            return final_faces, debug_info
        return final_faces
        
    def _initial_quality_filter(self, faces, image, debug_info):
        """Remove obviously poor detections that are clearly not faces"""
        filtered_faces = []
        
        for face in faces:
            # Basic sanity checks
            bbox = face['bbox']
            x1, y1, x2, y2 = bbox
            
            # Check for valid bounding box
            if x2 <= x1 or y2 <= y1:
                debug_info['removed_faces'].append({'face': face, 'reason': 'Invalid bounding box'})
                continue
                
            face_width = x2 - x1
            face_height = y2 - y1
            
            # Remove tiny detections (likely noise)
            if face_width < 25 or face_height < 25:
                debug_info['removed_faces'].append({'face': face, 'reason': 'Too small (noise)'})
                continue
                
            # Remove huge detections (likely false positives)
            image_area = image.shape[0] * image.shape[1]
            face_area = face_width * face_height
            if face_area > image_area * 0.6:  # More than 60% of image
                debug_info['removed_faces'].append({'face': face, 'reason': 'Too large (likely false positive)'})
                continue
                
            # Check aspect ratio (faces shouldn't be extremely elongated)
            aspect_ratio = face_width / face_height if face_height > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 3.0:
                debug_info['removed_faces'].append({'face': face, 'reason': f'Bad aspect ratio: {aspect_ratio:.2f}'})
                continue
                
            filtered_faces.append(face)
            
        debug_info['analysis_steps'].append(f"Initial quality filter: {len(faces)} → {len(filtered_faces)}")
        return filtered_faces
        
    def _test_detection_strategy(self, faces, image, strategy_name, params):
        """Test a specific detection strategy and return results"""
        
        # Analyze face quality for this strategy
        face_qualities = []
        for face in faces:
            quality = self._analyze_face_region_quality(face, image)
            face['strategy_quality'] = quality
            face_qualities.append(quality)
            
        # Filter by quality threshold
        quality_threshold = params['quality_threshold']
        quality_filtered = [f for f in faces if f.get('strategy_quality', 0) >= quality_threshold]
        
        # Remove overlapping faces
        overlap_threshold = params['overlap_threshold']
        non_overlapping = self._remove_overlapping_faces(quality_filtered, overlap_threshold)
        
        # Calculate consistency metrics
        if face_qualities:
            avg_quality = sum(face_qualities) / len(face_qualities)
            quality_std = np.std(face_qualities) if len(face_qualities) > 1 else 0
            consistency_score = avg_quality - quality_std  # Higher is better
        else:
            avg_quality = 0
            consistency_score = 0
            
        return {
            'faces': non_overlapping,
            'avg_quality': avg_quality,
            'consistency_score': consistency_score,
            'quality_distribution': face_qualities
        }
        
    def _choose_optimal_strategy(self, strategy_results, image, original_faces, debug_info):
        """Choose the best strategy based on image context and results"""
        
        # Analyze image context
        image_context = self._analyze_image_context(image, original_faces)
        debug_info['image_context'] = image_context
        
        # Score each strategy
        strategy_scores = {}
        
        for strategy_name, result in strategy_results.items():
            score = 0
            faces_count = len(result['faces'])
            
            # Base score from consistency
            score += result['consistency_score'] * 0.4
            
            # Context-based scoring
            if image_context['likely_scenario'] == 'portrait' and faces_count == 1:
                score += 30  # Bonus for single face in portrait-like image
            elif image_context['likely_scenario'] == 'group' and faces_count >= 2:
                score += 20  # Bonus for multiple faces in group-like image
            elif image_context['likely_scenario'] == 'classroom' and faces_count >= 3:
                score += 25  # Bonus for many faces in classroom-like image
                
            # Penalize strategies that find too many faces for the image size
            expected_max_faces = max(1, int(image.shape[0] * image.shape[1] / 50000))  # Rough estimate
            if faces_count > expected_max_faces * 2:
                score -= 15  # Penalty for likely over-detection
                
            # Quality bonus
            if result['avg_quality'] > 60:
                score += 10
            elif result['avg_quality'] > 40:
                score += 5
                
            strategy_scores[strategy_name] = score
            debug_info['analysis_steps'].append(f"{strategy_name}: {faces_count} faces, score={score:.1f}")
        
        # Choose best strategy
        best_strategy = max(strategy_scores.keys(), key=lambda k: strategy_scores[k])
        best_result = strategy_results[best_strategy]
        
        return best_strategy, best_result['faces']
        
    def _analyze_image_context(self, image, faces):
        """Analyze image to understand the likely scenario"""
        height, width = image.shape[:2]
        aspect_ratio = width / height
        image_area = height * width
        
        context = {
            'aspect_ratio': aspect_ratio,
            'resolution': f"{width}x{height}",
            'area': image_area,
            'likely_scenario': 'unknown'
        }
        
        # Determine likely scenario
        if aspect_ratio > 0.7 and aspect_ratio < 1.3 and len(faces) <= 2:
            # Square-ish, few faces = likely portrait/selfie
            context['likely_scenario'] = 'portrait'
        elif aspect_ratio > 1.3 and len(faces) >= 3:
            # Wide image with multiple faces = likely group photo
            context['likely_scenario'] = 'group'
        elif image_area > 1000000 and len(faces) >= 5:
            # Large image with many faces = likely classroom/event
            context['likely_scenario'] = 'classroom'
        elif len(faces) == 2:
            # Two faces = likely couple/pair
            context['likely_scenario'] = 'pair'
        else:
            context['likely_scenario'] = 'general'
            
        return context
        
    def _remove_overlapping_faces(self, faces, overlap_threshold):
        """Remove overlapping face detections, keeping the best ones"""
        if len(faces) <= 1:
            return faces
            
        # Sort by quality and confidence
        sorted_faces = sorted(faces, key=lambda f: (
            f.get('strategy_quality', 0) * 0.6 + 
            f.get('confidence', 0) * 0.4
        ), reverse=True)
        
        kept_faces = []
        
        for face in sorted_faces:
            # Check if this face overlaps significantly with any kept face
            overlaps = False
            for kept_face in kept_faces:
                overlap_ratio = self._calculate_overlap_ratio(face['bbox'], kept_face['bbox'])
                if overlap_ratio > overlap_threshold:
                    overlaps = True
                    break
                    
            if not overlaps:
                kept_faces.append(face)
                
        return kept_faces
        
    def _calculate_overlap_ratio(self, bbox1, bbox2):
        """Calculate IoU (Intersection over Union) between two bounding boxes"""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        x1_int = max(x1_1, x1_2)
        y1_int = max(y1_1, y1_2)
        x2_int = min(x2_1, x2_2)
        y2_int = min(y2_1, y2_2)
        
        if x2_int <= x1_int or y2_int <= y1_int:
            return 0  # No overlap
            
        intersection = (x2_int - x1_int) * (y2_int - y1_int)
        
        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0
        
    def _analyze_face_region_quality(self, face, image):
        """Analyze the quality of a face region"""
        try:
            bbox = face['bbox']
            x1, y1, x2, y2 = bbox
            
            # Extract face region
            face_region = image[y1:y2, x1:x2]
            
            if face_region.size == 0:
                return 0
                
            # Convert to grayscale
            if len(face_region.shape) == 3:
                gray_face = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
            else:
                gray_face = face_region
                
            # Calculate quality metrics
            
            # 1. Contrast (faces should have reasonable contrast)
            contrast = np.std(gray_face)
            contrast_score = min(50, contrast)
            
            # 2. Edge density (faces have more edges than flat regions)
            edges = cv2.Canny(gray_face, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            edge_score = min(30, edge_density * 3000)
            
            # 3. Brightness distribution (not too dark/bright)
            mean_brightness = np.mean(gray_face)
            brightness_score = 20 - abs(mean_brightness - 127) * 0.15
            brightness_score = max(0, brightness_score)
            
            # Combine scores
            total_score = contrast_score + edge_score + brightness_score
            return max(0, min(100, total_score))
            
        except Exception as e:
            logger.warning(f"Face quality analysis failed: {e}")
            return 25  # Default medium score
            
    def _adjust_final_confidence(self, faces, image, debug_info):
        """Final confidence adjustment based on context"""
        if not faces:
            return faces
            
        # Adjust confidence based on relative quality
        if len(faces) > 1:
            qualities = [f.get('strategy_quality', 50) for f in faces]
            max_quality = max(qualities) if qualities else 50
            
            for face in faces:
                face_quality = face.get('strategy_quality', 50)
                relative_quality = face_quality / max_quality if max_quality > 0 else 1
                
                # Boost confidence for high relative quality
                original_confidence = face.get('confidence', 0.5)
                adjusted_confidence = original_confidence * (0.5 + 0.5 * relative_quality)
                face['confidence'] = min(0.99, adjusted_confidence)
                
                debug_info['confidence_adjustments'].append({
                    'face_index': faces.index(face),
                    'original_confidence': original_confidence,
                    'adjusted_confidence': adjusted_confidence,
                    'quality_factor': relative_quality
                })
        
        return faces