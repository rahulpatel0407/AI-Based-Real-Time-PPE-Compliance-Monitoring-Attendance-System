import time
import unittest
import tempfile
from pathlib import Path
import json

import numpy as np

from violation_recorder import ViolationRecorder


class TestViolationRecorder(unittest.TestCase):
    def test_queue_drop_when_full(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = ViolationRecorder(
                base_path=tmp_dir,
                queue_maxsize=1,
                enable=True,
                start_worker=False,
            )
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            bbox = (10, 10, 110, 110)
            meta = {"camera_id": "CAM-TEST"}

            ok1 = recorder.enqueue_violation(frame, bbox, meta)
            ok2 = recorder.enqueue_violation(frame, bbox, meta)

            self.assertTrue(ok1)
            self.assertFalse(ok2)
            status = recorder.status()
            self.assertEqual(status.dropped_count, 1)

    def test_metadata_and_filenames(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = ViolationRecorder(
                base_path=tmp_dir,
                queue_maxsize=10,
                enable=True,
                save_crops=True,
                overlay_timestamp=False,
                max_concurrent_writes=1,
            )
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            bbox = (20, 30, 120, 140)
            meta = {
                "camera_id": "CAM-TEST",
                "helmet_confidence": 0.1,
                "person_confidence": 0.9,
                "frame_id": 7,
                "frame_number": 7,
                "detection_id": "test-id-123",
                "model_name": "ppe.pt",
                "confidence": 0.92,
            }

            recorder.enqueue_violation(frame, bbox, meta)
            recorder.queue.join()
            recorder.shutdown()

            base_dir = Path(tmp_dir) / "CAM-TEST"
            files = list(base_dir.glob("violation_*.json"))
            self.assertEqual(len(files), 1)
            json_path = files[0]
            image_path = json_path.with_suffix(".jpg")
            crop_path = json_path.with_name(json_path.stem + "_crop.jpg")
            thumb_path = json_path.with_name(json_path.stem + "_thumb.jpg")

            self.assertTrue(image_path.exists())
            self.assertTrue(crop_path.exists())
            self.assertTrue(thumb_path.exists())

            with open(json_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertRegex(image_path.name, r"^violation_\d{8}_\d{6}_\d{3}_test-id-123\.jpg$")
            self.assertEqual(payload["camera_id"], "CAM-TEST")
            self.assertEqual(payload["filename"], image_path.name)
            self.assertEqual(payload["bbox"], [20, 30, 100, 110])
            self.assertAlmostEqual(payload["confidence"], 0.92, places=2)
            self.assertEqual(payload["model"], "ppe.pt")
            self.assertEqual(payload["frame_number"], 7)
            self.assertEqual(payload["status"], "new")
            self.assertEqual(payload["thumbnail"], thumb_path.name)

    def test_integration_non_blocking_enqueue(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = ViolationRecorder(
                base_path=tmp_dir,
                queue_maxsize=50,
                enable=True,
                overlay_timestamp=False,
            )
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            bbox = (5, 5, 100, 100)
            meta = {"camera_id": "CAM-TEST"}

            start = time.monotonic()
            for _ in range(20):
                recorder.enqueue_violation(frame, bbox, meta)
            elapsed = time.monotonic() - start

            self.assertLess(elapsed, 0.5)

            recorder.queue.join()
            recorder.shutdown()
            base_dir = Path(tmp_dir) / "CAM-TEST"
            self.assertTrue(any(base_dir.glob("violation_*.jpg")))


if __name__ == "__main__":
    unittest.main()
