"""Communication topology simulation for UAV-ground station network."""

import random
import math
from dataclasses import dataclass, field


@dataclass
class TopoNode:
    id: str
    name: str
    node_type: str  # "ground", "drone", "relay"
    signal_strength: float  # dBm, range typically -30 to -90
    lat: float
    lng: float
    connected: bool = True


@dataclass
class TopoLink:
    source: str
    target: str
    signal_quality: float  # 0-100%
    latency_ms: float


@dataclass
class TopologyState:
    nodes: list[TopoNode] = field(default_factory=list)
    links: list[TopoLink] = field(default_factory=list)

    def initialize_default(self, drone_lat: float, drone_lng: float):
        """Create a default topology with ground station, drone, and relay nodes."""

        # Ground station at a fixed point on campus
        gs_lat, gs_lng = 31.9375, 118.8990

        self.nodes = [
            TopoNode("GS", "地面站", "ground", -40.0, gs_lat, gs_lng),
            TopoNode("DRONE", "无人机", "drone", -55.0, drone_lat, drone_lng),
            TopoNode("RL1", "中继节点1", "relay", -50.0,
                     (gs_lat + drone_lat) / 2 + 0.0002,
                     (gs_lng + drone_lng) / 2 - 0.0001),
            TopoNode("RL2", "中继节点2", "relay", -52.0,
                     (gs_lat + drone_lat) / 2 - 0.0001,
                     (gs_lng + drone_lng) / 2 + 0.0002),
        ]

        self._update_links()

    def update_drone_position(self, lat: float, lng: float):
        """Update drone position and recalculate signal strengths."""
        for node in self.nodes:
            if node.id == "DRONE":
                node.lat = lat
                node.lng = lng
                break

        # Simulate signal strength based on distance to ground station
        gs = next(n for n in self.nodes if n.id == "GS")
        dist = self._haversine(gs.lat, gs.lng, lat, lng)
        # Signal degrades with distance (simplified free-space path loss)
        signal = -40 - 20 * math.log10(max(dist, 1))
        signal = max(-90, min(-30, signal))

        for node in self.nodes:
            if node.id == "DRONE":
                node.signal_strength = signal
                node.connected = signal > -80

        self._update_links()

    def _update_links(self):
        self.links = []
        node_map = {n.id: n for n in self.nodes}

        # Connect ground station to relays
        for rid in ["RL1", "RL2"]:
            if rid in node_map:
                rl = node_map[rid]
                gs = node_map["GS"]
                dist = self._haversine(gs.lat, gs.lng, rl.lat, rl.lng)
                quality = max(0, 100 - dist * 100)
                latency = 5 + dist * 0.1 + random.uniform(-1, 1)
                self.links.append(TopoLink("GS", rid, quality, latency))

        # Connect drone to relays and directly to GS
        drone = node_map.get("DRONE")
        if drone and drone.connected:
            for src_id in ["RL1", "RL2", "GS"]:
                if src_id in node_map:
                    src = node_map[src_id]
                    dist = self._haversine(src.lat, src.lng, drone.lat, drone.lng)
                    quality = max(0, 100 - dist * 100)
                    latency = 5 + dist * 0.1 + random.uniform(-1, 1)
                    self.links.append(TopoLink(src_id, "DRONE", quality, latency))

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Distance in km."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
