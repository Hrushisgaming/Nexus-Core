import base64
from unittest import mock

import actions.image_generator as ig


class _P:
    def __init__(self, pid, available=True, result=None):
        self.pid, self.available, self._r = pid, available, result or {}
        self.calls = 0

    def generate(self, prompt, model=None):
        self.calls += 1
        return self._r


def _run(providers, chosen):
    with mock.patch.object(ig, "_selected_settings", return_value={"image_engine": chosen}), \
         mock.patch("core.image_providers.get_image_provider", side_effect=lambda pid, **k: providers.get(pid)):
        return ig._render_with_providers("a cat")


def test_uses_selected_provider_first():
    b64 = base64.b64encode(b"IMG").decode()
    nv = _P("nvidia", result={"image_data": b64})
    po = _P("pollinations", result={"image_data": b64})
    data, used = _run({"nvidia": nv, "pollinations": po}, "nvidia")
    assert used == "nvidia" and data == b"IMG" and po.calls == 0


def test_falls_back_when_selected_fails():
    b64 = base64.b64encode(b"OK").decode()
    nv = _P("nvidia", result={"error": "HTTP 401"})
    po = _P("pollinations", result={"image_data": b64})
    data, used = _run({"nvidia": nv, "pollinations": po}, "nvidia")
    assert used == "pollinations" and data == b"OK"


def test_ssl_bundle_is_configured():
    from core import ssl_certs
    assert ssl_certs.apply().endswith(".pem")
