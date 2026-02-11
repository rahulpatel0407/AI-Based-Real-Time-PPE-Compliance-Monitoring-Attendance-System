import time
from pathlib import Path

import numpy as np

from violation_recorder import ViolationRecorder


def main() -> int:
    base_path = Path("violations")
    recorder = ViolationRecorder(
        base_path=str(base_path),
        queue_maxsize=10,
        enable=True,
        overlay_timestamp=True,
        max_concurrent_writes=1,
    )

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bbox = (50, 60, 300, 420)
    meta = {
        "camera_id": "CAM-E2E",
        "confidence": 0.91,
        "frame_number": 12345,
        "model_name": "ppe.pt",
    }

    recorder.enqueue_violation(frame, bbox, meta)
    recorder.queue.join()
    recorder.shutdown()

    matches = list((base_path / "CAM-E2E").glob("violation_*.json"))
    if not matches:
        print("E2E failed: no metadata file created")
        return 1

    json_path = matches[-1]
    image_path = json_path.with_suffix(".jpg")
    if not image_path.exists():
        print("E2E failed: image file missing")
        return 1

    thumb_path = json_path.with_name(json_path.stem + "_thumb.jpg")
    if not thumb_path.exists():
        print("E2E failed: thumbnail file missing")
        return 1

    print(f"E2E success: {image_path} and {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
