"""Route planning with obstacle avoidance for UAV flight paths."""

import math
import heapq
from dataclasses import dataclass


@dataclass
class Point:
    lng: float
    lat: float

    def distance_to(self, other: "Point") -> float:
        """Haversine distance in meters."""
        R = 6371000
        dlat = math.radians(other.lat - self.lat)
        dlng = math.radians(other.lng - self.lng)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(self.lat)) * math.cos(math.radians(other.lat)) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class Obstacle:
    lng: float
    lat: float
    radius: float  # meters
    height: float = 50.0  # meters, obstacle height above ground


def _interpolate(p1: Point, p2: Point, fraction: float) -> Point:
    return Point(p1.lng + (p2.lng - p1.lng) * fraction,
                 p1.lat + (p2.lat - p1.lat) * fraction)


def _offset_point(p: Point, offset_lng: float, offset_lat: float) -> Point:
    """Offset a point by meters (approximate for small distances)."""
    meters_per_deg_lat = 111320.0
    meters_per_deg_lng = 111320.0 * math.cos(math.radians(p.lat))
    return Point(p.lng + offset_lng / meters_per_deg_lng,
                 p.lat + offset_lat / meters_per_deg_lat)


def plan_route(start: Point, end: Point, obstacles: list[Obstacle],
               safety_radius: float, strategy: str,
               flight_height: float) -> list[Point]:
    """
    Plan a route from start to end avoiding obstacles.

    strategy: "left", "right", "optimal"
    Only obstacles taller than flight_height require detouring;
    obstacles shorter than flight_height are flown over.
    Returns list of waypoints including start and end.
    """
    # Only consider obstacles that are taller than the flight height
    blocking = [o for o in obstacles if o.height >= flight_height]

    effective_obstacles = [
        Obstacle(o.lng, o.lat, o.radius + safety_radius, o.height) for o in blocking
    ]

    # Find which obstacles intersect the direct path
    intersecting = _find_intersecting(start, end, effective_obstacles)

    if not intersecting:
        return [start, end]

    if strategy == "left":
        return _detour_route(start, end, intersecting, effective_obstacles, side="left")
    elif strategy == "right":
        return _detour_route(start, end, intersecting, effective_obstacles, side="right")
    else:  # optimal
        return _a_star_route(start, end, effective_obstacles)


def _find_intersecting(start: Point, end: Point,
                       obstacles: list[Obstacle]) -> list[Obstacle]:
    """Find obstacles that intersect the line from start to end."""
    result = []
    for obs in obstacles:
        dist = _point_to_segment_distance(obs, start, end)
        if dist < obs.radius:
            result.append(obs)
    return result


def _point_to_segment_distance(obs: Obstacle, a: Point, b: Point) -> float:
    """Minimum distance from obstacle center to line segment AB in meters."""
    obs_pt = Point(obs.lng, obs.lat)
    ab_dist = a.distance_to(b)
    if ab_dist < 0.01:
        return obs_pt.distance_to(a)

    # Project point onto line
    a_to_obs = obs_pt.distance_to(a)
    b_to_obs = obs_pt.distance_to(b)

    # Use law of cosines to find projection
    cos_a = (a_to_obs ** 2 + ab_dist ** 2 - b_to_obs ** 2) / (2 * a_to_obs * ab_dist + 1e-10)
    cos_a = max(-1, min(1, cos_a))
    proj_dist = a_to_obs * cos_a

    if proj_dist < 0:
        return a_to_obs
    if proj_dist > ab_dist:
        return b_to_obs

    return abs(a_to_obs * math.sqrt(1 - cos_a ** 2))


