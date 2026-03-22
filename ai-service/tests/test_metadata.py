"""Tests for EXIF GPS parsing and video metadata extraction."""
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from extractor.metadata import (
    _extract_exif,
    _extract_video_metadata,
    _extract_xmp_sidecar,
    _parse_gps,
    extract_metadata,
)


# ---------------------------------------------------------------------------
# _parse_gps
# ---------------------------------------------------------------------------

class _IFDRational:
    """Minimal EXIF IFDRational stub."""
    def __init__(self, num: int, den: int):
        self.num = num
        self.den = den


def _make_coord_tag(degrees: int, minutes: int, seconds_num: int, seconds_den: int = 1):
    tag = MagicMock()
    tag.values = [
        _IFDRational(degrees, 1),
        _IFDRational(minutes, 1),
        _IFDRational(seconds_num, seconds_den),
    ]
    return tag


def _make_ref_tag(ref: str):
    tag = MagicMock()
    tag.__str__ = lambda self: ref
    return tag


class TestParseGps:
    def test_north_east_returns_positive_values(self):
        # 34 degrees 41 minutes 37.32 seconds N -> approx 34.6937
        lat_tag = _make_coord_tag(34, 41, 3732, 100)
        lat_ref = _make_ref_tag('N')
        result = _parse_gps(lat_tag, lat_ref)
        assert result is not None
        assert abs(result - 34.6937) < 0.001

    def test_south_hemisphere_returns_negative(self):
        lat_tag = _make_coord_tag(33, 51, 0)
        lat_ref = _make_ref_tag('S')
        result = _parse_gps(lat_tag, lat_ref)
        assert result is not None
        assert result < 0

    def test_west_longitude_returns_negative(self):
        lng_tag = _make_coord_tag(118, 14, 37)
        lng_ref = _make_ref_tag('W')
        result = _parse_gps(lng_tag, lng_ref)
        assert result is not None
        assert result < 0

    def test_missing_coord_tag_returns_none(self):
        assert _parse_gps(None, _make_ref_tag('N')) is None

    def test_missing_ref_tag_returns_none(self):
        lat_tag = _make_coord_tag(34, 41, 37)
        assert _parse_gps(lat_tag, None) is None

    def test_result_rounded_to_7_decimal_places(self):
        lat_tag = _make_coord_tag(35, 40, 0)
        lat_ref = _make_ref_tag('N')
        result = _parse_gps(lat_tag, lat_ref)
        assert result is not None
        # Should not have more than 7 decimal places
        str_result = str(result).split('.')
        if len(str_result) > 1:
            assert len(str_result[1]) <= 7

    def test_zero_coordinates_returns_zero(self):
        lat_tag = _make_coord_tag(0, 0, 0)
        lat_ref = _make_ref_tag('N')
        result = _parse_gps(lat_tag, lat_ref)
        assert result == 0.0

    def test_broken_values_returns_none(self):
        broken_tag = MagicMock()
        broken_tag.values = []  # empty -> IndexError
        result = _parse_gps(broken_tag, _make_ref_tag('N'))
        assert result is None


# ---------------------------------------------------------------------------
# _extract_exif
# ---------------------------------------------------------------------------

class TestExtractExif:
    def _make_tags(self, **kwargs):
        return {k: v for k, v in kwargs.items() if v is not None}

    def test_extracts_gps_coordinates(self, tmp_path):
        lat_tag = _make_coord_tag(34, 41, 3732, 100)
        lat_ref = _make_ref_tag('N')
        lng_tag = _make_coord_tag(135, 30, 835, 100)
        lng_ref = _make_ref_tag('E')

        tags = {
            'GPS GPSLatitude': lat_tag,
            'GPS GPSLatitudeRef': lat_ref,
            'GPS GPSLongitude': lng_tag,
            'GPS GPSLongitudeRef': lng_ref,
        }
        dummy_file = tmp_path / 'test.jpg'
        dummy_file.write_bytes(b'FAKE')

        with patch('extractor.metadata.exifread.process_file', return_value=tags):
            result = _extract_exif(str(dummy_file))

        assert 'gps_lat' in result
        assert 'gps_lng' in result
        assert result['gps_lat'] > 0
        assert result['gps_lng'] > 0

    def test_extracts_capture_time(self, tmp_path):
        dt_mock = MagicMock()
        dt_mock.__str__ = lambda self: '2026:03:15 09:30:00'

        tags = {'EXIF DateTimeOriginal': dt_mock}
        dummy_file = tmp_path / 'test.jpg'
        dummy_file.write_bytes(b'FAKE')

        with patch('extractor.metadata.exifread.process_file', return_value=tags):
            result = _extract_exif(str(dummy_file))

        assert result.get('captured_at') == '2026:03:15 09:30:00'

    def test_extracts_camera_info(self, tmp_path):
        make_mock = MagicMock()
        make_mock.__str__ = lambda self: 'Apple'
        model_mock = MagicMock()
        model_mock.__str__ = lambda self: 'iPhone 16 Pro'

        tags = {'Image Make': make_mock, 'Image Model': model_mock}
        dummy_file = tmp_path / 'test.jpg'
        dummy_file.write_bytes(b'FAKE')

        with patch('extractor.metadata.exifread.process_file', return_value=tags):
            result = _extract_exif(str(dummy_file))

        assert 'camera_info' in result
        assert 'Apple' in result['camera_info']

    def test_returns_exif_error_on_exception(self, tmp_path):
        dummy_file = tmp_path / 'nonexistent.jpg'
        result = _extract_exif(str(dummy_file))
        assert 'exif_error' in result

    def test_returns_empty_dict_when_no_tags(self, tmp_path):
        dummy_file = tmp_path / 'test.jpg'
        dummy_file.write_bytes(b'FAKE')

        with patch('extractor.metadata.exifread.process_file', return_value={}):
            result = _extract_exif(str(dummy_file))

        assert result == {}

    def test_does_not_mutate_input(self, tmp_path):
        dummy_file = tmp_path / 'test.jpg'
        dummy_file.write_bytes(b'FAKE')
        original_path = str(dummy_file)

        with patch('extractor.metadata.exifread.process_file', return_value={}):
            result = _extract_exif(original_path)

        # Original string unchanged
        assert original_path == str(dummy_file)


