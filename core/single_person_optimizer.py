# core/single_person_optimizer.py - Enhanced filtering for single-person photos

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SinglePersonOptimizer:
    """
    Enhanced filtering specifically for single-person photos
    Aggressively removes false positives when expecting one face
    """
    
    def __init__(self):
        self.single_person_mode = True
        
    def optimize_for_single_person(self, faces, image, return_debug_info=False):
        """
        Optimize face detections for single-person scenarios
        
        Args:
            faces: List of detected faces
            image: Original image
            return_debug_info: Return debugging information
            
        Returns:
            Single best face or empty list
        """
        if not faces:
            return faces
            
        debug_info = {
            'original_faces': len(faces),
            'optimization_steps': [],
            'removed_faces': []
        }
        
        # Step 1: If only one face, check if it's good enough
        if len(faces) == 1:
            face = faces[0]
            if face.get('region_quality', 50) > 30 and face.get('confidence', 0) > 0.3:
                debug_info['optimization_steps'].append("Single face detected - quality check passed")
                if return_debug_info:
                    return faces, debug_info
                return faces
        
        # Step 2: Multiple faces detected - find the best one
        debug_info['optimization_steps'].append(f"Multiple faces detected ({len(faces)}) - finding best single face")
        
        # Step 3: Score each face for single-person likelihood
        scored_faces = []
        for i, face in enumerate(faces):
            score = self._calculate_single_person_score(face, image, i)
            scored_faces.append((score, face))
            debug_info['optimization_steps'].append(f"Face {i}: score={score:.2f}")
        
        # Step 4: Sort by score and analyze top candidates
        scored_faces.sort(key=lambda x: x[0], reverse=True)
        
        # Step 5: Apply single-person criteria
        best_face = self._select_best_single_face(scored_faces, image, debug_info)
        
        if return_debug_info:
            return [best_face] if best_face else [], debug_info
        return [best_face] if best_face else []
        
    def _calculate_single_person_score(self, face, image, face_index):
        """
        Calculate how likely this face is to be the main person in a single-person photo
        """
        score = 0
        
        # Base quality and confidence
        region_quality = face.get('region_quality', 50)
        confidence = face.get('confidence', 0.5)
        
        # Quality component (0-40 points)
        score += min(40, region_quality * 0.4)
        
        # Confidence component (0-20 points)  
        score += confidence * 20
        
        # Size component (0-20 points) - larger faces more likely to be main subject
        bbox = face['bbox']
        x1, y1, x2, y2 = bbox
        face_area = (x2 - x1) * (y2 - y1)
        image_area = image.shape[0] * image.shape[1]
        area_ratio = face_area / image_area
        
        # Optimal size for single person: 5-30% of image
        if 0.05 <= area_ratio <= 0.30:
            score += 20  # Perfect size
        elif 0.03 <= area_ratio <= 0.50:
            score += 15  # Good size
        elif area_ratio > 0.50:
            score += 5   # Too large (might be close-up or false positive)
        else:
            score += 2   # Too small (likely false positive)
            
        # Position component (0-10 points) - centered faces more likely
        image_height, image_width = image.shape[:2]
        face_center_x = (x1 + x2) / 2
        face_center_y = (y1 + y2) / 2
        
        # Distance from image center
        center_distance = np.sqrt(
            ((face_center_x - image_width/2) / image_width)**2 + 
            ((face_center_y - image_height/2) / image_height)**2
        )
        
        # Closer to center = higher score
        position_score = max(0, 10 * (1 - center_distance * 2))
        score += position_score
        
        # Aspect ratio component (0-10 points) - face-like ratios
        face_width = x2 - x1
        face_height = y2 - y1
        aspect_ratio = face_width / face_height if face_height > 0 else 0
        
        if 0.8 <= aspect_ratio <= 1.2:
            score += 10  # Perfect face ratio
        elif 0.6 <= aspect_ratio <= 1.4:
            score += 7   # Good face ratio
        else:
            score += 2   # Poor ratio (likely false positive)
            
        return score
        
    def _select_best_single_face(self, scored_faces, image, debug_info):
        """
        Select the single best face using strict criteria
        """
        if not scored_faces:
            return None
            
        best_score, best_face = scored_faces[0]
        
        # Minimum thresholds for single-person detection
        min_score = 60  # Out of 100
        min_quality = 40
        min_confidence = 0.2
        
        # Check if best face meets minimum criteria
        if (best_score >= min_score and 
            best_face.get('region_quality', 0) >= min_quality and
            best_face.get('confidence', 0) >= min_confidence):
            
            debug_info['optimization_steps'].append(f"Best face selected: score={best_score:.2f}")
            
            # Check for significant gap between best and second-best
            if len(scored_faces) > 1:
                second_score, second_face = scored_faces[1]
                score_gap = best_score - second_score
                
                if score_gap < 15:  # Too close - might be ambiguous
                    debug_info['optimization_steps'].append(f"Score gap too small ({score_gap:.2f}) - applying additional criteria")
                    
                    # Additional criteria when scores are close
                    best_area = self._get_face_area(best_face)
                    second_area = self._get_face_area(second_face)
                    
                    # Prefer larger face if scores are close
                    if second_area > best_area * 1.5:
                        debug_info['optimization_steps'].append("Switching to larger face due to close scores")
                        return second_face
                        
            return best_face
        else:
            debug_info['optimization_steps'].append(f"Best face rejected: score={best_score:.2f}, quality={best_face.get('region_quality', 0):.1f}")
            return None
            
    def _get_face_area(self, face):
        """Calculate face area"""
        bbox = face['bbox']
        return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

# Integration function to use in your existing system
def optimize_single_person_detection(faces, image, return_debug_info=False):
    """
    Easy integration function for single-person optimization
    """
    optimizer = SinglePersonOptimizer()
    return optimizer.optimize_for_single_person(faces, image, return_debug_info)