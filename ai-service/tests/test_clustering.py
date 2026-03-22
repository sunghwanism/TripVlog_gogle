"""Tests for GPS clustering module."""
import math
import pytest
from src.clustering.gps_cluster import haversine_m, cluster_by_gps, compute_cluster_centroids


# ─── haversine_m ──────────────────────────────────────────────────────────────

class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_m(37.5, 126.9, 37.5, 126.9) == 0.0

    def test_known_distance_seoul_to_incheon(self):
        # Seoul City Hall to Incheon Airport: ~56 km
        dist = haversine_m(37.5665, 126.9780, 37.4602, 126.4407)
        assert 50_000 < dist < 65_000

    def test_symmetry(self):
        d1 = haversine_m(37.5, 126.9, 35.1, 129.0)
        d2 = haversine_m(35.1, 129.0, 37.5, 126.9)
        assert abs(d1 - d2) < 0.01

    def test_equator_one_degree_longitude(self):
        # 1 degree longitude at equator ≈ 111,320 m
        dist = haversine_m(0.0, 0.0, 0.0, 1.0)
        assert 111_000 < dist < 112_000

    def test_north_south_one_degree(self):
        # 1 degree latitude ≈ 111,000 m
        dist = haversine_m(0.0, 0.0, 1.0, 0.0)
        assert 110_000 < dist < 112_000


# ─── cluster_by_gps ───────────────────────────────────────────────────────────

class TestClusterByGps:
    def _make_item(self, file_id: str, lat: float, lng: float) -> dict:
        return {'file_id': file_id, 'gps_lat': lat, 'gps_lng': lng}

    def _make_item_no_gps(self, file_id: str) -> dict:
        return {'file_id': file_id}

    def test_single_item_gets_cluster_zero(self):
        items = [self._make_item('f1', 37.5, 126.9)]
        result = cluster_by_gps(items)
        assert result[0]['cluster_id'] == 0

    def test_two_nearby_items_same_cluster(self):
        # ~100m apart — well within 500m eps
        items = [
            self._make_item('f1', 37.5000, 126.9000),
            self._make_item('f2', 37.5009, 126.9000),
        ]
        result = cluster_by_gps(items)
        assert result[0]['cluster_id'] == result[1]['cluster_id']

    def test_two_far_items_different_clusters(self):
        # Seoul and Busan (~325 km apart)
        items = [
            self._make_item('f1', 37.5665, 126.9780),
            self._make_item('f2', 35.1796, 129.0756),
        ]
        result = cluster_by_gps(items)
        assert result[0]['cluster_id'] != result[1]['cluster_id']

    def test_items_without_gps_get_minus_one(self):
        items = [
            self._make_item('f1', 37.5, 126.9),
            self._make_item_no_gps('f2'),
            self._make_item_no_gps('f3'),
        ]
        result = cluster_by_gps(items)
        assert result[1]['cluster_id'] == -1
        assert result[2]['cluster_id'] == -1
        assert result[0]['cluster_id'] == 0

    def test_returns_new_list_does_not_mutate_input(self):
        original = [self._make_item('f1', 37.5, 126.9)]
        result = cluster_by_gps(original)
        assert 'cluster_id' not in original[0]
        assert 'cluster_id' in result[0]

    def test_empty_list(self):
        result = cluster_by_gps([])
        assert result == []

    def test_all_items_no_gps(self):
        items = [self._make_item_no_gps(f'f{i}') for i in range(5)]
        result = cluster_by_gps(items)
        assert all(r['cluster_id'] == -1 for r in result)

    def test_three_clusters(self):
        # Items in 3 distinct groups (>500m apart from each other)
        items = [
            self._make_item('a1', 37.5665, 126.9780),  # Seoul
            self._make_item('a2', 37.5666, 126.9781),  # Seoul (same cluster)
            self._make_item('b1', 35.1796, 129.0756),  # Busan
            self._make_item('c1', 33.4996, 126.5312),  # Jeju
        ]
        result = cluster_by_gps(items)
        cluster_ids = [r['cluster_id'] for r in result]
        assert cluster_ids[0] == cluster_ids[1]       # Seoul pair same
        assert cluster_ids[0] != cluster_ids[2]       # Seoul != Busan
        assert cluster_ids[2] != cluster_ids[3]       # Busan != Jeju
        assert len(set(cluster_ids)) == 3


# ─── compute_cluster_centroids ────────────────────────────────────────────────

class TestComputeClusterCentroids:
    def test_single_item_centroid(self):
        items = [{'file_id': 'f1', 'gps_lat': 37.5, 'gps_lng': 126.9, 'cluster_id': 0}]
        centroids = compute_cluster_centroids(items)
        assert 0 in centroids
        assert centroids[0]['lat'] == pytest.approx(37.5)
        assert centroids[0]['lng'] == pytest.approx(126.9)

    def test_two_item_centroid(self):
        items = [
            {'file_id': 'f1', 'gps_lat': 37.0, 'gps_lng': 126.0, 'cluster_id': 0},
            {'file_id': 'f2', 'gps_lat': 38.0, 'gps_lng': 128.0, 'cluster_id': 0},
        ]
        centroids = compute_cluster_centroids(items)
        assert centroids[0]['lat'] == pytest.approx(37.5)
        assert centroids[0]['lng'] == pytest.approx(127.0)

    def test_excludes_cluster_minus_one(self):
        items = [
            {'file_id': 'f1', 'gps_lat': 37.5, 'gps_lng': 126.9, 'cluster_id': -1},
        ]
        centroids = compute_cluster_centroids(items)
        assert -1 not in centroids

    def test_multiple_clusters(self):
        items = [
            {'file_id': 'f1', 'gps_lat': 37.0, 'gps_lng': 126.0, 'cluster_id': 0},
            {'file_id': 'f2', 'gps_lat': 35.0, 'gps_lng': 129.0, 'cluster_id': 1},
        ]
        centroids = compute_cluster_centroids(items)
        assert 0 in centroids
        assert 1 in centroids
        assert centroids[0]['lat'] == pytest.approx(37.0)
        assert centroids[1]['lat'] == pytest.approx(35.0)

    def test_empty_list(self):
        assert compute_cluster_centroids([]) == {}
