# core/smart_face_filter.py - Smart filtering to reduce false positives

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SmartFaceFilter:
    """
    Intelligent face filtering to reduce false positives from OpenCV
    """
    
    def __init__(self):
        self.filters = {
            'size_filter': True,
            'aspect_ratio_filter': True, 
            'position_filter': True,
            'quality_filter': True,
            'overlap_filter': True,
            'confidence_ranking': True
        }
        
    def filter_faces(self, faces, image, return_debug_info=False):
        """
        Apply intelligent filtering to remove false positives
        
        Args:
            faces: List of face detections from OpenCV
            image: Original image (numpy array)
            return_debug_info: Return debugging information
            
        Returns:
            Filtered list of faces
        """
        if not faces:
            return faces
            
        debug_info = {
            'original_count': len(faces),
            'filters_applied': [],
            'removed_faces': []
        }
        
        filtered_faces = faces.copy()
        
        # Filter 1: Size filtering (remove tiny and huge detections)
        if self.filters['size_filter']:
            filtered_faces, removed = self._filter_by_size(filtered_faces, image)
            debug_info['filters_applied'].append(f"Size filter: removed {len(removed)}")
            debug_info['removed_faces'].extend(removed)
            
        # Filter 2: Aspect ratio filtering (faces should be roughly square/oval)
        if self.filters['aspect_ratio_filter']:
            filtered_faces, removed = self._filter_by_aspect_ratio(filtered_faces)
            debug_info['filters_applied'].append(f"Aspect ratio filter: removed {len(removed)}")
            debug_info['removed_faces'].extend(removed)
            
        # Filter 3: Position filtering (remove edge artifacts)
        if self.filters['position_filter']:
            filtered_faces, removed = self._filter_by_position(filtered_faces, image)
            debug_info['filters_applied'].append(f"Position filter: removed {len(removed)}")
            debug_info['removed_faces'].extend(removed)
            
        # Filter 4: Image quality in face region
        if self.filters['quality_filter']:
            filtered_faces, removed = self._filter_by_face_quality(filtered_faces, image)
            debug_info['filters_applied'].append(f"Quality filter: removed {len(removed)}")
            debug_info['removed_faces'].extend(removed)
            
        # Filter 5: Remove overlapping detections (keep best one)
        if self.filters['overlap_filter']:
            filtered_faces, removed = self._filter_overlapping_faces(filtered_faces)
            debug_info['filters_applied'].append(f"Overlap filter: removed {len(removed)}")
            debug_info['removed_faces'].extend(removed)
            
        # Filter 6: Rank by confidence and keep top N
        if self.filters['confidence_ranking']:
            filtered_faces = self._rank_and_limit_faces(filtered_faces, max_faces=3)
            debug_info['filters_applied'].append(f"Confidence ranking: kept top {len(filtered_faces)}")
            
        debug_info['final_count'] = len(filtered_faces)
        
        logger.info(f"Face filtering: {debug_info['original_count']} → {debug_info['final_count']} faces")
        
        if return_debug_info:
            return filtered_faces, debug_info
        return filtered_faces
        
    def _filter_by_size(self, faces, image):
        """Remove faces that are too small or too large"""
        height, width = image.shape[:2]
        image_area = height * width
        
        filtered_faces = []
        removed_faces = []
        
        for face in faces:
            x1, y1, x2, y2 = face['bbox']
            face_width = x2 - x1
            face_height = y2 - y1
            face_area = face_width * face_height
            
            # Size limits based on image resolution
            min_size = min(30, min(width, height) * 0.02)  # At least 2% of smallest dimension
            max_size = min(width, height) * 0.8            # At most 80% of smallest dimension
            
            # Area limits (face shouldn't be more than 25% of image)
            max_area_ratio = 0.25
            
            if (face_width < min_size or face_height < min_size or
                face_width > max_size or face_height > max_size or
                face_area > image_area * max_area_ratio):
                
                removed_faces.append({
                    'face': face,
                    'reason': f'Size: {face_width}x{face_height}, limits: {min_size}-{max_size}'
                })
            else:
                filtered_faces.append(face)
                
        return filtered_faces, removed_faces
        
    def _filter_by_aspect_ratio(self, faces):
        """Remove detections with non-face-like aspect ratios"""
        filtered_faces = []
        removed_faces = []
        
        for face in faces:
            x1, y1, x2, y2 = face['bbox']
            width = x2 - x1
            height = y2 - y1
            aspect_ratio = width / height if height > 0 else 0
            
            # Faces should be roughly between 0.6 and 1.4 aspect ratio
            # (slightly taller than wide to square to slightly wider than tall)
            if 0.6 <= aspect_ratio <= 1.4:
                filtered_faces.append(face)
            else:
                removed_faces.append({
                    'face': face,
                    'reason': f'Aspect ratio: {aspect_ratio:.2f} (should be 0.6-1.4)'
                })
                
        return filtered_faces, removed_faces
        
    def _filter_by_position(self, faces, image):
        """Remove faces too close to image edges (likely artifacts)"""
        height, width = image.shape[:2]
        edge_margin = min(20, min(width, height) * 0.05)  # 5% margin from edges
        
        filtered_faces = []
        removed_faces = []
        
        for face in faces:
            x1, y1, x2, y2 = face['bbox']
            
            # Check if face is too close to any edge
            too_close_to_edge = (
                x1 < edge_margin or y1 < edge_margin or
                x2 > width - edge_margin or y2 > height - edge_margin
            )
            
            if too_close_to_edge:
                # Don't remove completely, but reduce confidence significantly
                face['confidence'] *= 0.3
                face['edge_detection'] = True
                
            filtered_faces.append(face)
                
        return filtered_faces, removed_faces
        
    def _filter_by_face_quality(self, faces, image):
        """Analyze the actual face region for face-like features"""
        filtered_faces = []
        removed_faces = []
        
        for face in faces:
            x1, y1, x2, y2 = face['bbox']
            
            # Extract face region
            face_region = image[y1:y2, x1:x2]
            
            if face_region.size == 0:
                removed_faces.append({
                    'face': face,
                    'reason': 'Empty face region'
                })
                continue
                
            # Convert to grayscale for analysis
            if len(face_region.shape) == 3:
                gray_face = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
            else:
                gray_face = face_region
                
            # Check for face-like characteristics
            quality_score = self._analyze_face_region_quality(gray_face)
            
            # Update confidence based on quality
            face['region_quality'] = quality_score
            face['confidence'] *= (quality_score / 100)  # Scale confidence by quality
            
            # Keep faces with reasonable quality
            if quality_score > 20:  # Very low threshold, just remove obvious non-faces
                filtered_faces.append(face)
            else:
                removed_faces.append({
                    'face': face,
                    'reason': f'Poor region quality: {quality_score:.1f}'
                })
                
        return filtered_faces, removed_faces
        
    def _analyze_face_region_quality(self, gray_face):
        """Analyze if a region looks like it could contain a face"""
        try:
            # Check for reasonable contrast (faces have eyes, mouth, etc.)
            contrast = np.std(gray_face)
            contrast_score = min(100, contrast * 2)  # Higher contrast = more likely to be face
            
            # Check for edge density (faces have more edges than flat regions)
            edges = cv2.Canny(gray_face, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            edge_score = min(100, edge_density * 1000)  # More edges = more likely to be face
            
            # Check brightness distribution (faces aren't pure black/white)
            mean_brightness = np.mean(gray_face)
            brightness_score = 100 - abs(mean_brightness - 127)  # Closer to middle gray = better
            
            # Combine scores
            quality_score = (contrast_score * 0.4 + edge_score * 0.4 + brightness_score * 0.2)
            
            return max(0, min(100, quality_score))
            
        except:
            return 50  # Default score if analysis fails
            
    def _filter_overlapping_faces(self, faces):
        """Remove overlapping face detections, keep the best one"""
        if len(faces) <= 1:
            return faces, []
            
        filtered_faces = []
        removed_faces = []
        
        # Sort by confidence (highest first)
        sorted_faces = sorted(faces, key=lambda f: f['confidence'], reverse=True)
        
        for face in sorted_faces:
            # Check if this face overlaps significantly with any already accepted face
            overlaps = False
            for accepted_face in filtered_faces:
                if self._calculate_overlap(face['bbox'], accepted_face['bbox']) > 0.3:
                    overlaps = True
                    removed_faces.append({
                        'face': face,
                        'reason': 'Overlaps with higher confidence face'
                    })
                    break
                    
            if not overlaps:
                filtered_faces.append(face)
                
        return filtered_faces, removed_faces
        
    def _calculate_overlap(self, bbox1, bbox2):
        """Calculate overlap ratio between two bounding boxes"""
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
        
    def _rank_and_limit_faces(self, faces, max_faces=2):
        """Keep only the top N most confident faces"""
        # Sort by confidence and keep top N
        sorted_faces = sorted(faces, key=lambda f: f['confidence'], reverse=True)
        return sorted_faces[:max_faces]