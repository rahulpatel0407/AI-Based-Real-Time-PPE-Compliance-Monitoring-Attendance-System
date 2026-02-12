from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import json
from pathlib import Path

import cv2
import numpy as np


@dataclass
class HSVRange:
    lower: Tuple[int, int, int]
    upper: Tuple[int, int, int]


@dataclass
class ColorThresholds:
    yellow: HSVRange
    red1: HSVRange
    red2: HSVRange


DEFAULT_THRESHOLDS = ColorThresholds(
    yellow=HSVRange((15, 100, 80), (40, 255, 255)),
    red1=HSVRange((0, 100, 50), (10, 255, 255)),
    red2=HSVRange((170, 100, 50), (180, 255, 255)),
)


def load_calibration(path: str | Path) -> Dict:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _range_from_cfg(cfg: Dict, key: str, default: HSVRange) -> HSVRange:
    payload = cfg.get(key, {}) if isinstance(cfg, dict) else {}
    lower = payload.get("lower", list(default.lower))
    upper = payload.get("upper", list(default.upper))
    return HSVRange(tuple(lower), tuple(upper))


def thresholds_from_cfg(cfg: Dict) -> ColorThresholds:
    return ColorThresholds(
        yellow=_range_from_cfg(cfg, "yellow", DEFAULT_THRESHOLDS.yellow),
        red1=_range_from_cfg(cfg, "red1", DEFAULT_THRESHOLDS.red1),
        red2=_range_from_cfg(cfg, "red2", DEFAULT_THRESHOLDS.red2),
    )


def build_color_mask(hsv: np.ndarray, thresholds: ColorThresholds) -> np.ndarray:
    yellow_mask = cv2.inRange(hsv, thresholds.yellow.lower, thresholds.yellow.upper)
    red_mask1 = cv2.inRange(hsv, thresholds.red1.lower, thresholds.red1.upper)
    red_mask2 = cv2.inRange(hsv, thresholds.red2.lower, thresholds.red2.upper)
    red_mask = cv2.bitwise_or(red_mask1, red_mask2)
    return cv2.bitwise_or(yellow_mask, red_mask)


def refine_mask(mask: np.ndarray, kernel_size: int = 7) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def color_coverage(mask: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(mask.shape[1], x2)
    y2 = min(mask.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    roi = mask[y1:y2, x1:x2]
    area = float(roi.size)
    if area <= 0:
        return 0.0
    return float(cv2.countNonZero(roi)) / area


def head_box(person_bbox: Tuple[int, int, int, int], head_ratio: float = 0.3) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = person_bbox
    head_height = max(1, int((y2 - y1) * head_ratio))
    return (x1, y1, x2, y1 + head_height)
