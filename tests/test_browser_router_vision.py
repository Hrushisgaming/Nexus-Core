from unittest import mock

import actions.browser_router as br


def _shot(tmp_path):
    p = tmp_path / "s.jpg"
    p.write_bytes(b"\xff\xd8fake")
    return {"message": "Captured.", "file_path": str(p), "image_width": 1000, "image_height": 500,
            "viewport_width": 1500, "viewport_height": 750}


def test_live_model_gets_the_image_and_a_short_text(tmp_path, monkeypatch):
    got = []
    monkeypatch.setattr(br, "IMAGE_SINK", lambda b: got.append(b) or True)
    out = br._show_screenshot(_shot(tmp_path))
    assert got == [b"\xff\xd8fake"] and "in front of you" in out and "1.500" in out


def test_text_only_chat_gets_a_vision_description(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "IMAGE_SINK", None)
    with mock.patch.object(br, "_describe_screenshot", return_value="a text box at the bottom"):
        out = br._show_screenshot(_shot(tmp_path))
    assert "a text box at the bottom" in out


def test_dead_live_session_falls_back_to_description(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "IMAGE_SINK", lambda b: False)
    with mock.patch.object(br, "_describe_screenshot", return_value="desc"):
        assert "desc" in br._show_screenshot(_shot(tmp_path))


def test_no_file_means_no_crash():
    assert "Captured" in br._show_screenshot({"message": "Captured."})
