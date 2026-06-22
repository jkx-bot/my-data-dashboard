"""Heartbeat simulation — UAV sends heartbeat packets, ground station monitors."""

import time
import threading
from dataclasses import dataclass, field


@dataclass
class HeartbeatPacket:
    seq: int
    timestamp: float


@dataclass
class HeartbeatState:
    packets: list[HeartbeatPacket] = field(default_factory=list)
    running: bool = False
    timeout: bool = False
    last_received: float = 0.0
    seq: int = 0
    _thread: threading.Thread | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self):
        if self.running:
            return
        self.running = True
        self.timeout = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self.last_received = 0.0

    def _run(self):
        while self.running:
            self.seq += 1
            packet = HeartbeatPacket(seq=self.seq, timestamp=time.time())
            with self._lock:
                self.packets.append(packet)
                self.last_received = time.time()
                self.timeout = False
                # Keep only last 60 packets
                if len(self.packets) > 60:
                    self.packets = self.packets[-60:]
            time.sleep(1)

    def check_timeout(self) -> bool:
        with self._lock:
            if self.last_received == 0:
                return False
            now = time.time()
            if now - self.last_received > 3.0:
                self.timeout = True
                return True
            return False

    def trigger_timeout(self):
        """Simulate connection loss by freezing last_received."""
        with self._lock:
            self.last_received = time.time() - 5.0
            self.timeout = True

    def reset(self):
        with self._lock:
            self.packets.clear()
            self.timeout = False
            self.last_received = 0.0
            self.seq = 0
