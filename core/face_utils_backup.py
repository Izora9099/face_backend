# core/face_utils.py - Fixed version without circular import
import face_recognition
import numpy as np
from keras_facenet import FaceNet
from mtcnn.mtcnn import MTCNN
import cv2
from PIL import Image
# REMOVED: from .adaptive_detector import AdaptiveFaceDetector  # This was causing circular import

# Initialize models only once
FACENET_EMBEDDER = None
MTCNN_DETECTOR = None


def get_mtcnn_detector():
    """Initialize MTCNN detector with default settings"""
    global MTCNN_DETECTOR
    if MTCNN_DETECTOR is None:
        # Use default MTCNN initialization - most versions support this
        MTCNN_DETECTOR = MTCNN()
    return MTCNN_DETECTOR


def get_facenet_embedder():
    """Initialize FaceNet embedder"""
    global FACENET_EMBEDDER
    if FACENET_EMBEDDER is None:
        FACENET_EMBEDDER = FaceNet()
    return FACENET_EMBEDDER


def detect_and_align_face(image):
    """
    Use MTCN
