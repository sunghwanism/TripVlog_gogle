"""Tests for GeminiAnalyzer — mocks the Gemini API."""
import json
import pytest
from unittest.mock import patch, MagicMock
from src.gemini.validator import MediaBatch, SceneAnalysis


def _make_scene_json(**overrides) -> dict:
    base = {
        'scene_id': 'scene_001',
        'scene_type': 'establishing',
        'emotion_tags': ['serene'],
        'quality_score': 7.5,
        'suggested_duration_seconds': 4.0,
        'transition_type': 'dissolve',
        'caption_suggestion': 'Golden hour over the bay',
    }
    return {**base, **overrides}


def _make_batch(n: int = 3) -> MediaBatch:
    return MediaBatch.model_validate({
        'project_id': 'proj_test001',
        'concept_prompt': 'A cinematic summer road trip through coastal Japan',
        'media_items': [
            {'file_id': f'f{i}', 'file_type': 'image/jpeg'}
            for i in range(n)
        ],
    })


# ─── analyze_batch ────────────────────────────────────────────────────────────

class TestAnalyzeBatch:
    def _mock_model(self, response_text: str) -> MagicMock:
        model = MagicMock()
        model.generate_content.return_value.text = response_text
        return model

    def test_returns_scene_analyses_on_valid_response(self):
        from src.gemini.analyzer import analyze_batch
        scenes = [_make_scene_json(scene_id=f'scene_{i:03d}') for i in range(3)]
        model = self._mock_model(json.dumps(scenes))
        result = analyze_batch(model, [{}] * 3, 'Road trip', 0)
        assert len(result) == 3
        assert all(isinstance(r, SceneAnalysis) for r in result)

    def test_returns_empty_list_after_three_failures(self):
        from src.gemini.analyzer import analyze_batch
        model = MagicMock()
        model.generate_content.side_effect = Exception('Gemini unavailable')
        result = analyze_batch(model, [{}] * 3, 'Road trip', 0)
        assert result == []

    def test_retries_on_invalid_json(self):
        from src.gemini.analyzer import analyze_batch
        valid_response = json.dumps([_make_scene_json()])
        model = MagicMock()
        # First call: not JSON array; second call: valid
        model.generate_content.side_effect = [
            MagicMock(text='not valid json ['),
            MagicMock(text=valid_response),
        ]
        result = analyze_batch(model, [{}], 'Road trip', 0)
        assert len(result) == 1

    def test_rejects_non_array_response(self):
        from src.gemini.analyzer import analyze_batch
        model = self._mock_model('{"scene_id": "scene_001"}')  # object not array
        result = analyze_batch(model, [{}], 'Road trip', 0)
        assert result == []

    def test_does_not_mutate_input_items(self):
        from src.gemini.analyzer import analyze_batch
        model = self._mock_model(json.dumps([_make_scene_json()]))
        items = [{'file_id': 'f0', 'file_type': 'image/jpeg'}]
        original_keys = set(items[0].keys())
        analyze_batch(model, items, 'Road trip', 0)
        assert set(items[0].keys()) == original_keys


# ─── analyze_media_batch ──────────────────────────────────────────────────────

class TestAnalyzeMediaBatch:
    @patch('src.gemini.analyzer.genai')
    def test_raises_when_api_key_missing(self, mock_genai):
        import os
        from src.gemini.analyzer import analyze_media_batch
        env_backup = os.environ.pop('GEMINI_API_KEY', None)
        try:
            with pytest.raises(RuntimeError, match='GEMINI_API_KEY'):
                analyze_media_batch(_make_batch())
        finally:
            if env_backup:
                os.environ['GEMINI_API_KEY'] = env_backup

    @patch('src.gemini.analyzer._get_client')
    @patch('src.gemini.analyzer.analyze_batch')
    def test_splits_large_batch(self, mock_analyze_batch, mock_get_client):
        from src.gemini.analyzer import analyze_media_batch, BATCH_SIZE
        import os
        os.environ['GEMINI_API_KEY'] = 'test-key'

        n = BATCH_SIZE + 5  # Force 2 batches
        batch = _make_batch(n)
        mock_analyze_batch.return_value = [
            SceneAnalysis.model_validate(_make_scene_json())
        ]

        try:
            result = analyze_media_batch(batch)
            # Should have been called twice (2 batches)
            assert mock_analyze_batch.call_count == 2
        finally:
            del os.environ['GEMINI_API_KEY']

    @patch('src.gemini.analyzer._get_client')
    @patch('src.gemini.analyzer.analyze_batch')
    def test_single_batch_for_small_input(self, mock_analyze_batch, mock_get_client):
        from src.gemini.analyzer import analyze_media_batch
        import os
        os.environ['GEMINI_API_KEY'] = 'test-key'

        scenes = [SceneAnalysis.model_validate(_make_scene_json(scene_id=f'scene_{i:03d}')) for i in range(3)]
        mock_analyze_batch.return_value = scenes
        batch = _make_batch(3)

        try:
            result = analyze_media_batch(batch)
            assert mock_analyze_batch.call_count == 1
            assert len(result) == 3
        finally:
            del os.environ['GEMINI_API_KEY']
