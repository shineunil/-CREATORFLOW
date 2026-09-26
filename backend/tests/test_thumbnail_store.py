"""원본 썸네일 보관(snapshot_original_thumbnail) 테스트. 유튜브·Cloudinary 호출은 가짜로 대신한다."""
import asyncio
import io

from PIL import Image

import thumbnail_store


def _jpeg_bytes(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content


def _fake_client(responses, requested):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            requested.append(url.rsplit("/", 1)[-1])
            return responses.get(url.rsplit("/", 1)[-1], _FakeResponse(404))

    return FakeClient


def test_snapshot_falls_back_to_a_smaller_size_and_resizes_for_youtube(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # uploads/ 를 임시 폴더에 만든다
    requested = []
    # 고화질(maxresdefault)이 없는 오래된 영상
    monkeypatch.setattr(thumbnail_store.httpx, "AsyncClient", _fake_client({"sddefault.jpg": _FakeResponse(200, _jpeg_bytes(640, 480))}, requested))
    published = {}

    async def fake_publish(path, filename):
        with Image.open(path) as img:
            published["size"] = img.size
        return "https://res.cloudinary.com/demo/" + filename

    monkeypatch.setattr(thumbnail_store, "publish_local_image", fake_publish)

    url = asyncio.run(thumbnail_store.snapshot_original_thumbnail("vid123"))

    assert requested == ["maxresdefault.jpg", "sddefault.jpg"]
    assert url.startswith("https://res.cloudinary.com/demo/original_vid123_") and url.endswith(".jpg")
    assert published["size"][0] >= 1280  # 유튜브 최소 규격 이상으로 맞춰 보관


def test_snapshot_returns_none_when_no_thumbnail_can_be_downloaded(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    requested = []
    monkeypatch.setattr(thumbnail_store.httpx, "AsyncClient", _fake_client({}, requested))

    assert asyncio.run(thumbnail_store.snapshot_original_thumbnail("vid123")) is None
    assert requested == ["maxresdefault.jpg", "sddefault.jpg", "hqdefault.jpg"]
