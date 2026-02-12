from ultralytics import YOLO
import cv2
import os
import numpy as np
from ppe_color_utils import (
    build_color_mask,
    refine_mask,
    color_coverage,
    thresholds_from_cfg,
    load_calibration,
)
from fire_alarm import start_fire_alarm, stop_fire_alarm

# Load model ONCE (IMPORTANT)
model = YOLO("YOLO-Weights/ppe.pt")

MODEL_CONF = float(os.environ.get("MODEL_CONF", "0.25"))
MODEL_IOU = float(os.environ.get("MODEL_IOU", "0.45"))
MODEL_IMGSZ = int(os.environ.get("MODEL_IMGSZ", "640"))
HELMET_THRESHOLD = float(os.environ.get("HELMET_THRESHOLD", "0.5"))
VEST_CONF_STRICT = float(os.environ.get("VEST_CONF_STRICT", "0.45"))
VEST_CONF_SOFT = float(os.environ.get("VEST_CONF_SOFT", "0.3"))
VEST_COLOR_COVERAGE_MIN = float(os.environ.get("VEST_COLOR_COVERAGE_MIN", "0.12"))
VEST_MIN_BOX_AREA = int(os.environ.get("VEST_MIN_BOX_AREA", "300"))
COLOR_CALIBRATION_PATH = os.environ.get("COLOR_CALIBRATION_PATH", "")
CALIBRATION = load_calibration(COLOR_CALIBRATION_PATH) if COLOR_CALIBRATION_PATH else {}
COLOR_THRESHOLDS = thresholds_from_cfg(CALIBRATION.get("thresholds", {})) if CALIBRATION else thresholds_from_cfg({})

classNames = [
    'Hardhat', None, 'NO-Hardhat', None,
    'NO-Safety Vest', 'Person',
    'Safety Cone', 'Safety Vest',
    'machinery', 'vehicle'
]

# Fire detection using color-based analysis
def detect_fire(frame):
    """Detect fire using HSV color ranges."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Fire detection (red-orange colors)
    lower_fire1 = np.array([0, 100, 100])
    upper_fire1 = np.array([10, 255, 255])
    mask_fire1 = cv2.inRange(hsv, lower_fire1, upper_fire1)

    lower_fire2 = np.array([170, 100, 100])
    upper_fire2 = np.array([180, 255, 255])
    mask_fire2 = cv2.inRange(hsv, lower_fire2, upper_fire2)

    fire_mask = cv2.bitwise_or(mask_fire1, mask_fire2)

    # Calculate contours to find fire regions
    fire_contours, _ = cv2.findContours(fire_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    fire_areas = []
    for contour in fire_contours:
        area = cv2.contourArea(contour)
        if area > 500:
            fire_areas.append(contour)

    fire_detected = len(fire_areas) > 0

    return fire_detected, fire_areas


def video_detection(video_path):
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Cannot open video")

    # Output video
    output_path = video_path.replace(".mp4", "_out.mp4")

    width = int(cap.get(3))
    height = int(cap.get(4))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    out = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        (width, height)
    )

    helmet_detected = False
    fire_detected = False
    max_confidence = 0.0
    alarm_triggered = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Check for fire
        fire, fire_areas = detect_fire(frame)

        if fire:
            fire_detected = True
            if not alarm_triggered:
                start_fire_alarm()
                alarm_triggered = True

            # Draw fire detection boxes
            for contour in fire_areas:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 3)

            # Add fire alert text
            cv2.putText(frame, "🔥 FIRE DETECTED! 🔥", (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = build_color_mask(hsv, COLOR_THRESHOLDS)
        mask = refine_mask(mask, kernel_size=7)

        results = model.predict(
            frame,
            conf=MODEL_CONF,
            iou=MODEL_IOU,
            imgsz=MODEL_IMGSZ,
            verbose=False,
        )

        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = classNames[cls]
                if not class_name:
                    continue

                if conf > max_confidence:
                    max_confidence = conf

                if class_name == "Safety Vest":
                    area = (x2 - x1) * (y2 - y1)
                    if area < VEST_MIN_BOX_AREA:
                        continue
                    coverage = color_coverage(mask, (x1, y1, x2, y2))
                    if not (conf >= VEST_CONF_STRICT or (conf >= VEST_CONF_SOFT and coverage >= VEST_COLOR_COVERAGE_MIN)):
                        continue

                if class_name == "Hardhat" and conf >= HELMET_THRESHOLD:
                    helmet_detected = True

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                color = (0, 255, 0) if "NO" not in class_name else (0, 0, 255)
                label = f"{class_name} {conf:.2f}"

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                )

        out.write(frame)

    cap.release()
    out.release()

    if alarm_triggered:
        stop_fire_alarm()

    return {
        "output_path": output_path,
        "helmet_detected": helmet_detected,
        "fire_detected": fire_detected,
        "confidence": round(max_confidence, 2)
    }


def stream_detection(camera_index=0):
    """Yield processed frames from a webcam with fire detection (generator)."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise ValueError("Cannot open camera")

    alarm_triggered = False
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Check for fire
            fire, fire_areas = detect_fire(frame)

            if fire:
                if not alarm_triggered:
                    start_fire_alarm()
                    alarm_triggered = True

                # Draw fire detection boxes
                for contour in fire_areas:
                    x, y, w, h = cv2.boundingRect(contour)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 3)

                # Add fire alert text
                cv2.putText(frame, "🔥 FIRE DETECTED! 🔥", (50, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            else:
                if alarm_triggered:
                    stop_fire_alarm()
                    alarm_triggered = False

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = build_color_mask(hsv, COLOR_THRESHOLDS)
            mask = refine_mask(mask, kernel_size=7)

            results = model.predict(
                frame,
                conf=MODEL_CONF,
                iou=MODEL_IOU,
                imgsz=MODEL_IMGSZ,
                stream=True,
                verbose=False,
            )

            for r in results:
                for box in r.boxes:
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    class_name = classNames[cls]
                    if not class_name:
                        continue

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    if class_name == "Safety Vest":
                        area = (x2 - x1) * (y2 - y1)
                        if area < VEST_MIN_BOX_AREA:
                            continue
                        coverage = color_coverage(mask, (x1, y1, x2, y2))
                        if not (conf >= VEST_CONF_STRICT or (conf >= VEST_CONF_SOFT and coverage >= VEST_COLOR_COVERAGE_MIN)):
                            continue

                    color = (0, 255, 0) if "NO" not in class_name else (0, 0, 255)
                    label = f"{class_name} {conf:.2f}"

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                    )

            yield frame
    finally:
        if alarm_triggered:
            stop_fire_alarm()
        cap.release()
        cv2.destroyAllWindows()
