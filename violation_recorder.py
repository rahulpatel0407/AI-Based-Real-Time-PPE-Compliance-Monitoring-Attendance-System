import os
import json
import uuid
import errno
import time
import logging
from collections import deque, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue, Full, Empty
from threading import Event, Thread, Lock
from typing import Dict, Optional, Tuple, Any

import cv2
import numpy as np
try:
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None


@dataclass
class ViolationRecorderStatus:
    saved_count: int
    dropped_count: int
    queue_length: int


class ViolationRecorder:
    def __init__(
        self,
        base_path: str = "violations",
        queue_maxsize: int = 200,
        jpeg_quality: int = 85,
        enable: bool = True,
        rate_limit_per_minute: int = 30,
        rate_limit_seconds: float = 60.0,
        save_crops: bool = True,
        obfuscate_faces: bool = False,
        obfuscate_ratio: float = 0.4,
        model_name: str = "ppe.pt",
        default_camera_id: str = "CAM-DEFAULT",
        retention_days: int = 30,
        overlay_timestamp: bool = True,
        max_concurrent_writes: int = 2,
        thumbnail_width: int = 200,
        upload_enabled: bool = False,
        upload_endpoint: Optional[str] = None,
        upload_timeout: float = 5.0,
        start_worker: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.base_path = Path(base_path)
        self.queue = Queue(maxsize=max(queue_maxsize, 1))
        self.jpeg_quality = int(jpeg_quality)
        self.enable = bool(enable)
        self.rate_limit_per_minute = int(rate_limit_per_minute)
        self.rate_limit_seconds = float(rate_limit_seconds)
        self.save_crops = bool(save_crops)
        self.obfuscate_faces = bool(obfuscate_faces)
        self.obfuscate_ratio = float(obfuscate_ratio)
        self.model_name = model_name
        self.default_camera_id = default_camera_id
        self.retention_days = int(retention_days)
        self.overlay_timestamp = bool(overlay_timestamp)
        self.max_concurrent_writes = max(1, int(max_concurrent_writes))
        self.thumbnail_width = max(64, int(thumbnail_width))
        self.upload_enabled = bool(upload_enabled)
        self.upload_endpoint = upload_endpoint
        self.upload_timeout = float(upload_timeout)
        self._prune_interval_sec = 3600
        self._last_prune_at = 0.0

        self._saved_count = 0
        self._dropped_count = 0
        self._lock = Lock()
        self._stop_event = Event()
        self._workers: list[Thread] = []
        self._rate_windows: Dict[str, deque] = defaultdict(deque)
        self._bbox_last_saved: Dict[Tuple[Any, ...], float] = {}

        self.logger = logger or logging.getLogger("violation_recorder")
        if start_worker:
            self.start()

    def start(self) -> None:
        if any(worker.is_alive() for worker in self._workers):
            return
        self._stop_event.clear()
        self._workers = []
        for idx in range(self.max_concurrent_writes):
            worker = Thread(
                target=self._worker_loop,
                name=f"ViolationRecorderWorker-{idx + 1}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if wait:
            for worker in self._workers:
                worker.join(timeout=timeout)

    def status(self) -> ViolationRecorderStatus:
        with self._lock:
            return ViolationRecorderStatus(
                saved_count=self._saved_count,
                dropped_count=self._dropped_count,
                queue_length=self.queue.qsize(),
            )

    def enqueue_violation(self, frame: np.ndarray, bbox: Tuple[int, int, int, int], meta: Dict[str, Any]) -> bool:
        if not self.enable:
            return False

        camera_id = str(meta.get("camera_id") or self.default_camera_id)
        if self.rate_limit_seconds > 0 and not self._allow_bbox_rate(camera_id, bbox):
            self._mark_dropped("rate_limit_bbox")
            return False
        if self.rate_limit_per_minute > 0 and not self._allow_rate(camera_id):
            self._mark_dropped("rate_limit")
            return False

        detection_id = meta.get("detection_id") or uuid.uuid4().hex
        payload = {
            "frame": frame.copy(),
            "bbox": bbox,
            "meta": dict(meta, detection_id=detection_id, camera_id=camera_id),
        }

        try:
            self.queue.put_nowait(payload)
            return True
        except Full:
            self._mark_dropped("queue_full")
            return False

    def _mark_dropped(self, reason: str) -> None:
        with self._lock:
            self._dropped_count += 1
        self.logger.warning("Violation recorder dropped item (%s)", reason)

    def _allow_rate(self, camera_id: str) -> bool:
        now = time.time()
        window = self._rate_windows[camera_id]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.rate_limit_per_minute:
            return False
        window.append(now)
        return True

    def _allow_bbox_rate(self, camera_id: str, bbox: Tuple[int, int, int, int]) -> bool:
        if not bbox:
            return True
        key = (camera_id,) + tuple(int(v) for v in bbox)
        now = time.time()
        last = self._bbox_last_saved.get(key)
        if last is not None and (now - last) < self.rate_limit_seconds:
            return False
        self._bbox_last_saved[key] = now
        return True

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            self._maybe_prune()
            try:
                payload = self.queue.get(timeout=0.2)
            except Empty:
                continue

            try:
                self._process_payload(payload)
            except Exception as exc:
                self.logger.exception("Violation recorder worker error: %s", exc)
                self._mark_dropped("worker_error")
            finally:
                self.queue.task_done()

    def _process_payload(self, payload: Dict[str, Any]) -> None:
        frame = payload["frame"]
        bbox = payload["bbox"]
        meta = payload["meta"]

        camera_id = str(meta.get("camera_id") or self.default_camera_id)
        detection_id = meta.get("detection_id") or uuid.uuid4().hex
        local_now = datetime.now()
        ts_label = local_now.strftime("%Y%m%d_%H%M%S_%f")[:-3]

        camera_dir = self.base_path / camera_id
        camera_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"violation_{ts_label}_{detection_id}"
        violation_id = f"{camera_id}__{base_name}"
        image_path = camera_dir / f"{base_name}.jpg"
        crop_path = camera_dir / f"{base_name}_crop.jpg"
        thumb_path = camera_dir / f"{base_name}_thumb.jpg"
        meta_path = camera_dir / f"{base_name}.json"

        image_to_save = frame
        if self.obfuscate_faces and bbox:
            image_to_save = self._obfuscate_frame(frame, bbox)

        if self.overlay_timestamp:
            overlay_text = local_now.strftime("%Y-%m-%d %H:%M:%S")
            if camera_id:
                overlay_text = f"{overlay_text} {camera_id}"
            image_to_save = self._apply_text_overlay(image_to_save, overlay_text)

        self._atomic_write_jpeg(image_to_save, image_path)

        crop = None
        crop_file_path = None
        if self.save_crops and bbox:
            crop = self._safe_crop(frame, bbox)
            if crop is not None:
                self._atomic_write_jpeg(crop, crop_path)
                crop_file_path = str(crop_path)

        thumb_source = crop if crop is not None else image_to_save
        thumb_file_path = None
        thumbnail = self._create_thumbnail(thumb_source)
        if thumbnail is not None:
            self._atomic_write_jpeg(thumbnail, thumb_path)
            thumb_file_path = str(thumb_path)

        normalized_bbox = list(self._normalize_bbox(bbox, frame))
        frame_number = meta.get("frame_number")
        if frame_number is None:
            frame_number = meta.get("frame_id")

        meta_payload = {
            "id": violation_id,
            "timestamp": local_now.strftime("%Y-%m-%dT%H:%M:%S"),
            "camera_id": camera_id,
            "zone": meta.get("zone", ""),
            "filename": image_path.name,
            "bbox": normalized_bbox,
            "confidence": meta.get("confidence"),
            "model": meta.get("model_name") or self.model_name,
            "frame_number": frame_number,
            "thumbnail": thumb_path.name if thumb_file_path else None,
            "image_path": str(image_path),
            "crop_path": crop_file_path,
            "thumbnail_path": thumb_file_path,
            "detection_id": detection_id,
            "helmet_confidence": meta.get("helmet_confidence"),
            "person_confidence": meta.get("person_confidence"),
            "local_timestamp": local_now.isoformat(),
            "missing_ppe": meta.get("missing_ppe", "Helmet"),
            "status": meta.get("status", "new"),
        }

        self._atomic_write_json(meta_payload, meta_path)

        self._maybe_upload(meta_payload, image_path, thumb_path if thumb_file_path else None)

        self.logger.info(
            "[violation] camera=%s time=%s bbox=%s conf=%.2f file=%s",
            camera_id,
            meta_payload["timestamp"],
            normalized_bbox,
            float(meta_payload.get("confidence") or 0.0),
            image_path.name,
        )

        with self._lock:
            self._saved_count += 1

    def _normalize_bbox(self, bbox: Tuple[int, int, int, int], frame: np.ndarray) -> Tuple[int, int, int, int]:
        h, w = frame.shape[:2]
        if len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            if x2 > x1 and y2 > y1:
                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))
                return int(x1), int(y1), int(x2 - x1), int(y2 - y1)
        return 0, 0, 0, 0

    def _safe_crop(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = self._normalize_bbox(bbox, frame)
        if x2 <= 0 or y2 <= 0:
            return None
        x2 = x1 + x2
        y2 = y1 + y2
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2].copy()

    def _obfuscate_frame(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        output = frame.copy()
        h, w = frame.shape[:2]
        x1, y1, bw, bh = self._normalize_bbox(bbox, frame)
        if bw <= 0 or bh <= 0:
            return output
        x2 = min(w, x1 + bw)
        y2 = min(h, y1 + bh)
        face_height = int((y2 - y1) * self.obfuscate_ratio)
        if face_height <= 0:
            return output
        fx2 = x2
        fy2 = min(h, y1 + face_height)
        face_region = output[y1:fy2, x1:fx2]
        if face_region.size == 0:
            return output
        blurred = cv2.GaussianBlur(face_region, (31, 31), 0)
        output[y1:fy2, x1:fx2] = blurred
        return output

    def _apply_text_overlay(self, image: np.ndarray, text: str) -> np.ndarray:
        output = image.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.6
        thickness = 2
        text_size, baseline = cv2.getTextSize(text, font, scale, thickness)
        text_w, text_h = text_size
        x = 10
        y = 10 + text_h
        cv2.rectangle(
            output,
            (x - 5, y - text_h - 5),
            (x + text_w + 5, y + baseline + 5),
            (0, 0, 0),
            -1,
        )
        cv2.putText(output, text, (x, y), font, scale, (255, 255, 255), thickness)
        return output

    def _create_thumbnail(self, image: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if image is None:
            return None
        h, w = image.shape[:2]
        if w <= 0 or h <= 0:
            return None
        if w <= self.thumbnail_width:
            return image.copy()
        scale = self.thumbnail_width / float(w)
        new_h = max(1, int(h * scale))
        return cv2.resize(image, (self.thumbnail_width, new_h), interpolation=cv2.INTER_AREA)

    def _maybe_upload(self, payload: Dict[str, Any], image_path: Path, thumb_path: Optional[Path]) -> None:
        if not self.upload_enabled:
            return
        if not self.upload_endpoint:
            self.logger.warning("Violation upload enabled but no endpoint configured")
            return
        if requests is None:
            self.logger.warning("Violation upload requires 'requests' package")
            return
        try:
            with image_path.open("rb") as image_handle:
                files = {
                    "image": (image_path.name, image_handle, "image/jpeg"),
                }
                thumb_handle = None
                if thumb_path and thumb_path.exists():
                    thumb_handle = thumb_path.open("rb")
                    files["thumbnail"] = (thumb_path.name, thumb_handle, "image/jpeg")
                try:
                    response = requests.post(
                        self.upload_endpoint,
                        data={"metadata": json.dumps(payload)},
                        files=files,
                        timeout=self.upload_timeout,
                    )
                    if response.status_code >= 300:
                        self.logger.warning("Violation upload failed (%s)", response.status_code)
                finally:
                    if thumb_handle:
                        thumb_handle.close()
        except Exception as exc:
            self.logger.warning("Violation upload error (%s)", exc)

    def _atomic_write_jpeg(self, image: np.ndarray, target_path: Path) -> None:
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        for attempt in range(3):
            try:
                success, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
                if not success:
                    raise OSError("Failed to encode JPEG")
                with open(tmp_path, "wb") as handle:
                    handle.write(encoded.tobytes())
                os.replace(tmp_path, target_path)
                self._set_file_permissions(target_path)
                return
            except OSError as exc:
                if exc.errno in (errno.ENOSPC, errno.EACCES):
                    self.logger.warning("Unable to save %s (%s)", target_path, exc)
                    return
                if attempt == 2:
                    self.logger.warning("Failed to save %s (%s)", target_path, exc)
                    return
                time.sleep(0.05 * (attempt + 1))
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

    def _atomic_write_json(self, payload: Dict[str, Any], target_path: Path) -> None:
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        for attempt in range(3):
            try:
                with open(tmp_path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                os.replace(tmp_path, target_path)
                self._set_file_permissions(target_path)
                return
            except OSError as exc:
                if exc.errno in (errno.ENOSPC, errno.EACCES):
                    self.logger.warning("Unable to save %s (%s)", target_path, exc)
                    return
                if attempt == 2:
                    self.logger.warning("Failed to save %s (%s)", target_path, exc)
                    return
                time.sleep(0.05 * (attempt + 1))
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

    def _set_file_permissions(self, path: Path) -> None:
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass

    def _maybe_prune(self) -> None:
        if self.retention_days <= 0:
            return
        now = time.time()
        if now - self._last_prune_at < self._prune_interval_sec:
            return
        self._last_prune_at = now
        cutoff = now - (self.retention_days * 86400)
        try:
            self._prune_old_files(cutoff)
        except Exception as exc:
            self.logger.warning("Violation retention cleanup failed (%s)", exc)

    def _prune_old_files(self, cutoff: float) -> None:
        if not self.base_path.exists():
            return
        for root, _, files in os.walk(self.base_path):
            for name in files:
                path = Path(root) / name
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError as exc:
                    self.logger.warning("Unable to prune %s (%s)", path, exc)
