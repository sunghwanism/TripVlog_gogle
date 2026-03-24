"""
GeminiAnalyzer: batched visual analysis via Gemini 1.5 Pro.
Batch size: 10-15 items. Exponential backoff on rate limits.
"""
import json
import logging
import os
import time

import google.generativeai as genai

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .validator import MediaBatch, SceneAnalysis

logger = logging.getLogger(__name__)

BATCH_SIZE = 12  # Within 10-15 range


def _get_client() -> genai.GenerativeModel:
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not configured')
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        system_instruction=SYSTEM_PROMPT,
    )


def analyze_batch(
    model: genai.GenerativeModel,
    items: list[dict],
    concept: str,
    batch_idx: int,
    batch_size: int = BATCH_SIZE,
) -> list[SceneAnalysis]:
    """Analyze one batch with retry + exponential backoff."""
    current_items = items
    prompt = build_user_prompt(concept, current_items, batch_idx)

    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()

            # Output anomaly detection: response must be pure JSON array
            if not raw.startswith('['):
                raise ValueError(
                    f'Unexpected response format (attempt {attempt}): {raw[:100]}'
                )

            parsed = json.loads(raw)
            return [SceneAnalysis.model_validate(s) for s in parsed]

        except Exception as e:
            wait = 2 ** attempt
            logger.warning(
                'Gemini batch %d attempt %d failed: %s. Retrying in %ds',
                batch_idx,
                attempt,
                type(e).__name__,
                wait,
            )
            if attempt < 2:
                time.sleep(wait)
                # On timeout, reduce batch size
                if 'timeout' in str(e).lower() and len(current_items) > 5:
                    current_items = current_items[: len(current_items) // 2]
                    prompt = build_user_prompt(concept, current_items, batch_idx)
            else:
                logger.error('Gemini batch %d failed after 3 attempts', batch_idx)
                return []
    return []


def analyze_media_batch(batch: MediaBatch) -> list[SceneAnalysis]:
    """
    Analyze all items in a MediaBatch.
    Splits into sub-batches of BATCH_SIZE.
    Returns combined list of SceneAnalysis objects.
    """
    model = _get_client()
    items = [item.model_dump() for item in batch.media_items]
    results: list[SceneAnalysis] = []

    for i in range(0, len(items), BATCH_SIZE):
        sub_batch = items[i : i + BATCH_SIZE]
        batch_results = analyze_batch(model, sub_batch, batch.concept_prompt, i // BATCH_SIZE)
        results.extend(batch_results)

        # Respect 60 RPM limit — pause between batches
        if i + BATCH_SIZE < len(items):
            time.sleep(1.0)

    return results
