"""Tests for FastAPI endpoints — mocks extractor and Gemini analyzer."""
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.api import app
    return TestClient(app)


# ─── GET /health ──────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client: TestClient):
        res = client.get('/health')
        assert res.status_code == 200
        assert res.json()['status'] == 'ok'


# ─── POST /analyze ────────────────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    @patch('src.api.extract_metadata')
    @patch('src.api.reverse_geocode')
    def test_analyze_returns_metadata(self, mock_geocode, mock_extract, client: TestClient):
        mock_extract.return_value = {
            'gps_lat': 37.5665,
            'gps_lng': 126.9780,
            'captured_at': '2026-03-10T08:30:00',
            'width': 4032,
            'height': 3024,
        }
        mock_geocode.return_value = 'Seoul, South Korea'

        res = client.post('/analyze', json={
            'project_id': 'proj_test001',
            'files': [
                {'file_path': '/tmp/photo.jpg', 'drive_file_id': 'gdrive-1', 'mime_type': 'image/jpeg'},
            ],
        })

        assert res.status_code == 200
        body = res.json()
        assert body['project_id'] == 'proj_test001'
        assert len(body['results']) == 1
        assert body['results'][0]['location_name'] == 'Seoul, South Korea'
        assert body['results'][0]['gps_lat'] == 37.5665

    @patch('src.api.extract_metadata')
    @patch('src.api.reverse_geocode')
    def test_analyze_no_gps_gives_unknown_location(self, mock_geocode, mock_extract, client: TestClient):
        mock_extract.return_value = {'width': 1920, 'height': 1080}
        mock_geocode.return_value = 'Unknown Location'

        res = client.post('/analyze', json={
            'project_id': 'proj_test002',
            'files': [
                {'file_path': '/tmp/clip.mp4', 'drive_file_id': 'gdrive-2', 'mime_type': 'video/mp4'},
            ],
        })

        assert res.status_code == 200
        result = res.json()['results'][0]
        assert result['location_name'] == 'Unknown Location'
        # reverse_geocode should NOT have been called (no GPS coords)
        mock_geocode.assert_not_called()

    @patch('src.api.extract_metadata')
    def test_analyze_multiple_files(self, mock_extract, client: TestClient):
        mock_extract.return_value = {}

        res = client.post('/analyze', json={
            'project_id': 'proj_multi',
            'files': [
                {'file_path': f'/tmp/file{i}.jpg', 'drive_file_id': f'gdrive-{i}', 'mime_type': 'image/jpeg'}
                for i in range(5)
            ],
        })

        assert res.status_code == 200
        assert len(res.json()['results']) == 5
        assert mock_extract.call_count == 5


# ─── POST /storyboard ─────────────────────────────────────────────────────────

class TestStoryboardEndpoint:
    def _valid_batch(self, n: int = 5) -> dict:
        return {
            'project_id': 'proj_story001',
            'concept_prompt': 'A cinematic summer road trip through coastal Japan',
            'media_items': [
                {'file_id': f'f{i}', 'file_type': 'image/jpeg'}
                for i in range(n)
            ],
        }

    def _make_scene_analysis(self, scene_id: str = 'scene_001') -> MagicMock:
        from src.gemini.validator import SceneAnalysis
        return SceneAnalysis.model_validate({
            'scene_id': scene_id,
            'scene_type': 'action',
            'emotion_tags': ['adventurous'],
            'quality_score': 8.0,
            'suggested_duration_seconds': 3.5,
            'transition_type': 'cut',
            'caption_suggestion': 'Racing along the coastal highway',
        })

    @patch('src.api.analyze_media_batch')
    @patch('src.api.cluster_by_gps')
    @patch('src.api.compute_cluster_centroids')
    def test_storyboard_returns_valid_structure(
        self, mock_centroids, mock_cluster, mock_analyze, client: TestClient
    ):
        analyses = [self._make_scene_analysis(f'scene_{i:03d}') for i in range(5)]
        mock_analyze.return_value = analyses
        mock_cluster.return_value = [
            {'file_id': f'f{i}', 'cluster_id': 0} for i in range(5)
        ]
        mock_centroids.return_value = {0: {'lat': 37.5, 'lng': 126.9}}

        res = client.post('/storyboard', json=self._valid_batch())
        assert res.status_code == 200
        body = res.json()

        assert body['project_id'] == 'proj_story001'
        assert 'scenes' in body
        assert 'total_duration_seconds' in body
        assert 'metadata' in body
        assert body['metadata']['gemini_model'] == 'gemini-1.5-pro'
        assert isinstance(body['total_duration_seconds'], float)

    @patch('src.api.analyze_media_batch')
    def test_storyboard_422_when_no_analyses(self, mock_analyze, client: TestClient):
        mock_analyze.return_value = []
        res = client.post('/storyboard', json=self._valid_batch())
        assert res.status_code == 422

    @patch('src.api.analyze_media_batch')
    @patch('src.api.cluster_by_gps')
    @patch('src.api.compute_cluster_centroids')
    def test_quality_gate_excludes_low_score_scenes(
        self, mock_centroids, mock_cluster, mock_analyze, client: TestClient
    ):
        """Scenes with quality_score < 3.0 should be excluded when cluster has other footage."""
        from src.gemini.validator import SceneAnalysis
        # 4 good scenes + 1 low quality in same cluster
        good_scenes = [self._make_scene_analysis(f'scene_{i:03d}') for i in range(4)]
        low_quality = SceneAnalysis.model_validate({
            'scene_id': 'scene_004',
            'scene_type': 'action',
            'emotion_tags': ['adventurous'],
            'quality_score': 1.5,  # Below gate
            'suggested_duration_seconds': 2.0,
            'transition_type': 'cut',
            'caption_suggestion': 'Blurry shot',
        })
        mock_analyze.return_value = good_scenes + [low_quality]
        mock_cluster.return_value = [
            {'file_id': f'f{i}', 'cluster_id': 0} for i in range(5)
        ]
        mock_centroids.return_value = {0: {'lat': 37.5, 'lng': 126.9}}

        res = client.post('/storyboard', json=self._valid_batch())
        assert res.status_code == 200
        scenes = res.json()['scenes']
        quality_scores = [s['quality_score'] for s in scenes]
        assert all(score >= 3.0 for score in quality_scores)

    @patch('src.api.analyze_media_batch')
    @patch('src.api.cluster_by_gps')
    @patch('src.api.compute_cluster_centroids')
    def test_total_duration_is_sum_of_scenes_plus_transitions(
        self, mock_centroids, mock_cluster, mock_analyze, client: TestClient
    ):
        analyses = [self._make_scene_analysis(f'scene_{i:03d}') for i in range(3)]
        mock_analyze.return_value = analyses
        mock_cluster.return_value = [
            {'file_id': f'f{i}', 'cluster_id': 0} for i in range(3)
        ]
        mock_centroids.return_value = {0: {'lat': 37.5, 'lng': 126.9}}

        res = client.post('/storyboard', json=self._valid_batch(n=3))
        assert res.status_code == 200
        body = res.json()

        scene_total = sum(s['duration_seconds'] for s in body['scenes'])
        transition_total = sum(
            s['transition_duration_ms'] / 1000
            for s in body['scenes'][:-1]  # No transition after last scene
        )
        expected = round(scene_total + transition_total, 2)
        assert body['total_duration_seconds'] == pytest.approx(expected, abs=0.01)
