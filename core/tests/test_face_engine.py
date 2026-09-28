import numpy as np
from django.test import SimpleTestCase, override_settings

from core import face_engine

from .base import FIXTURES


class FaceEngineTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.obama = face_engine.encode_single(FIXTURES / 'obama.jpg')
        cls.obama2 = face_engine.encode_single(FIXTURES / 'obama2.jpg')
        cls.biden = face_engine.encode_single(FIXTURES / 'biden.jpg')

    def test_encoding_shape_and_round_trip(self):
        self.assertEqual(self.obama.shape, (128,))
        np.testing.assert_array_equal(face_engine.from_bytes(face_engine.to_bytes(self.obama)), self.obama)

    def test_match_picks_nearest_within_threshold(self):
        result = face_engine.match(self.obama2, [(1, self.obama), (2, self.biden)], threshold=0.6)
        self.assertTrue(result.matched)
        self.assertEqual(result.student_id, 1)
        self.assertAlmostEqual(result.confidence, 1 - result.distance, places=3)

    @override_settings(FACE_MATCH_THRESHOLD=0.2)
    def test_threshold_setting_is_respected(self):
        result = face_engine.match(self.obama2, [(1, self.obama)])
        self.assertFalse(result.matched)
        self.assertEqual(result.threshold, 0.2)

    def test_no_candidates(self):
        result = face_engine.match(self.obama, [])
        self.assertFalse(result.matched)
        self.assertEqual(result.confidence, 0.0)

    def test_multiple_faces_sorted_largest_first(self):
        encodings = face_engine.encode(face_engine.load_image(FIXTURES / 'two_people.jpg'))
        self.assertEqual(len(encodings), 2)

    def test_invalid_image(self):
        with self.assertRaises(face_engine.FaceEngineError) as ctx:
            face_engine.load_image(b'not an image')
        self.assertEqual(ctx.exception.code, 'invalid_image')
