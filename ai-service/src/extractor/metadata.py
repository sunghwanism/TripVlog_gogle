"""
Metadata extractor for images and videos.
All functions are pure — return new dicts, never mutate inputs.
"""
import exifread
from pathlib import Path
from typing import Optional


def extract_metadata(file_path: str, mime_type: str) -> dict:
    """Extract metadata — returns new dict, never mutates input."""
    if mime_type.startswith('image/'):
        return {
            **_extract_exif(file_path),
            **_extract_xmp(file_path),
        }
    elif mime_type.startswith('video/'):
        return {
            **_extract_video_metadata(file_path),
            **_extract_xmp_sidecar(file_path),
        }
    return {}


def _extract_exif(file_path: str) -> dict:
    """Extract EXIF fields: GPS lat/lng, capture time, camera info, orientation."""
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

        result = {}

        # GPS
        lat = _parse_gps(tags.get('GPS GPSLatitude'), tags.get('GPS GPSLatitudeRef'))
        lng = _parse_gps(tags.get('GPS GPSLongitude'), tags.get('GPS GPSLongitudeRef'))
        if lat is not None:
            result['gps_lat'] = lat
        if lng is not None:
            result['gps_lng'] = lng

        # Timestamp
        dt_tag = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
        if dt_tag:
            result['captured_at'] = str(dt_tag)

        # Camera
        make = tags.get('Image Make')
        model = tags.get('Image Model')
        if make or model:
            result['camera_info'] = f"{make or ''} {model or ''}".strip()

        # Orientation
        orientation = tags.get('Image Orientation')
        if orientation:
            result['orientation'] = int(str(orientation).split()[0])

        # Resolution
        width = tags.get('EXIF ExifImageWidth') or tags.get('Image ImageWidth')
        height = tags.get('EXIF ExifImageLength') or tags.get('Image ImageLength')
        if width:
            result['width'] = int(str(width))
        if height:
            result['height'] = int(str(height))

        return result
    except Exception as e:
        return {'exif_error': str(e)}


def _parse_gps(coord_tag, ref_tag) -> Optional[float]:
    """Convert EXIF GPS IFDRational to decimal degrees."""
    if not coord_tag or not ref_tag:
        return None
    try:
        values = coord_tag.values
        degrees = float(values[0].num) / float(values[0].den)
        minutes = float(values[1].num) / float(values[1].den)
        seconds = float(values[2].num) / float(values[2].den)
        decimal = degrees + minutes / 60 + seconds / 3600
        ref = str(ref_tag)
        if ref in ('S', 'W'):
            decimal = -decimal
        return round(decimal, 7)
    except Exception:
        return None


def _extract_xmp(file_path: str) -> dict:
    """Extract XMP metadata from image file."""
    try:
        import libxmp
        xmp = libxmp.XMPFiles(file_path=file_path)
        meta = xmp.get_xmp()
        xmp.close_file()
        if meta:
            return {'xmp_raw': str(meta)}
        return {}
    except Exception:
        return {}


def _extract_video_metadata(file_path: str) -> dict:
    """Extract video metadata via ffprobe."""
    try:
        import ffprobe as fp
        probe = fp.FFProbe(file_path)

        result = {}
        fmt = probe.format
        if fmt and hasattr(fmt, 'duration') and fmt.duration:
            result['duration_ms'] = int(float(fmt.duration) * 1000)

        for stream in probe.streams:
            if stream.is_video():
                frame_size = stream.frame_size()
                if frame_size:
                    result['width'] = frame_size[0]
                    result['height'] = frame_size[1]
                codec = stream.codec()
                if codec:
                    result['codec'] = codec
                fps_str = stream.frames_per_second()
                if fps_str:
                    result['fps'] = float(fps_str)
                break

        return {k: v for k, v in result.items() if v is not None}
    except Exception as e:
        return {'ffprobe_error': str(e)}


def _extract_xmp_sidecar(file_path: str) -> dict:
    """Check for .xmp sidecar file next to video."""
    sidecar = Path(file_path).with_suffix('.xmp')
    if sidecar.exists():
        return {'xmp_sidecar_path': str(sidecar)}
    return {}
