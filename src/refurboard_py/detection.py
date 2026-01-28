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
    
    def __init__(self, quad_vertices: List[Tuple[float, float]], expand_pct: float = 0.12) -> None:
        """
        Initialize with 4 camera-space points defining the valid region.
        Points should be in order: top_left, top_right, bottom_right, bottom_left.
        
        Args:
            quad_vertices: 4 camera-space calibration points
            expand_pct: Expand the quad outward by this percentage (default 12%)
                        to cover screen edges beyond calibration targets
        """
        if len(quad_vertices) < 4:
            raise ValueError("QuadFilter requires exactly 4 vertices")
        
        pts = np.array(quad_vertices, dtype=np.float32)
        
        # Expand quad outward from centroid to cover screen edges
        centroid = pts.mean(axis=0)
        expanded = centroid + (pts - centroid) * (1.0 + expand_pct)
        
        # Convert to contour format for cv2.pointPolygonTest
        self._contour = expanded.reshape((-1, 1, 2))
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


class StationarySourceFilter:
    """
    Detects and filters out stationary IR sources (LEDs, reflections) that remain
    in roughly the same position for many frames. The real pen should be moving
    with user input, while spurious sources stay fixed.
    """
    
    def __init__(self, stationary_threshold: float = 8.0, history_frames: int = 30) -> None:
        """
        Args:
            stationary_threshold: Max movement (pixels) for a source to be considered stationary
            history_frames: Number of frames to track position history
        """
        self.stationary_threshold = stationary_threshold
        self.history_frames = history_frames
        # Track: {blob_id: (positions_history, total_movement)}
        self._sources: dict[int, Tuple[List[Tuple[float, float]], float]] = {}
        self._next_id = 0
        self._association_radius_sq = 25.0 ** 2  # 25px to match across frames
        
    def update_and_filter(self, blobs: List[IrBlob]) -> List[IrBlob]:
        """
        Update source tracking and return only blobs that appear to be moving (the pen).
        Stationary sources are filtered out.
        """
        if not blobs:
            return []
        
        # Match blobs to existing tracked sources
        unmatched_blobs = list(blobs)
        updated_sources: dict[int, Tuple[List[Tuple[float, float]], float]] = {}
        stationary_positions: set[Tuple[float, float]] = set()
        
        for source_id, (history, total_movement) in self._sources.items():
            if not history:
                continue
            last_pos = history[-1]
            best_match: IrBlob | None = None
            best_dist_sq = float('inf')
            
            for blob in unmatched_blobs:
                dx = blob.center[0] - last_pos[0]
                dy = blob.center[1] - last_pos[1]
                dist_sq = dx * dx + dy * dy
                if dist_sq < self._association_radius_sq and dist_sq < best_dist_sq:
                    best_match = blob
                    best_dist_sq = dist_sq
            
            if best_match is not None:
                unmatched_blobs.remove(best_match)
                # Update history
                new_history = history + [best_match.center]
                if len(new_history) > self.history_frames:
                    new_history = new_history[-self.history_frames:]
                # Calculate total movement over history
                movement = self._calculate_movement(new_history)
                updated_sources[source_id] = (new_history, movement)
                
                # If stationary for enough frames, mark this position
                if len(new_history) >= 10 and movement < self.stationary_threshold:
                    stationary_positions.add((round(best_match.center[0], 0), round(best_match.center[1], 0)))
        
        # Create new sources for unmatched blobs
        for blob in unmatched_blobs:
            updated_sources[self._next_id] = ([blob.center], 999.0)  # Start with high movement
            self._next_id += 1
        
        self._sources = updated_sources
        
        # Filter out stationary blobs
        moving_blobs = []
        for blob in blobs:
            is_stationary = False
            for source_id, (history, movement) in self._sources.items():
                if not history:
                    continue
                dx = blob.center[0] - history[-1][0]
                dy = blob.center[1] - history[-1][1]
                if dx * dx + dy * dy < 4:  # Same blob
                    if len(history) >= 10 and movement < self.stationary_threshold:
                        is_stationary = True
                    break
            if not is_stationary:
                moving_blobs.append(blob)
        
        return moving_blobs
    
    def _calculate_movement(self, history: List[Tuple[float, float]]) -> float:
        """Calculate total movement distance over position history."""
        if len(history) < 2:
            return 999.0
        total = 0.0
        for i in range(1, len(history)):
            dx = history[i][0] - history[i-1][0]
            dy = history[i][1] - history[i-1][1]
            total += (dx * dx + dy * dy) ** 0.5
        return total
    
    def get_stationary_sources(self) -> List[Tuple[float, float]]:
        """Return positions of detected stationary sources for debugging."""
        stationary = []
        for source_id, (history, movement) in self._sources.items():
            if len(history) >= 10 and movement < self.stationary_threshold:
                stationary.append(history[-1])
        return stationary
    
    def reset(self) -> None:
        """Clear tracking state."""
        self._sources.clear()


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


