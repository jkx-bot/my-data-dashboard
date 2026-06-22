"""Flight simulation engine — simulates UAV movement along waypoints."""

import time
import math
import threading
from dataclasses import dataclass, field

from .route import Point


@dataclass
class FlightState:
    waypoints: list[Point] = field(default_factory=list)
    speed: float = 10.0  # m/s
    current_wp_index: int = 0
    current_position: Point | None = None
    elapsed_time: float = 0.0
    remaining_distance: float = 0.0
    total_distance: float = 0.0
    eta_seconds: float = 0.0
    battery: float = 100.0  # percentage
    flying: bool = False
    completed: bool = False
    position_history: list[Point] = field(default_factory=list)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _start_time: float = 0.0

    def start_flight(self, waypoints: list[Point], speed: float):
        if self.flying:
            return
        self.waypoints = waypoints
        self.speed = speed
        self.current_wp_index = 0
        self.current_position = waypoints[0] if waypoints else None
        self.elapsed_time = 0.0
        self.battery = 100.0
        self.flying = True
        self.completed = False
        self.position_history = []

        # Calculate total distance
        total = 0.0
        for i in range(len(waypoints) - 1):
            total += waypoints[i].distance_to(waypoints[i + 1])
        self.total_distance = total
        self.remaining_distance = total
        self.eta_seconds = total / speed if speed > 0 else 0

        self._start_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_flight(self):
        self.flying = False
        self.completed = False

    def _run(self):
        """Main flight loop — moves the drone along waypoints."""
        while self.flying and self.current_wp_index < len(self.waypoints) - 1:
            wp_from = self.waypoints[self.current_wp_index]
            wp_to = self.waypoints[self.current_wp_index + 1]
            segment_dist = wp_from.distance_to(wp_to)

            if segment_dist < 0.1:
                with self._lock:
                    self.current_wp_index += 1
                continue

            segment_time = segment_dist / self.speed
            segment_start = time.time()

            while True:
                now = time.time()
                elapsed_seg = now - segment_start

                if elapsed_seg >= segment_time:
                    # Arrived at next waypoint
                    with self._lock:
                        self.current_wp_index += 1
                        self.current_position = wp_to
                        self.elapsed_time = now - self._start_time
                    break

                fraction = elapsed_seg / segment_time
                current_lng = wp_from.lng + (wp_to.lng - wp_from.lng) * fraction
                current_lat = wp_from.lat + (wp_to.lat - wp_from.lat) * fraction

                with self._lock:
                    self.current_position = Point(current_lng, current_lat)
                    self.position_history.append(Point(current_lng, current_lat))
                    self.elapsed_time = now - self._start_time
                    # Calculate remaining distance
                    remaining = 0.0
                    cp = Point(current_lng, current_lat)
                    remaining += cp.distance_to(wp_to)
                    for i in range(self.current_wp_index + 1, len(self.waypoints) - 1):
                        remaining += self.waypoints[i].distance_to(self.waypoints[i + 1])
                    self.remaining_distance = remaining
                    self.eta_seconds = remaining / self.speed if self.speed > 0 else 0
                    # Battery drain: ~0.05% per second of flight
                    self.battery = max(0, 100 - self.elapsed_time * 0.05)

                time.sleep(0.1)  # 10 Hz update

        with self._lock:
            if self.current_wp_index >= len(self.waypoints) - 1:
                self.current_position = self.waypoints[-1] if self.waypoints else None
                self.elapsed_time = time.time() - self._start_time
                self.remaining_distance = 0.0
                self.eta_seconds = 0.0
                self.flying = False
                self.completed = True

    def get_snapshot(self) -> dict:
        """Thread-safe snapshot of current flight state."""
        with self._lock:
            return {
                "current_wp": self.current_wp_index,
                "total_wp": len(self.waypoints),
                "position": self.current_position,
                "elapsed_time": self.elapsed_time,
                "remaining_distance": self.remaining_distance,
                "total_distance": self.total_distance,
                "eta_seconds": self.eta_seconds,
                "battery": self.battery,
                "speed": self.speed,
                "flying": self.flying,
                "completed": self.completed,
                "trail": list(self.position_history),
            }
