"""Tests for Pydantic validation models."""
import pytest
from pydantic import ValidationError
from src.gemini.validator import SceneAnalysis, SceneType, TransitionType, MediaBatch, MediaItem


# ─── SceneAnalysis ────────────────────────────────────────────────────────────

class TestSceneAnalysis:
    def _valid(self, **overrides) -> dict:
        base = {
            'scene_id': 'scene_001',
            'scene_type': 'establishing',
            'emotion_tags': ['serene'],
            'quality_score': 7.5,
            'suggested_duration_seconds': 4.0,
            'transition_type': 'dissolve',
            'caption_suggestion': 'Golden hour over the mountains',
        }
        return {**base, **overrides}

    def test_valid_scene_analysis(self):
        sa = SceneAnalysis.model_validate(self._valid())
        assert sa.scene_type == SceneType.ESTABLISHING
        assert sa.transition_type == TransitionType.DISSOLVE
        assert sa.quality_score == 7.5

    def test_quality_score_rounded_to_one_decimal(self):
        sa = SceneAnalysis.model_validate(self._valid(quality_score=7.567))
        assert sa.quality_score == 7.6

    def test_quality_score_zero_is_valid(self):
        sa = SceneAnalysis.model_validate(self._valid(quality_score=0.0))
        assert sa.quality_score == 0.0

    def test_quality_score_ten_is_valid(self):
        sa = SceneAnalysis.model_validate(self._valid(quality_score=10.0))
        assert sa.quality_score == 10.0

    def test_quality_score_above_ten_rejected(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(quality_score=10.1))

    def test_quality_score_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(quality_score=-0.1))

    def test_all_scene_types_accepted(self):
        for scene_type in ['establishing', 'action', 'transition', 'climax', 'outro']:
            sa = SceneAnalysis.model_validate(self._valid(scene_type=scene_type))
            assert sa.scene_type.value == scene_type

    def test_invalid_scene_type_rejected(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(scene_type='unknown'))

    def test_all_transition_types_accepted(self):
        for tt in ['cut', 'dissolve', 'fade']:
            sa = SceneAnalysis.model_validate(self._valid(transition_type=tt))
            assert sa.transition_type.value == tt

    def test_invalid_transition_type_rejected(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(transition_type='wipe'))

    def test_emotion_tags_min_one_required(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(emotion_tags=[]))

    def test_emotion_tags_max_three_allowed(self):
        sa = SceneAnalysis.model_validate(self._valid(emotion_tags=['a', 'b', 'c']))
        assert len(sa.emotion_tags) == 3

    def test_emotion_tags_more_than_three_rejected(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(emotion_tags=['a', 'b', 'c', 'd']))

    def test_duration_below_half_second_rejected(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(suggested_duration_seconds=0.4))

    def test_duration_above_thirty_rejected(self):
        with pytest.raises(ValidationError):
            SceneAnalysis.model_validate(self._valid(suggested_duration_seconds=30.1))

    def test_duration_half_second_accepted(self):
        sa = SceneAnalysis.model_validate(self._valid(suggested_duration_seconds=0.5))
        assert sa.suggested_duration_seconds == 0.5


# ─── MediaItem ────────────────────────────────────────────────────────────────

class TestMediaItem:
    def test_minimal_valid_item(self):
        item = MediaItem.model_validate({'file_id': 'f1', 'file_type': 'video/mp4'})
        assert item.file_id == 'f1'
        assert item.file_type == 'video/mp4'
        assert item.duration_seconds is None
        assert item.metadata is None

    def test_full_item(self):
        item = MediaItem.model_validate({
            'file_id': 'f2',
            'file_type': 'image/jpeg',
            'duration_seconds': 14.5,
            'resolution': {'width': 3840, 'height': 2160},
            'metadata': {'gps': {'lat': 37.5, 'lng': 126.9}},
        })
        assert item.resolution == {'width': 3840, 'height': 2160}

    def test_missing_file_id_rejected(self):
        with pytest.raises(ValidationError):
            MediaItem.model_validate({'file_type': 'video/mp4'})


# ─── MediaBatch ───────────────────────────────────────────────────────────────

class TestMediaBatch:
    def _valid_batch(self) -> dict:
        return {
            'project_id': 'proj_abc123',
            'concept_prompt': 'A cinematic summer road trip through coastal Japan',
            'media_items': [
                {'file_id': 'f1', 'file_type': 'video/mp4'},
            ],
        }

    def test_valid_batch(self):
        batch = MediaBatch.model_validate(self._valid_batch())
        assert batch.project_id == 'proj_abc123'
        assert len(batch.media_items) == 1

    def test_concept_prompt_too_short_rejected(self):
        data = self._valid_batch()
        data['concept_prompt'] = 'short'
        with pytest.raises(ValidationError):
            MediaBatch.model_validate(data)

    def test_concept_prompt_too_long_rejected(self):
        data = self._valid_batch()
        data['concept_prompt'] = 'a' * 5001
        with pytest.raises(ValidationError):
            MediaBatch.model_validate(data)

    def test_empty_media_items_rejected(self):
        data = self._valid_batch()
        data['media_items'] = []
        with pytest.raises(ValidationError):
            MediaBatch.model_validate(data)

    def test_multiple_media_items(self):
        data = self._valid_batch()
        data['media_items'] = [
            {'file_id': f'f{i}', 'file_type': 'image/jpeg'} for i in range(15)
        ]
        batch = MediaBatch.model_validate(data)
        assert len(batch.media_items) == 15
