"""
DBSCAN-inspired GPS clustering.
eps = 500 metres (Haversine), min_samples = 1.
Pure Python — no scikit-learn dependency.
"""
import math


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two GPS points."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cluster_by_gps(
    items: list[dict],
    eps_m: float = 500.0,
) -> list[dict]:
    """
    Assign cluster_id to each item.
    Items without gps_lat/gps_lng -> cluster_id = -1 ("Unknown Location").
    Returns new list of dicts with added 'cluster_id' field.
    """
    n = len(items)
    cluster_ids = [-1] * n
    current_cluster = 0

    gps_items = [
        (i, item['gps_lat'], item['gps_lng'])
        for i, item in enumerate(items)
        if item.get('gps_lat') is not None and item.get('gps_lng') is not None
    ]

    visited: set[int] = set()

    for idx, (i, lat, lng) in enumerate(gps_items):
        if i in visited:
            continue
        visited.add(i)
        neighbours = _range_query(gps_items, lat, lng, eps_m)
        cluster_ids[i] = current_cluster
        seed_set = list(neighbours)
        while seed_set:
            j, j_lat, j_lng = seed_set.pop()
            if j not in visited:
                visited.add(j)
                j_neighbours = _range_query(gps_items, j_lat, j_lng, eps_m)
                seed_set.extend(j_neighbours)
            if cluster_ids[j] == -1:
                cluster_ids[j] = current_cluster
        current_cluster += 1

    return [
        {**item, 'cluster_id': cluster_ids[i]}
        for i, item in enumerate(items)
    ]


def _range_query(
    gps_items: list[tuple],
    lat: float,
    lng: float,
    eps_m: float,
) -> list[tuple]:
    return [
        (i, ilat, ilng)
        for i, ilat, ilng in gps_items
        if haversine_m(lat, lng, ilat, ilng) <= eps_m
    ]


def compute_cluster_centroids(items: list[dict]) -> dict[int, dict]:
    """
    Return {cluster_id: {lat, lng}} for all clusters.
    cluster_id = -1 (no GPS) is excluded.
    """
    clusters: dict[int, list] = {}
    for item in items:
        cid = item.get('cluster_id', -1)
        if cid == -1:
            continue
        clusters.setdefault(cid, []).append((item['gps_lat'], item['gps_lng']))

    return {
        cid: {
            'lat': sum(p[0] for p in points) / len(points),
            'lng': sum(p[1] for p in points) / len(points),
        }
        for cid, points in clusters.items()
    }