class OneEuroFilter:
    """
    One-Euro Filter for smooth, low-latency pointer tracking.
    
    Automatically adapts filtering based on movement speed:
    - Slow movement → heavy filtering (removes jitter)
    - Fast movement → light filtering (responsive, low latency)
    
    Reference: Casiez et al. "1€ Filter: A Simple Speed-based Low-pass Filter
    for Noisy Input in Interactive Systems" (CHI 2012)
    """
    
    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
        reacquire_frames: int = 1,
        reacquire_radius: float = 0.25,
    ) -> None:
        """
        Args:
            min_cutoff: Minimum cutoff frequency in Hz. Lower = more smoothing
                        at low speeds. Try 0.5-2.0 for drawing.
            beta: Speed coefficient. Higher = less lag at high speeds.
                  Try 0.001-0.01 for drawing.
            d_cutoff: Cutoff frequency for derivative estimation.
            reacquire_frames: Frames needed to trust position after pen lost.
                              1 = immediate (good for drawing), 3+ = strict (filters reflections)
            reacquire_radius: Max normalized movement (0-1) to count as stable.
                              0.25 = 25% of screen diagonal movement allowed.
        """
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reacquire_frames = reacquire_frames
        self.reacquire_radius = reacquire_radius
        
        # State
        self._x: Optional[np.ndarray] = None  # Filtered position
        self._dx: Optional[np.ndarray] = None  # Filtered derivative
        self._last_time: Optional[float] = None
        
        # Reacquisition state
        self._candidate: Optional[np.ndarray] = None
        self._candidate_frames: int = 0
    
    def reset(self) -> None:
        """Clear filter state when pen is lost."""
        self._x = None
        self._dx = None
        self._last_time = None
        self._candidate = None
        self._candidate_frames = 0
    
    def _smoothing_factor(self, cutoff: float, dt: float) -> float:
        """Compute exponential smoothing factor from cutoff frequency."""
        tau = 1.0 / (2.0 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)
    
    def update(
        self, value: tuple[float, float], timestamp: float | None = None
    ) -> tuple[float, float] | None:
        """
        Filter a new position sample.
        
        Args:
            value: Raw (x, y) position in normalized coords [0, 1].
            timestamp: Time in seconds. If None, assumes 60fps.
        
        Returns:
            Filtered (x, y) position, or None during reacquisition.
        """
        import time
        
        current = np.array(value, dtype=np.float64)
        now = timestamp if timestamp is not None else time.perf_counter()
        
        if self._x is None:
            # Reacquisition mode
            if self.reacquire_frames <= 0:
                # Disabled - accept immediately
                self._x = current
                self._dx = np.zeros(2, dtype=np.float64)
                self._last_time = now
                return float(self._x[0]), float(self._x[1])
            
            if self._candidate is None:
                self._candidate = current
                self._candidate_frames = 1
                self._last_time = now
                return None
            
            dist = float(np.linalg.norm(current - self._candidate))
            if dist < self.reacquire_radius:
                self._candidate_frames += 1
                self._candidate = 0.7 * self._candidate + 0.3 * current
                
                if self._candidate_frames >= self.reacquire_frames:
                    self._x = self._candidate
                    self._dx = np.zeros(2, dtype=np.float64)
                    self._candidate = None
                    self._candidate_frames = 0
                    self._last_time = now
                    return float(self._x[0]), float(self._x[1])
                return None
            else:
                self._candidate = current
                self._candidate_frames = 1
                return None
        
        # Normal filtering
        dt = now - self._last_time if self._last_time else 1.0 / 60.0
        dt = max(dt, 1e-6)  # Prevent division by zero
        self._last_time = now
        
        # Estimate derivative (velocity)
        dx = (current - self._x) / dt
        
        # Filter the derivative
        alpha_d = self._smoothing_factor(self.d_cutoff, dt)
        self._dx = alpha_d * dx + (1.0 - alpha_d) * self._dx
        
        # Compute adaptive cutoff based on filtered speed
        speed = float(np.linalg.norm(self._dx))
        cutoff = self.min_cutoff + self.beta * speed
        
        # Filter the position
        alpha = self._smoothing_factor(cutoff, dt)
        self._x = alpha * current + (1.0 - alpha) * self._x
        
        return float(self._x[0]), float(self._x[1])


