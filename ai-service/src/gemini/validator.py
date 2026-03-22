"""Pydantic models for Gemini response validation."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SceneType(str, Enum):
    ESTABLISHING = "establishing"
    ACTION = "action"
    TRANSITION = "transition"
    CLIMAX = "climax"
    OUTRO = "outro"


class TransitionType(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE = "fade"


class SceneAnalysis(BaseModel):
    scene_id: str
    scene_type: SceneType
    emotion_tags: list[str] = Field(min_length=1, max_length=3)
    quality_score: float = Field(ge=0.0, le=10.0)
    suggested_duration_seconds: float = Field(ge=0.5, le=30.0)
    transition_type: TransitionType
    caption_suggestion: str

    @field_validator('quality_score')
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(v, 1)

    @field_validator('emotion_tags')
    @classmethod
    def validate_emotion_tags(cls, v: list[str]) -> list[str]:
        if len(v) < 1 or len(v) > 3:
            raise ValueError('emotion_tags must have between 1 and 3 items')
        return v


class MediaItem(BaseModel):
    file_id: str
    file_type: str
    duration_seconds: Optional[float] = None
    resolution: Optional[dict] = None
    metadata: Optional[dict] = None


class MediaBatch(BaseModel):
    project_id: str
    concept_prompt: str = Field(min_length=10, max_length=5000)
    media_items: list[MediaItem] = Field(min_length=1)
