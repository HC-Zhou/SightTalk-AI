from __future__ import annotations

from PIL import Image

from sighttalk_api.agent.livekit_runtime import encode_jpeg_under_limit


def test_encode_jpeg_under_limit_compresses_large_frame() -> None:
    image = Image.new("RGB", (1280, 720), color=(82, 120, 180))

    data = encode_jpeg_under_limit(image, quality=90, max_bytes=20_000)

    assert len(data) <= 20_000
    assert data.startswith(b"\xff\xd8")
