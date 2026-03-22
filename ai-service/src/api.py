"""
AI Service FastAPI application.
Endpoints:
  POST /analyze      - Extract metadata from media files
  POST /storyboard   - Run Gemini analysis + assemble storyboard JSON
  GET  /health       - Health check
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from clustering.gps_cluster import cluster_by_gps, compute_cluster_centroids
from extractor.geocoding import reverse_geocode
from extractor.metadata import extract_metadata
from gemini.analyzer import analyze_media_batch
from gemini.validator import MediaBatch

app = FastAPI(title='TripVlog AI Service', version='1.0.0')

STORYBOARD_SCHEMA_PATH = Path(__file__).parent / 'schemas' / 'storyboard.json'
QUALITY_GATE = 3.0  # Scenes below this score are excluded unless only footage for cluster


class AnalyzeRequest(BaseModel):
    project_id: str
    files: list[dict]  # [{file_path, drive_file_id, mime_type}]


@app.post('/analyze')
async def analyze_files(req: AnalyzeRequest) -> dict:
    """Extract EXIF/XMP/ffprobe metadata and geocode GPS coordinates."""
    results = []
    for f in req.files:
        meta = extract_metadata(f['file_path'], f['mime_type'])

        location_name = 'Unknown Location'
        if meta.get('gps_lat') and meta.get('gps_lng'):
            location_name = reverse_geocode(meta['gps_lat'], meta['gps_lng'])

        results.append({
            'drive_file_id': f['drive_file_id'],
            'location_name': location_name,
            **meta,
        })

    return {'project_id': req.project_id, 'results': results}


@app.post('/storyboard')
async def generate_storyboard(batch: MediaBatch) -> dict:
    """Run Gemini analysis and assemble validated storyboard JSON."""
    # 1. Run Gemini analysis
    scene_analyses = analyze_media_batch(batch)

    if not scene_analyses:
        raise HTTPException(status_code=422, detail='Gemini analysis returned no results')

    # 2. GPS clustering on media items
    items_with_meta = [item.model_dump() for item in batch.media_items]
    clustered_items = cluster_by_gps(items_with_meta)
    centroids = compute_cluster_centroids(clustered_items)

    # 3. Build item -> cluster map
    item_cluster = {
        item['file_id']: item.get('cluster_id', -1)
        for item in clustered_items
    }

    # 4. Count items per cluster for quality gate decisions
    cluster_counts: dict[int, int] = {}
    for cid in item_cluster.values():
        cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

    # 5. Assemble scenes — apply quality gate
    scenes = _assemble_scenes(scene_analyses, batch, item_cluster, cluster_counts, centroids)

    if len(scenes) < 3:
        raise HTTPException(
            status_code=422,
            detail=f'Insufficient scenes after quality gate: {len(scenes)}',
        )

    # 6. Calculate total_duration via Python (never LLM math)
    total_duration = _calculate_total_duration(scenes)

    storyboard = {
        'project_id': batch.project_id,
        'concept': batch.concept_prompt[:500],
        'total_duration_seconds': total_duration,
        'scenes': scenes,
        'metadata': {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'gemini_model': 'gemini-1.5-pro',
            'analysis_version': '1.0.0',
            'total_media_items': len(batch.media_items),
            'failed_items': len(batch.media_items) - len(scene_analyses),
            'location_clusters': len(centroids),
        },
    }

    return storyboard


def _assemble_scenes(
    scene_analyses: list,
    batch: MediaBatch,
    item_cluster: dict[str, int],
    cluster_counts: dict[int, int],
    centroids: dict[int, dict],
) -> list[dict]:
    """Build scene list applying quality gate logic. Returns new list."""
    scenes = []
    for i, analysis in enumerate(scene_analyses):
        file_id = batch.media_items[i].file_id if i < len(batch.media_items) else f'file_{i}'
        cluster_id = item_cluster.get(file_id, -1)

        # Quality gate: exclude score < 3.0 unless only footage for cluster
        if analysis.quality_score < QUALITY_GATE and cluster_counts.get(cluster_id, 0) > 1:
            continue

        centroid = centroids.get(cluster_id, {'lat': 0.0, 'lng': 0.0})
        location_name = 'Unknown Location' if cluster_id == -1 else f'Location {cluster_id}'

        scenes.append({
            'scene_id': f'scene_{len(scenes):03d}',
            'order': len(scenes),
            'source_files': [file_id],
            'scene_type': analysis.scene_type.value,
            'location': {
                **centroid,
                'name': location_name,
            },
            'duration_seconds': analysis.suggested_duration_seconds,
            'transition_type': analysis.transition_type.value,
            'transition_duration_ms': 500,
            'emotion_tags': analysis.emotion_tags,
            'quality_score': analysis.quality_score,
            'caption': {
                'text': analysis.caption_suggestion,
                'style': 'cinematic',
            },
        })
    return scenes


def _calculate_total_duration(scenes: list[dict]) -> float:
    """Calculate total video duration in seconds — Python math, no LLM."""
    scene_total = sum(s['duration_seconds'] for s in scenes)
    transition_total = sum(s['transition_duration_ms'] / 1000 for s in scenes[:-1])
    return round(scene_total + transition_total, 2)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}
