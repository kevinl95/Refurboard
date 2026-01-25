"""IR blob detection and adaptive click heuristics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class IrBlob:
    center: tuple[float, float]
    area: float
    intensity: float
    confidence: float


class QuadFilter:
    """Filters blobs to only those inside a camera-space quadrilateral."""
    
    def __init__(self, quad_vertices: List[Tuple[float, float]]) -> None:
        """
        Initialize with 4 camera-space points defining the valid region.
        Points should be in order: top_left, top_right, bottom_right, bottom_left.
        """
        if len(quad_vertices) < 4:
            raise ValueError("QuadFilter requires exactly 4 vertices")
        # Convert to numpy array for cv2.pointPolygonTest
        self._contour = np.array(quad_vertices, dtype=np.float32).reshape((-1, 1, 2))
        # Compute convex hull to handle any ordering issues
        self._hull = cv2.convexHull(self._contour)
        
    def contains(self, point: Tuple[float, float]) -> bool:
        """Check if a point is inside the quadrilateral."""
        result = cv2.pointPolygonTest(self._hull, point, False)
        return result >= 0  # >= 0 means inside or on edge
    
    def filter_blobs(self, blobs: List[IrBlob]) -> List[IrBlob]:
        """Return only blobs whose centers are inside the quad."""
        return [blob for blob in blobs if self.contains(blob.center)]


class BlobTracker:
    """
    Requires blobs to persist for N consecutive frames before accepting them.
    This eliminates transient noise/spurious detections.
    """
    
    def __init__(self, persistence_frames: int = 3, association_radius: float = 20.0) -> None:
        """
        Args:
            persistence_frames: Number of consecutive frames a blob must be seen
            association_radius: Max distance to consider a blob the same across frames
        """
        self.persistence_frames = persistence_frames
        self.association_radius_sq = association_radius ** 2
        # Track: {blob_id: (last_position, consecutive_count, last_blob)}
        self._tracks: dict[int, Tuple[Tuple[float, float], int, IrBlob]] = {}
        self._next_id = 0
        
    def update(self, blobs: List[IrBlob]) -> List[IrBlob]:
        """
        Update tracker with new frame's blobs.
        Returns only blobs that have persisted for enough frames.
        """
        if not blobs:
            self._tracks.clear()
            return []
        
        # Match new blobs to existing tracks
        unmatched_blobs = list(blobs)
        updated_tracks: dict[int, Tuple[Tuple[float, float], int, IrBlob]] = {}
        
        for track_id, (last_pos, count, _) in self._tracks.items():
            best_match: IrBlob | None = None
            best_dist_sq = float('inf')
            
            for blob in unmatched_blobs:
                dx = blob.center[0] - last_pos[0]
                dy = blob.center[1] - last_pos[1]
                dist_sq = dx * dx + dy * dy
                if dist_sq < self.association_radius_sq and dist_sq < best_dist_sq:
                    best_match = blob
                    best_dist_sq = dist_sq
            
            if best_match is not None:
                unmatched_blobs.remove(best_match)
                updated_tracks[track_id] = (best_match.center, count + 1, best_match)
        
        # Create new tracks for unmatched blobs
        for blob in unmatched_blobs:
            updated_tracks[self._next_id] = (blob.center, 1, blob)
            self._next_id += 1
        
        self._tracks = updated_tracks
        
        # Return blobs that have persisted long enough
        persistent = [
            blob for (_, count, blob) in self._tracks.values()
            if count >= self.persistence_frames
        ]
        
        # Sort by quality (same as IrBlobDetector)
        persistent.sort(key=lambda b: (b.intensity * 0.7) + (b.area * 0.3), reverse=True)
        return persistent
    
    def reset(self) -> None:
        """Clear all tracking state."""
        self._tracks.clear()


class AdaptiveThreshold:
    """Learns background intensity and produces a dynamic trigger level."""

    def __init__(self, sensitivity: float, hysteresis: float) -> None:
        self.sensitivity = sensitivity
        self.hysteresis = hysteresis
        self.baseline = 0.0
        self.state = False

    def evaluate(self, signal: float) -> bool:
        if self.baseline == 0:
            self.baseline = signal
        else:
            self.baseline = (0.98 * self.baseline) + (0.02 * signal)

        high = self.baseline + (self.baseline * self.sensitivity)
        low = high * (1.0 - self.hysteresis)

        if self.state:
            self.state = signal >= low
        else:
            self.state = signal >= high
        return self.state

    def reset(self) -> None:
        self.baseline = 0.0
        self.state = False


class IrBlobDetector:
    def __init__(self, min_area: int, max_area: int) -> None:
        self.min_area = min_area
        self.max_area = max_area

    def find_blobs(self, frame) -> List[IrBlob]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blobs: List[IrBlob] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not self.min_area <= area <= self.max_area:
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            cx = float(moments["m10"] / moments["m00"])
            cy = float(moments["m01"] / moments["m00"])
            mask = np.zeros(gray.shape, dtype="uint8")
            cv2.drawContours(mask, [contour], -1, 255, -1)
            intensity = float(cv2.mean(gray, mask=mask)[0])
            confidence = min(1.0, (intensity / 255.0) * 0.7 + (area / self.max_area) * 0.3)
            blobs.append(IrBlob(center=(cx, cy), area=area, intensity=intensity, confidence=confidence))
        blobs.sort(key=lambda blob: (blob.intensity * 0.7) + (blob.area * 0.3), reverse=True)
        return blobs


class Smoother:
    def __init__(self, factor: float, max_step: float | None = None) -> None:
        self.factor = factor
        self.max_step = max_step
        self._value: Optional[np.ndarray] = None

    def update(self, value: tuple[float, float]) -> tuple[float, float]:
        current = np.array(value, dtype=np.float32)
        if self._value is None:
            self._value = current
        else:
            prev = self._value
            blended = (1 - self.factor) * self._value + self.factor * current
            if self.max_step is not None:
                delta = blended - prev
                step = float(np.linalg.norm(delta))
                if step > self.max_step > 0:
                    delta *= self.max_step / step
                    blended = prev + delta
            self._value = blended
        return float(self._value[0]), float(self._value[1])
