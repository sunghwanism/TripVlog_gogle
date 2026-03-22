"""
Reverse geocoding: GPS coordinates -> location name.
Uses Google Maps Geocoding API with Nominatim fallback.
Results are cached in-memory to respect Nominatim rate limits.
"""
import os
import time
import requests
from typing import Optional
from functools import lru_cache


def reverse_geocode(lat: float, lng: float) -> str:
    """Return location name for GPS coordinates. Returns 'Unknown Location' on failure."""
    gmaps_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    if gmaps_key:
        result = _gmaps_reverse_geocode(lat, lng, gmaps_key)
        if result:
            return result
    return _nominatim_reverse_geocode(lat, lng) or 'Unknown Location'


@lru_cache(maxsize=1000)
def _gmaps_reverse_geocode(lat: float, lng: float, api_key: str) -> Optional[str]:
    try:
        resp = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'latlng': f'{lat},{lng}', 'key': api_key},
            timeout=5,
        )
        data = resp.json()
        if data.get('status') == 'OK' and data.get('results'):
            return data['results'][0].get('formatted_address', '')
        return None
    except Exception:
        return None


_last_nominatim_call = 0.0


@lru_cache(maxsize=1000)
def _nominatim_reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """Nominatim enforces 1 req/sec — rate limited via module-level timestamp."""
    global _last_nominatim_call
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lng, 'format': 'json'},
            headers={'User-Agent': 'TripVlogAI/1.0'},
            timeout=5,
        )
        _last_nominatim_call = time.time()
        data = resp.json()
        return data.get('display_name', None)
    except Exception:
        return None
