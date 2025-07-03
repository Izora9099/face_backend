# core/image_enhancer.py
import cv2
import numpy as np
from skimage import exposure, restoration, filters
import logging

logger = logging.getLogger(__name__)

class ImageEnhancer:
    """
    Handles image preprocessing for poor quality images
    before YOLO detection - optimized for limited storage
    """
    
    def __init__(self):
        self.enhancement_methods = {
            'deblur': self._deblur_image,
            'denoise': self._denoise_image,
            'enhance_contrast': self._enhance_contrast,
            'sharpen': self._sharpen_image,
            'histogram_eq': self._histogram_equalization
        }
        
    def assess_image_quality(self, image):
        """
        Assess image quality using multiple metrics
        Returns score from 0-100 (100 = excellent quality)
        """
        try:
            # Convert to grayscale for analysis
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            # Calculate quality metrics
            blur_score = self._calculate_blur_score(gray)
            noise_score = self._calculate_noise_score(gray)
            contrast_score = self._calculate_contrast_score(gray)
            brightness_score = self._calculate_brightness_score(gray)
            
            # Weighted average (adjust weights based on your needs)
            quality_score = (
                blur_score * 0.3 +
                noise_score * 0.25 +
                contrast_score * 0.25 +
                brightness_score * 0.2
            )
            
            return min(100, max(0, quality_score))
            
        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return 50  # Default middle score
            
    def enhance_image(self, image, quality_score=None):
        """
        Apply appropriate enhancement based on image quality
        
        Args:
            image: numpy array (BGR format)
            quality_score: pre-calculated quality score
            
        Returns:
            Enhanced image
        """
        if quality_score is None:
            quality_score = self.assess_image_quality(image)
            
        enhanced = image.copy()
        
        try:
            # Apply enhancements based on quality score
            if quality_score < 30:
                # Very poor quality - apply all enhancements
                enhanced = self._enhance_contrast(enhanced)
                enhanced = self._denoise_image(enhanced)
                enhanced = self._deblur_image(enhanced)
                enhanced = self._sharpen_image(enhanced)
                
            elif quality_score < 50:
                # Poor quality - apply moderate enhancements
                enhanced = self._enhance_contrast(enhanced)
                enhanced = self._denoise_image(enhanced)
                enhanced = self._sharpen_image(enhanced)
                
            elif quality_score < 70:
                # Acceptable quality - light enhancement
                enhanced = self._enhance_contrast(enhanced)
                
            # For quality >= 70, return original image
            
            logger.info(f"Enhanced image (quality: {quality_score:.1f})")
            return enhanced
            
        except Exception as e:
            logger.error(f"Image enhancement failed: {e}")
            return image  # Return original if enhancement fails
            
    def _calculate_blur_score(self, gray_image):
        """Calculate blur score using Laplacian variance"""
        try:
            laplacian_var = cv2.Laplacian(gray_image, cv2.CV_64F).var()
            # Normalize to 0-100 scale (higher = less blur)
            return min(100, laplacian_var / 10)
        except:
            return 50
            
    def _calculate_noise_score(self, gray_image):
        """Estimate noise level (higher score = less noise)"""
        try:
            # Use standard deviation of Laplacian as noise estimate
            noise_level = np.std(cv2.Laplacian(gray_image, cv2.CV_64F))
            # Invert and normalize (lower noise = higher score)
            return max(0, 100 - (noise_level / 2))
        except:
            return 50
            
    def _calculate_contrast_score(self, gray_image):
        """Calculate contrast score"""
        try:
            # Use standard deviation as contrast measure
            contrast = np.std(gray_image)
            # Normalize to 0-100 scale
            return min(100, contrast / 2)
        except:
            return 50
            
    def _calculate_brightness_score(self, gray_image):
        """Calculate brightness appropriateness"""
        try:
            mean_brightness = np.mean(gray_image)
            # Optimal range is around 100-150 for 8-bit images
            optimal_range = abs(mean_brightness - 125)
            return max(0, 100 - (optimal_range / 2))
        except:
            return 50
            
    def _deblur_image(self, image):
        """Apply deblurring filter - lightweight for storage constraints"""
        try:
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            return cv2.filter2D(image, -1, kernel)
        except:
            return image
            
    def _denoise_image(self, image):
        """Apply noise reduction - fast method for storage constraints"""
        try:
            return cv2.bilateralFilter(image, 9, 75, 75)  # Faster than fastNlMeans
        except:
            return image
            
    def _enhance_contrast(self, image):
        """Enhance image contrast using CLAHE"""
        try:
            # Convert to LAB color space
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            l = clahe.apply(l)
            
            # Merge and convert back
            lab = cv2.merge([l, a, b])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        except:
            return image
            
    def _sharpen_image(self, image):
        """Apply sharpening filter"""
        try:
            kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
            return cv2.filter2D(image, -1, kernel)
        except:
            return image
            
    def _histogram_equalization(self, image):
        """Apply histogram equalization"""
        try:
            # Convert to YUV for better results
            yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
            yuv[:,:,0] = cv2.equalizeHist(yuv[:,:,0])
            return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        except:
            return image