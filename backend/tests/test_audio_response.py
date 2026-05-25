from types import SimpleNamespace

from backend.app.main import _audio_file_response, _parse_range_header


def test_parse_range_header_supports_open_and_suffix_ranges() -> None:
    assert _parse_range_header("bytes=2-5", 10) == (2, 5)
    assert _parse_range_header("bytes=2-", 10) == (2, 9)
    assert _parse_range_header("bytes=-4", 10) == (6, 9)
    assert _parse_range_header("bytes=12-15", 10) is None


def test_audio_file_response_returns_requested_byte_range(tmp_path) -> None:
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"abcdef")
    request = SimpleNamespace(headers={"range": "bytes=2-4"})

    response = _audio_file_response(
        request=request,
        audio_file=audio_file,
        media_type="audio/wav",
        filename="示例.wav",
    )

    assert response.status_code == 206
    assert response.body == b"cde"
    assert response.headers["content-range"] == "bytes 2-4/6"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-disposition"].startswith("inline;")


def test_audio_file_response_returns_full_file_without_range(tmp_path) -> None:
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"abcdef")
    request = SimpleNamespace(headers={})

    response = _audio_file_response(
        request=request,
        audio_file=audio_file,
        media_type="audio/wav",
        filename="sample.wav",
    )

    assert response.status_code == 200
    assert response.body == b"abcdef"
    assert response.headers["content-length"] == "6"
