import base64
import io
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

import actions.image_generator as ig
from core import image_refs


def _png(path: Path, size=(64, 48)):
    Image.new("RGBA", size, (200, 10, 10, 255)).save(path, "PNG")
    return path


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch):
    monkeypatch.setattr(image_refs, "cache_dir", lambda: tmp_path / "cache" if (tmp_path / "cache").mkdir(exist_ok=True) is None else tmp_path / "cache")


def test_local_file_is_normalised_to_small_jpeg(tmp_path):
    big = tmp_path / "big.png"
    Image.new("RGB", (4000, 3000), (1, 2, 3)).save(big)
    [ref] = image_refs.resolve_references([str(big)])
    im = Image.open(ref)
    assert im.format == "JPEG" and max(im.size) <= image_refs.MAX_SIDE


def test_non_images_and_missing_files_are_dropped(tmp_path):
    txt = tmp_path / "a.txt"
    txt.write_text("hello")
    assert image_refs.resolve_references([str(txt), str(tmp_path / "nope.png")]) == []


class _Resp:
    def __init__(self, data, ctype="image/png"):
        self._d, self.headers = data, {"Content-Type": ctype}

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self._d


def test_download_rejects_html_and_accepts_images(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "PNG")
    sess = mock.Mock()
    sess.get.return_value = _Resp(buf.getvalue())
    assert image_refs.download_image("https://x.test/a.png", session=sess)
    sess.get.return_value = _Resp(b"<html>", "text/html")
    assert image_refs.download_image("https://x.test/page", session=sess) is None
    assert image_refs.download_image("file:///etc/passwd") is None


def test_topic_search_downloads_first_usable_image(tmp_path):
    ok = _png(tmp_path / "ok.png")
    with mock.patch.object(image_refs, "search_image_urls", return_value=["https://bad", "https://good"]), \
         mock.patch.object(image_refs, "download_image", side_effect=lambda u: ok if u == "https://good" else None):
        assert image_refs.fetch_reference_for_topic("cats") == [ok]


class _P:
    def __init__(self, result, refs=False):
        self.available, self._r, self.calls = True, result, []
        self.supports_references = refs

    def generate(self, prompt, model=None, **kw):
        self.calls.append((prompt, kw))
        return self._r(kw) if callable(self._r) else self._r


def _run(providers, refs, chosen="pollinations"):
    with mock.patch.object(ig, "_selected_settings", return_value={"image_engine": chosen}), \
         mock.patch("core.image_providers.get_image_provider", side_effect=lambda pid, **k: providers.get(pid)), \
         mock.patch.object(ig, "_describe_references", return_value="a red square"):
        return ig._render_with_providers("a cat", None, refs)


def test_reference_goes_to_nvidia_first_even_if_another_engine_is_selected(tmp_path):
    ref = _png(tmp_path / "r.png")
    b64 = base64.b64encode(b"IMG").decode()
    nv = _P({"image_data": b64}, refs=True)
    po = _P({"image_data": b64})
    data, used, note = _run({"nvidia": nv, "pollinations": po}, [ref])
    assert used == "nvidia" and po.calls == [] and "reference_images" in nv.calls[0][1]
    assert nv.calls[0][1]["reference_images"][0].startswith("data:image/jpeg;base64,")
    assert "Used your reference" in note


def test_rejected_reference_is_retried_as_a_description(tmp_path):
    ref = _png(tmp_path / "r.png")
    b64 = base64.b64encode(b"IMG").decode()
    nv = _P(lambda kw: {"image_data": b64} if "reference_images" not in kw else
            {"error": "HTTP 422", "reference_rejected": True}, refs=True)
    data, used, note = _run({"nvidia": nv}, [ref])
    assert used == "nvidia" and len(nv.calls) == 2
    assert "a red square" in nv.calls[1][0] and "described" in note


def test_engine_without_reference_support_gets_a_description(tmp_path):
    ref = _png(tmp_path / "r.png")
    po = _P({"image_data": base64.b64encode(b"X").decode()})
    data, used, note = _run({"pollinations": po}, [ref])
    assert "a red square" in po.calls[0][0] and "described" in note


def test_generate_image_errors_when_reference_is_unreadable(tmp_path):
    out = ig.generate_image({"prompt": "x", "reference_images": [str(tmp_path / "missing.png")]})
    assert out.startswith("Error") and "reference" in out


def test_generate_image_errors_when_web_search_finds_nothing():
    with mock.patch("core.image_refs.fetch_reference_for_topic", return_value=[]):
        out = ig.generate_image({"prompt": "x", "reference_search": "zzz"})
    assert out.startswith("Error") and "web" in out
