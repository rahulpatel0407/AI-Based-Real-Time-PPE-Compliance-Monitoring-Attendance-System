import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def sample_frames(video_path, max_frames=300, stride=5):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    frames = []
    idx = 0
    while len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % stride == 0:
            frames.append(frame)
        idx += 1
    cap.release()
    return frames


def collect_hsv_pixels(frames, min_s=60, min_v=50):
    pixels = []
    for frame in frames:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        mask = (s >= min_s) & (v >= min_v)
        hsv_pixels = np.stack([h[mask], s[mask], v[mask]], axis=-1)
        if hsv_pixels.size:
            pixels.append(hsv_pixels)
    if not pixels:
        return np.empty((0, 3), dtype=np.uint8)
    return np.vstack(pixels)


def kmeans_hue(pixels, k=3):
    if pixels.shape[0] < k:
        return []
    data = pixels.astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(data, k, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    return centers


def pick_ranges(centers):
    ranges = {
        "yellow": {"lower": [15, 100, 80], "upper": [40, 255, 255]},
        "red1": {"lower": [0, 100, 50], "upper": [10, 255, 255]},
        "red2": {"lower": [170, 100, 50], "upper": [180, 255, 255]},
    }
    if not centers:
        return ranges

    for center in centers:
        hue = center[0]
        if 10 <= hue <= 50:
            ranges["yellow"]["lower"][0] = max(10, int(hue - 12))
            ranges["yellow"]["upper"][0] = min(50, int(hue + 12))
        if hue <= 8:
            ranges["red1"]["upper"][0] = min(12, int(hue + 6))
        if hue >= 170:
            ranges["red2"]["lower"][0] = max(165, int(hue - 6))

    return ranges


def main():
    parser = argparse.ArgumentParser(description="Calibrate HSV thresholds for PPE colors.")
    parser.add_argument("--video", required=True, help="Path to calibration video.")
    parser.add_argument("--out", default="calibration/color_calibration.json", help="Output JSON path.")
    parser.add_argument("--max-frames", type=int, default=240)
    parser.add_argument("--stride", type=int, default=5)
    args = parser.parse_args()

    frames = sample_frames(args.video, max_frames=args.max_frames, stride=args.stride)
    pixels = collect_hsv_pixels(frames)
    centers = kmeans_hue(pixels, k=3)
    ranges = pick_ranges(centers)

    payload = {
        "source_video": str(args.video),
        "thresholds": ranges,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved calibration to {out_path}")


if __name__ == "__main__":
    main()