def _detour_route(start: Point, end: Point, obs_list: list[Obstacle],
                  all_obs: list[Obstacle], side: str) -> list[Point]:
    """Create a detour route going left or right around obstacles."""
    if not obs_list:
        return [start, end]

    # Find the largest intersecting obstacle
    largest = max(obs_list, key=lambda o: o.radius)

    # Calculate perpendicular direction
    dx = end.lng - start.lng
    dy = end.lat - start.lat
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-10:
        return [start, end]

    if side == "left":
        perp_lng, perp_lat = -dy / length, dx / length
    else:
        perp_lng, perp_lat = dy / length, -dx / length

    # Offset distance
    offset_dist = largest.radius * 1.5  # 50% extra clearance

    # Convert to meters
    meters_per_deg_lat = 111320.0
    meters_per_deg_lng = 111320.0 * math.cos(math.radians(largest.lat))

    offset_lng = perp_lng * offset_dist / meters_per_deg_lng
    offset_lat = perp_lat * offset_dist / meters_per_deg_lat

    # Create midpoint offset from the obstacle center
    mid_lng_c = (start.lng + end.lng) / 2
    mid_lat_c = (start.lat + end.lat) / 2

    # But actually offset from the obstacle center
    mid_lng = largest.lng + offset_lng
    mid_lat = largest.lat + offset_lat

    # Add some intermediate points to make a smoother curve
    mid = Point(mid_lng, mid_lat)

    # Check if the detour is clear
    if not _find_intersecting(start, mid, all_obs) and not _find_intersecting(mid, end, all_obs):
        return [start, mid, end]

    # If still intersecting, move further out
    offset_lng *= 2
    offset_lat *= 2
    mid2 = Point(largest.lng + offset_lng, largest.lat + offset_lat)
    return [start, mid2, end]


def _a_star_route(start: Point, end: Point,
                  obstacles: list[Obstacle]) -> list[Point]:
    """A* pathfinding around obstacles using a grid of candidate waypoints."""
    # Generate candidate waypoints: start, end, and tangent points around obstacles
    candidates = [start, end]

    for obs in obstacles:
        # Generate 8 points around each obstacle at safe distance
        meters_per_deg_lat = 111320.0
        meters_per_deg_lng = 111320.0 * math.cos(math.radians(obs.lat))
        safe_r = obs.radius * 1.3
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            dlng = safe_r * math.cos(rad) / meters_per_deg_lng
            dlat = safe_r * math.sin(rad) / meters_per_deg_lat
            candidates.append(Point(obs.lng + dlng, obs.lat + dlat))

    # Build graph: connect points that don't intersect obstacles
    n = len(candidates)
    graph: list[list[tuple[int, float]]] = [[] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            dist = candidates[i].distance_to(candidates[j])
            if dist > 1000:  # Skip very long edges
                continue
            if not _find_intersecting(candidates[i], candidates[j], obstacles):
                graph[i].append((j, dist))
                graph[j].append((i, dist))

    # A* on the graph
    start_idx, end_idx = 0, 1
    queue = [(0, start_idx, [start_idx])]
    visited: dict[int, float] = {start_idx: 0}

    while queue:
        f, current, path = heapq.heappop(queue)
        if current == end_idx:
            return [candidates[i] for i in path]

        g = visited[current]
        for neighbor, edge_cost in graph[current]:
            new_g = g + edge_cost
            if neighbor not in visited or new_g < visited[neighbor]:
                visited[neighbor] = new_g
                h = candidates[neighbor].distance_to(end)
                heapq.heappush(queue, (new_g + h, neighbor, path + [neighbor]))

    return [start, end]


def calculate_route_stats(waypoints: list[Point], speed: float = 10.0) -> dict:
    """Calculate route statistics."""
    total_dist = 0.0
    segments = []
    for i in range(len(waypoints) - 1):
        d = waypoints[i].distance_to(waypoints[i + 1])
        total_dist += d
        segments.append(d)

    eta = total_dist / speed if speed > 0 else 0

    return {
        "total_distance": total_dist,
        "num_waypoints": len(waypoints),
        "segments": segments,
        "eta_seconds": eta,
    }
