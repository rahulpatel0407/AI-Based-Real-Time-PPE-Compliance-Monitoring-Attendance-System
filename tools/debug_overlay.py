import argparse
from pathlib import Path

import cv2
import numpy as np

from ultralytics import YOLO

from ppe_color_utils import build_color_mask, refine_mask, color_coverage, thresholds_from_cfg, load_calibration


def parse_args():
    parser = argparse.ArgumentParser(description="Overlay person/PPE detections with color mask coverage.")
    parser.add_argument("--video", required=True, help="Input video path")
    parser.add_argument("--out", required=True, help="Output video path")
    parser.add_argument("--ppe-model", default="YOLO-Weights/ppe.pt", help="PPE model path")
    parser.add_argument("--person-model", default="", help="Optional person model path")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--calibration", default="", help="Path to color calibration JSON")
    parser.add_argument("--show", action="store_true", help="Show preview window")
    return parser.parse_args()


def overlay_debug(frame, person_bbox, color_mask, vest_box=None, vest_conf=None, coverage=None):
    vis = frame.copy()
    x1, y1, x2, y2 = person_bbox
    cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
    if vest_box is not None:
        vx1, vy1, vx2, vy2 = vest_box
        cv2.rectangle(vis, (vx1, vy1), (vx2, vy2), (0, 255, 0), 2)
        if vest_conf is not None:
            cv2.putText(vis, f"vest:{vest_conf:.2f}", (vx1, max(0, vy1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    mask3 = cv2.cvtColor(color_mask, cv2.COLOR_GRAY2BGR)
    mask3 = (mask3 > 0).astype("uint8") * 255
    alpha = 0.35
    vis = cv2.addWeighted(vis, 1.0, mask3, alpha, 0)
    if coverage is not None:
        cv2.putText(vis, f"cov:{coverage:.2f}", (x1, min(vis.shape[0] - 4, y2 + 16)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return vis


def main():
    args = parse_args()
    video_path = Path(args.video)
    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit("Cannot open video")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h),
    )

    ppe_model = YOLO(args.ppe_model)
    person_model = YOLO(args.person_model) if args.person_model else None

    calibration = load_calibration(args.calibration) if args.calibration else {}
    thresholds = thresholds_from_cfg(calibration.get("thresholds", {})) if calibration else thresholds_from_cfg({})

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = build_color_mask(hsv, thresholds)
        mask = refine_mask(mask, kernel_size=7)

        person_boxes = []
        if person_model:
            person_results = person_model.predict(frame, conf=args.conf, iou=args.iou, imgsz=args.imgsz, verbose=False)
            for r in person_results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    if cls != 0:
                        continue
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    person_boxes.append((x1, y1, x2, y2))
        else:
            ppe_results = ppe_model.predict(frame, conf=args.conf, iou=args.iou, imgsz=args.imgsz, verbose=False)
            for r in ppe_results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    if cls != 5:
                        continue
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    person_boxes.append((x1, y1, x2, y2))

        ppe_results = ppe_model.predict(frame, conf=args.conf, iou=args.iou, imgsz=args.imgsz, verbose=False)
        vest_boxes = []
        for r in ppe_results:
            for box in r.boxes:
                cls = int(box.cls[0])
                if cls != 7:
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                vest_boxes.append((x1, y1, x2, y2, conf))

        vis = frame
        for (px1, py1, px2, py2) in person_boxes:
            best_vest = None
            best_conf = 0.0
            for (vx1, vy1, vx2, vy2, vconf) in vest_boxes:
                if vconf > best_conf:
                    best_conf = vconf
                    best_vest = (vx1, vy1, vx2, vy2)
            coverage = color_coverage(mask, (px1, py1, px2, py2))
            vis = overlay_debug(vis, (px1, py1, px2, py2), mask, best_vest, best_conf if best_vest else None, coverage)

        writer.write(vis)
        if args.show:
            cv2.imshow("debug", vis)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    writer.release()
    if args.show:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
