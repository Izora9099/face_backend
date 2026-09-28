"""
Single face-recognition engine for FACE.IT.

Wraps the `face_recognition` library (dlib ResNet, 128-d encodings) behind a
small interface so the backend can be swapped later without touching views:

    encode(image)                -> list[np.ndarray]   (one vector per face)
    match(vector, candidates)    -> MatchResult

Stored encodings (Student.face_encoding) are float64 bytes produced by
`encode(...)[0].tobytes()`; changing engine means re-enrolling students.

Biometric data rules: never log images or encodings, never return raw
vectors from the API.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

ENGINE_NAME = 'face_recognition'
ENCODING_DIM = 128
ENCODING_DTYPE = np.float64


class FaceEngineError(Exception):
    """Raised for unusable input (unreadable image, no face, ...)."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass
class MatchResult:
    student_id: Optional[int]
    distance: Optional[float]
    threshold: float
    candidates_compared: int

    @property
    def matched(self) -> bool:
        return self.student_id is not None

    @property
    def confidence(self) -> float:
        """Similarity in [0, 1]: 1 - distance, clipped. 0 when nothing to compare."""
        if self.distance is None:
            return 0.0
        return round(float(max(0.0, min(1.0, 1.0 - self.distance))), 4)


def get_threshold() -> float:
    return float(getattr(settings, 'FACE_MATCH_THRESHOLD', 0.6))


_MODELS = {}


def _models():
    """
    Load dlib's HOG detector, 5-point shape predictor and ResNet encoder once.

    This is exactly what `face_recognition.face_encodings(img)` uses (model
    "small", num_jitters=1), called directly so we can depend on the prebuilt
    `dlib-bin` wheel instead of compiling dlib. Encodings are bit-identical.
    """
    if not _MODELS:
        import warnings

        import dlib
        with warnings.catch_warnings():
            # face_recognition_models still imports the deprecated pkg_resources.
            warnings.simplefilter('ignore', UserWarning)
            import face_recognition_models as frm
        _MODELS['hog'] = dlib.get_frontal_face_detector()
        _MODELS['cnn_path'] = frm.cnn_face_detector_model_location()
        _MODELS['pose'] = dlib.shape_predictor(frm.pose_predictor_five_point_model_location())
        _MODELS['encoder'] = dlib.face_recognition_model_v1(frm.face_recognition_model_location())
    return _MODELS


def _detect(image: np.ndarray, model: str):
    """Face rectangles (dlib.rectangle), clipped to the image."""
    import dlib
    m = _models()
    if model == 'cnn':
        if 'cnn' not in m:
            m['cnn'] = dlib.cnn_face_detection_model_v1(m['cnn_path'])
        rects = [d.rect for d in m['cnn'](image, 1)]
    else:
        rects = list(m['hog'](image, 1))
    h, w = image.shape[:2]
    return [dlib.rectangle(max(r.left(), 0), max(r.top(), 0), min(r.right(), w), min(r.bottom(), h))
            for r in rects]


def load_image(image_file) -> np.ndarray:
    """Decode an uploaded file / path / bytes into an RGB uint8 array."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        if isinstance(image_file, (bytes, bytearray)):
            import io
            image_file = io.BytesIO(image_file)
        elif hasattr(image_file, 'seek'):
            image_file.seek(0)
        img = Image.open(image_file)
        img = ImageOps.exif_transpose(img)  # phone photos come rotated
        img = img.convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise FaceEngineError('Could not read image.', 'invalid_image') from exc

    # Keep dlib fast on large phone photos.
    max_side = 1280
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))
    return np.asarray(img)


def encode(image: np.ndarray, model: Optional[str] = None) -> list[np.ndarray]:
    """Return one 128-d encoding per detected face, largest face first."""
    m = _models()
    model = model or getattr(settings, 'FACE_DETECTION_MODEL', 'hog')
    started = time.perf_counter()
    image = np.ascontiguousarray(image)
    rects = _detect(image, model)
    # Largest face first so callers can take [0] as "the subject".
    rects.sort(key=lambda r: r.width() * r.height(), reverse=True)
    encodings = [
        np.asarray(m['encoder'].compute_face_descriptor(image, m['pose'](image, r), 1), dtype=ENCODING_DTYPE)
        for r in rects
    ]
    logger.info('encode: faces=%d model=%s ms=%.0f',
                len(encodings), model, (time.perf_counter() - started) * 1000)
    return encodings


def encode_single(image_file) -> np.ndarray:
    """Load an upload and return the encoding of its main face, or raise."""
    encodings = encode(load_image(image_file))
    if not encodings:
        raise FaceEngineError('No face detected in image.', 'no_face')
    return encodings[0]


def to_bytes(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=ENCODING_DTYPE).tobytes()


def from_bytes(raw) -> Optional[np.ndarray]:
    if not raw:
        return None
    vec = np.frombuffer(bytes(raw), dtype=ENCODING_DTYPE)
    return vec if vec.shape == (ENCODING_DIM,) else None


def distances(vector: np.ndarray, candidates: Sequence[np.ndarray]) -> np.ndarray:
    if len(candidates) == 0:
        return np.empty((0,))
    return np.linalg.norm(np.vstack(candidates) - vector, axis=1)


def match(vector: np.ndarray,
          candidates: Iterable[Tuple[int, np.ndarray]],
          threshold: Optional[float] = None) -> MatchResult:
    """
    Nearest-neighbour match of `vector` against (student_id, encoding) pairs.
    Returns the closest candidate if its distance is within `threshold`.
    """
    threshold = get_threshold() if threshold is None else float(threshold)
    ids, vecs = [], []
    for sid, enc in candidates:
        if enc is not None:
            ids.append(sid)
            vecs.append(enc)

    if not vecs:
        return MatchResult(None, None, threshold, 0)

    d = distances(vector, vecs)
    best = int(np.argmin(d))
    best_distance = float(d[best])
    student_id = ids[best] if best_distance <= threshold else None
    logger.info('match: candidates=%d best_distance=%.4f matched=%s',
                len(vecs), best_distance, student_id is not None)
    return MatchResult(student_id, best_distance, threshold, len(vecs))


def student_candidates(students) -> list[Tuple[int, np.ndarray]]:
    """(id, encoding) pairs for a Student queryset, skipping unusable rows."""
    pairs = []
    for s in students:
        try:
            vec = from_bytes(s.face_encoding)
        except Exception:  # undecryptable (wrong FIELD_ENCRYPTION_KEY) or corrupt
            logger.warning('encoding unreadable for student_id=%s', s.pk)
            continue
        if vec is not None:
            pairs.append((s.pk, vec))
    return pairs
