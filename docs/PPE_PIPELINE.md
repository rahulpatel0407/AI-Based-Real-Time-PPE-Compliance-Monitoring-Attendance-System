# PPE Detection Pipeline (IOCL)

## Preprocess
- Capture frame from camera.
- Convert to HSV and generate yellow/red masks using calibrated thresholds.
- Morphological open/close to remove small blobs and fill holes.
- (Optional) Person detector crop to focus on torso/head regions.

## Model
- YOLOv8 (seg preferred) trained with granular labels: helmet, no_helmet, vest_yellow, vest_red, vest_other, shirt, hardhat, reflective_strip, no_ppe.
- Transfer learning from COCO or safety PPE datasets. Freeze backbone initially, then fine-tune.
- Add color channel fusion (stack color mask as extra channel or add small fusion head).

## Postprocess
- Class-aware NMS.
- Helmet decision uses head-region overlap IoU to avoid torso overlaps.
- Vest decision uses fused logic:
  - Accept if conf ≥ T1 or (conf ≥ T2 and color_coverage ≥ T_color).
- Per-person missing PPE logic with debounce, cooldown and snapshot capture.

## Deployment
- Per-camera color calibration using short video sample.
- Export to ONNX/TensorRT/OpenVINO for real-time throughput.
- Log false positives and feed into hard-negative mining.