# ---------------------------------------------------------------------------
# _extract_video_metadata
# ---------------------------------------------------------------------------

class TestExtractVideoMetadata:
    def test_extracts_duration_ms(self, tmp_path):
        mock_format = MagicMock()
        mock_format.duration = '10.5'

        mock_stream = MagicMock()
        mock_stream.is_video.return_value = True
        mock_stream.frame_size.return_value = (1920, 1080)
        mock_stream.codec.return_value = 'h264'
        mock_stream.frames_per_second.return_value = '30.0'

        mock_probe = MagicMock()
        mock_probe.format = mock_format
        mock_probe.streams = [mock_stream]

        with patch('extractor.metadata.fp') as mock_fp:
            mock_fp.FFProbe.return_value = mock_probe
            result = _extract_video_metadata('/fake/video.mp4')

        assert result['duration_ms'] == 10500
        assert result['width'] == 1920
        assert result['height'] == 1080
        assert result['codec'] == 'h264'
        assert result['fps'] == 30.0

    def test_returns_ffprobe_error_on_failure(self):
        with patch('extractor.metadata.fp') as mock_fp:
            mock_fp.FFProbe.side_effect = Exception('file not found')
            result = _extract_video_metadata('/nonexistent/video.mp4')

        assert 'ffprobe_error' in result

    def test_skips_audio_only_streams(self, tmp_path):
        mock_format = MagicMock()
        mock_format.duration = '5.0'

        audio_stream = MagicMock()
        audio_stream.is_video.return_value = False

        mock_probe = MagicMock()
        mock_probe.format = mock_format
        mock_probe.streams = [audio_stream]

        with patch('extractor.metadata.fp') as mock_fp:
            mock_fp.FFProbe.return_value = mock_probe
            result = _extract_video_metadata('/fake/audio.mp4')

        assert 'width' not in result
        assert result['duration_ms'] == 5000


# ---------------------------------------------------------------------------
# _extract_xmp_sidecar
# ---------------------------------------------------------------------------

class TestExtractXmpSidecar:
    def test_returns_sidecar_path_when_exists(self, tmp_path):
        video = tmp_path / 'clip.mp4'
        sidecar = tmp_path / 'clip.xmp'
        video.write_bytes(b'fake')
        sidecar.write_text('<xmpmeta/>')

        result = _extract_xmp_sidecar(str(video))
        assert result == {'xmp_sidecar_path': str(sidecar)}

    def test_returns_empty_dict_when_no_sidecar(self, tmp_path):
        video = tmp_path / 'clip.mp4'
        video.write_bytes(b'fake')

        result = _extract_xmp_sidecar(str(video))
        assert result == {}


# ---------------------------------------------------------------------------
# extract_metadata (integration)
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_routes_image_to_exif(self, tmp_path):
        dummy_file = tmp_path / 'photo.jpg'
        dummy_file.write_bytes(b'FAKE')

        with patch('extractor.metadata.exifread.process_file', return_value={}):
            result = extract_metadata(str(dummy_file), 'image/jpeg')

        assert isinstance(result, dict)

    def test_routes_video_to_ffprobe(self, tmp_path):
        mock_format = MagicMock()
        mock_format.duration = '5.0'
        mock_probe = MagicMock()
        mock_probe.format = mock_format
        mock_probe.streams = []

        with patch('extractor.metadata.fp') as mock_fp:
            mock_fp.FFProbe.return_value = mock_probe
            result = extract_metadata('/fake/video.mp4', 'video/mp4')

        assert isinstance(result, dict)

    def test_unknown_mime_returns_empty(self):
        result = extract_metadata('/fake/file.pdf', 'application/pdf')
        assert result == {}

    def test_returns_new_dict_not_mutated_input(self, tmp_path):
        """Immutability: returns fresh dict each call."""
        dummy_file = tmp_path / 'photo.jpg'
        dummy_file.write_bytes(b'FAKE')

        with patch('extractor.metadata.exifread.process_file', return_value={}):
            result1 = extract_metadata(str(dummy_file), 'image/jpeg')
            result2 = extract_metadata(str(dummy_file), 'image/jpeg')

        assert result1 is not result2