class Smoother:
    def __init__(self, factor: float, max_step: float | None = None, reacquire_frames: int = 1) -> None:
        self.factor = factor
        self.max_step = max_step
        self.reacquire_frames = reacquire_frames  # Frames needed to trust new position after reset
        self._value: Optional[np.ndarray] = None
        self._candidate: Optional[np.ndarray] = None  # Candidate position during reacquisition
        self._candidate_frames: int = 0
        self._reacquire_radius: float = 0.25  # Max normalized movement (25% of screen) to count as stable

    def reset(self) -> None:
        """Clear smoothing state to prevent drift from stale data."""
        self._value = None
        self._candidate = None
        self._candidate_frames = 0

    def update(self, value: tuple[float, float]) -> tuple[float, float] | None:
        """
        Update smoother with new position.
        Returns smoothed position, or None if reacquisition is in progress.
        """
        current = np.array(value, dtype=np.float32)
        
        if self._value is None:
            # Check if reacquisition is disabled
            if self.reacquire_frames <= 0:
                # No reacquisition - accept immediately
                self._value = current
                return float(self._value[0]), float(self._value[1])
            
            # Reacquisition mode: pen was lost, need stable position before trusting
            if self._candidate is None:
                # First frame after reset - start tracking candidate
                self._candidate = current
                self._candidate_frames = 1
                return None  # Don't move cursor yet
            else:
                # Check if new position is close to candidate
                dist = float(np.linalg.norm(current - self._candidate))
                if dist < self._reacquire_radius:
                    # Position is stable, increment counter
                    self._candidate_frames += 1
                    # Update candidate with average
                    self._candidate = 0.7 * self._candidate + 0.3 * current
                    
                    if self._candidate_frames >= self.reacquire_frames:
                        # Stable for enough frames - accept position
                        self._value = self._candidate
                        self._candidate = None
                        self._candidate_frames = 0
                        return float(self._value[0]), float(self._value[1])
                    return None  # Still waiting for stability
                else:
                    # Position jumped - restart candidate tracking
                    self._candidate = current
                    self._candidate_frames = 1
                    return None
        else:
            # Normal tracking mode
            prev = self._value
            blended = (1 - self.factor) * self._value + self.factor * current
            if self.max_step is not None:
                delta = blended - prev
                step = float(np.linalg.norm(delta))
                if step > self.max_step > 0:
                    delta *= self.max_step / step
                    blended = prev + delta
            self._value = blended
            # Reset candidate tracking since we have good lock
            self._candidate = None
            self._candidate_frames = 0
            return float(self._value[0]), float(self._value[1])
