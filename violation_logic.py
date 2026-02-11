from typing import Iterable, Tuple, Optional


Box = Tuple[int, int, int, int]
NoHelmetBox = Tuple[int, int, int, int, float]
HardhatBox = Tuple[int, int, int, int, float]


def _iou(box_a: Box, box_b: Box) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def _head_box(person_bbox: Box, head_ratio: float = 0.3) -> Box:
    x1, y1, x2, y2 = person_bbox
    head_height = max(1, int((y2 - y1) * head_ratio))
    return (x1, y1, x2, y1 + head_height)


def best_overlap_confidence(
    person_bbox: Optional[Box],
    candidate_boxes: Iterable[Tuple[int, int, int, int, float]],
    min_iou: float,
    use_head_region: bool = False,
    head_ratio: float = 0.3,
) -> float:
    if person_bbox is None:
        return 0.0
    target_box = _head_box(person_bbox, head_ratio) if use_head_region else person_bbox
    best_conf = 0.0
    for x1, y1, x2, y2, conf in candidate_boxes:
        if _iou(target_box, (x1, y1, x2, y2)) >= min_iou:
            if conf > best_conf:
                best_conf = conf
    return best_conf


def is_helmet_violation(
    person_confidence: float,
    person_bbox: Optional[Box],
    no_helmet_boxes: Iterable[NoHelmetBox],
    hardhat_boxes: Iterable[HardhatBox],
    person_threshold: float,
    no_helmet_threshold: float,
    hardhat_threshold: float,
    min_overlap_iou: float = 0.1,
    head_ratio: float = 0.3,
) -> Tuple[bool, float]:
    if person_bbox is None or person_confidence < person_threshold:
        return False, 0.0

    no_helmet_conf = best_overlap_confidence(
        person_bbox,
        no_helmet_boxes,
        min_overlap_iou,
        use_head_region=True,
        head_ratio=head_ratio,
    )
    hardhat_conf = best_overlap_confidence(
        person_bbox,
        hardhat_boxes,
        min_overlap_iou,
        use_head_region=True,
        head_ratio=head_ratio,
    )

    if hardhat_conf >= hardhat_threshold and hardhat_conf >= no_helmet_conf:
        return False, 0.0

    if no_helmet_conf >= no_helmet_threshold:
        return True, no_helmet_conf
    return False, 0.0
