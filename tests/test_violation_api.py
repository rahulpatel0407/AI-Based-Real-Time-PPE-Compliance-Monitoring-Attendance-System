import json
import tempfile
import unittest
from pathlib import Path

import backend


class TestViolationAPI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        backend.VIOLATIONS_BASE_PATH = self.tmp_dir.name
        self.client = backend.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'admin'
            sess['role'] = 'admin'

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_list_and_review_violation(self):
        base_dir = Path(self.tmp_dir.name) / "CAM-TEST"
        base_dir.mkdir(parents=True, exist_ok=True)
        base_name = "violation_20260121_174144_123_test123"
        meta_path = base_dir / f"{base_name}.json"
        payload = {
            "id": "CAM-TEST__" + base_name,
            "timestamp": "2026-01-21T17:41:44",
            "camera_id": "CAM-TEST",
            "zone": "Zone A",
            "filename": f"{base_name}.jpg",
            "bbox": [10, 20, 100, 120],
            "confidence": 0.42,
            "model": "ppe.pt",
            "frame_number": 123,
            "thumbnail": f"{base_name}_thumb.jpg",
            "missing_ppe": "Helmet",
            "status": "new"
        }
        with meta_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        list_response = self.client.get('/api/violations?limit=5')
        self.assertEqual(list_response.status_code, 200)
        data = list_response.get_json()
        self.assertEqual(data['count'], 1)
        violation_id = data['items'][0]['id']

        detail_response = self.client.get(f"/api/violations/{violation_id}")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.get_json()
        self.assertEqual(detail['camera_id'], 'CAM-TEST')

        review_response = self.client.post(f"/api/violations/{violation_id}/review")
        self.assertEqual(review_response.status_code, 200)
        reviewed = review_response.get_json()
        self.assertEqual(reviewed['status'], 'reviewed')


if __name__ == '__main__':
    unittest.main()
