"""Voice engines offered at first-run setup: providers, playback helpers, merge, CLI step."""
from __future__ import annotations

import io
import json
import sys
import types
import wave
from unittest import mock

import pytest

from core import tts_providers, voice_output, voice_settings


def _wav(frames: int = 100, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * frames)
    return buf.getvalue()


class _Resp:
    def __init__(self, status=200, content=b"", text=""):
        self.status_code, self.content, self.text = status, content, text


# ---------------------------------------------------------------- Groq
def test_groq_uses_orpheus_wav_and_autumn_by_default():
    prov = tts_providers.GroqTTSProvider(api_key="gsk")
    with mock.patch("requests.post", return_value=_Resp(200, _wav())) as post:
        assert prov.synthesize("hello there")[:4] == b"RIFF"
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "canopylabs/orpheus-v1-english"
    assert payload["response_format"] == "wav"
    assert payload["voice"] == "autumn"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer gsk"


@pytest.mark.parametrize("legacy", ["playai-tts", "playai-tts-arabic", "", None])
def test_groq_retired_playai_model_is_mapped_to_orpheus(legacy):
    assert tts_providers.GroqTTSProvider(api_key="k", model=legacy).model == "canopylabs/orpheus-v1-english"


def test_groq_long_text_is_chunked_and_wavs_are_joined():
    prov = tts_providers.GroqTTSProvider(api_key="k")
    text = " ".join(f"This is sentence number {i} of a long reply." for i in range(20))
    with mock.patch("requests.post", return_value=_Resp(200, _wav(100))) as post:
        audio = prov.synthesize(text)
    assert post.call_count > 1
    assert all(len(c.kwargs["json"]["input"]) <= prov.MAX_CHARS for c in post.call_args_list)
    with wave.open(io.BytesIO(audio), "rb") as w:
        assert w.getnframes() == 100 * post.call_count


def test_groq_unknown_saved_voice_falls_back_to_default_voice():
    prov = tts_providers.GroqTTSProvider(api_key="k", voice_id="fortuna")
    responses = [_Resp(400, text='{"error":"voice fortuna not found"}'), _Resp(200, _wav())]
    with mock.patch("requests.post", side_effect=responses) as post:
        assert prov.synthesize("hi")
    assert post.call_args_list[1].kwargs["json"]["voice"] == "autumn"


def test_groq_bad_key_reports_reason_instead_of_silence():
    prov = tts_providers.GroqTTSProvider(api_key="bad")
    with mock.patch("requests.post", return_value=_Resp(401, text="invalid api key")):
        assert prov.synthesize("hi") == b""
    assert "401" in prov.last_error and "key rejected" in prov.last_error


# ---------------------------------------------------------------- ElevenLabs
def test_elevenlabs_voice_ids_match_their_names():
    ids = {v["name"]: v["id"] for v in tts_providers.ElevenLabsTTSProvider(api_key="k").voices}
    assert ids["Rachel"] == "21m00Tcm4TlvDq8ikWAM"
    assert ids["Adam"] == "pNInz6obpgDQGcFmaJgB"
    assert tts_providers.ElevenLabsTTSProvider.DEFAULT_VOICE_ID == ids["Rachel"]


def test_elevenlabs_failure_records_reason():
    prov = tts_providers.ElevenLabsTTSProvider(api_key="k")
    with mock.patch("requests.post", return_value=_Resp(401, text="unauthorized")):
        assert prov.synthesize("hi") == b""
    assert "401" in prov.last_error


# ---------------------------------------------------------------- Edge (free)
def _fake_edge(chunks):
    mod = types.ModuleType("edge_tts")

    class Communicate:
        def __init__(self, text, voice=None):
            mod.used = (text, voice)

        async def stream(self):
            for c in chunks:
                yield c

    mod.Communicate = Communicate
    return mod


def test_edge_needs_no_key_and_concatenates_audio_chunks():
    fake = _fake_edge([{"type": "audio", "data": b"AB"}, {"type": "WordBoundary"}, {"type": "audio", "data": b"CD"}])
    with mock.patch.dict(sys.modules, {"edge_tts": fake}):
        prov = tts_providers.EdgeTTSProvider()
        assert prov.available and prov.needs_key is False
        assert prov.synthesize("hi", voice_id="en-GB-RyanNeural") == b"ABCD"
    assert fake.used == ("hi", "en-GB-RyanNeural")


def test_edge_works_when_called_from_inside_a_running_event_loop():
    import asyncio
    fake = _fake_edge([{"type": "audio", "data": b"X"}])

    async def go():
        return prov.synthesize("hi")

    with mock.patch.dict(sys.modules, {"edge_tts": fake}):
        prov = tts_providers.EdgeTTSProvider()
        assert asyncio.run(go()) == b"X"


def test_edge_reports_missing_package():
    with mock.patch.dict(sys.modules, {"edge_tts": None}):
        prov = tts_providers.EdgeTTSProvider()
    assert not prov.available and "edge-tts" in prov.init_error


def test_provider_listing_includes_edge_and_needs_key_flags():
    with mock.patch("core.tts_providers.get_api_key", return_value=""):
        info = {p["id"]: p for p in tts_providers.get_available_tts_providers()}
    assert info["edge_tts"]["needs_key"] is False
    assert info["elevenlabs"]["needs_key"] is True


# ---------------------------------------------------------------- playback helpers
def test_audio_extension_detects_wav_and_mp3():
    assert voice_output.audio_extension(_wav()) == ".wav"
    assert voice_output.audio_extension(b"ID3\x04rest") == ".mp3"
    assert voice_output.audio_extension(b"\xff\xfb\x90\x00") == ".mp3"


def test_speak_external_plays_wav_with_wav_extension():
    fake = mock.Mock(available=True, native=False, voice_id="autumn")
    fake.synthesize.return_value = _wav()
    played = {}
    with mock.patch.object(voice_settings, "load", return_value={"tts_engine": "groq_tts"}), \
         mock.patch.object(voice_output, "build_provider", return_value=fake), \
         mock.patch.object(voice_output, "_play_file", side_effect=lambda p: played.setdefault("path", p) and True):
        assert voice_output.speak_external("hello") is True
    assert played["path"].endswith(".wav")


def test_preview_voice_explains_failures_and_success():
    prov = mock.Mock(native=False, available=True, voice_id="v", last_error="HTTP 401 (key rejected)")
    prov.synthesize.return_value = b""
    with mock.patch.object(voice_output, "build_provider", return_value=prov):
        ok, msg = voice_output.preview_voice("elevenlabs", api_key="k")
        assert (ok, msg) == (False, "HTTP 401 (key rejected)")

    prov.synthesize.return_value = b"ID3audio"
    with mock.patch.object(voice_output, "build_provider", return_value=prov), \
         mock.patch.object(voice_output, "_play_audio", return_value=True):
        assert voice_output.preview_voice("elevenlabs", api_key="k") == (True, "Voice works.")
    with mock.patch.object(voice_output, "build_provider", return_value=prov), \
         mock.patch.object(voice_output, "_play_audio", return_value=False):
        ok, msg = voice_output.preview_voice("elevenlabs", api_key="k")
        assert ok and "no audio player" in msg

    prov.available, prov.init_error = False, "ELEVENLABS_API_KEY not set"
    with mock.patch.object(voice_output, "build_provider", return_value=prov):
        assert voice_output.preview_voice("elevenlabs") == (False, "ELEVENLABS_API_KEY not set")


def test_build_provider_passes_explicit_key_and_voice_over_saved_settings():
    with mock.patch.object(voice_settings, "load", return_value={"tts_voices": {"groq_tts": "troy"}}):
        prov = voice_output.build_provider("groq_tts", api_key="gsk_x", voice="diana")
    assert prov.api_key == "gsk_x" and prov.voice_id == "diana"


# ---------------------------------------------------------------- settings merge
def test_merge_setup_result_merges_engine_dicts_and_never_blanks_keys():
    existing = {"elevenlabs_api_key": "old", "tts_voices": {"gemini_live": "Puck"}, "x": 1}
    setup = {"elevenlabs_api_key": "", "groq_api_key": " gsk ", "tts_engine": "groq_tts",
             "tts_voices": {"groq_tts": "autumn"}}
    merged = voice_settings.merge_setup_result(existing, setup)
    assert merged["elevenlabs_api_key"] == "old"
    assert merged["groq_api_key"] == "gsk" and merged["tts_engine"] == "groq_tts"
    assert merged["tts_voices"] == {"gemini_live": "Puck", "groq_tts": "autumn"}
    assert merged["x"] == 1 and existing["tts_voices"] == {"gemini_live": "Puck"}  # input untouched


# ---------------------------------------------------------------- CLI setup
def _answers(monkeypatch, nexus_setup, yes, texts):
    it = iter(texts)
    monkeypatch.setattr(nexus_setup, "_ask_yes_no", lambda *a, **k: yes)
    monkeypatch.setattr(nexus_setup, "_prompt", lambda prompt, default="": next(it, "") or default)


def test_cli_voice_step_is_skipped_by_default(monkeypatch):
    import setup as nexus_setup
    _answers(monkeypatch, nexus_setup, False, [])
    assert nexus_setup.setup_voice({}) == ({}, {})


def test_cli_voice_step_elevenlabs_asks_for_key(monkeypatch):
    import setup as nexus_setup
    _answers(monkeypatch, nexus_setup, True, ["elevenlabs", "xi-key", ""])
    keys, settings = nexus_setup.setup_voice({})
    assert keys == {"elevenlabs_api_key": "xi-key"}
    assert settings == {"tts_engine": "elevenlabs", "tts_voices": {"elevenlabs": "21m00Tcm4TlvDq8ikWAM"}}


def test_cli_voice_step_reuses_groq_key_and_edge_needs_none(monkeypatch):
    import setup as nexus_setup
    _answers(monkeypatch, nexus_setup, True, ["2", ""])
    keys, settings = nexus_setup.setup_voice({"groq_api_key": "gsk_chat"})
    assert keys == {"groq_api_key": "gsk_chat"} and settings["tts_engine"] == "groq_tts"
    assert settings["tts_voices"] == {"groq_tts": "autumn"}

    _answers(monkeypatch, nexus_setup, True, ["4", ""])
    keys, settings = nexus_setup.setup_voice({})
    assert keys == {} and settings["tts_engine"] == "edge_tts"


def test_cli_voice_step_without_key_or_choice_changes_nothing(monkeypatch):
    import setup as nexus_setup
    _answers(monkeypatch, nexus_setup, True, ["fish", ""])         # picked Fish but gave no key
    assert nexus_setup.setup_voice({}) == ({}, {})
    _answers(monkeypatch, nexus_setup, True, [""])                  # no engine picked
    assert nexus_setup.setup_voice({}) == ({}, {})


def test_write_config_saves_voice_engine_without_losing_other_settings(monkeypatch, tmp_path):
    import setup as nexus_setup
    from core import user_paths
    monkeypatch.setattr(user_paths, "get_user_data_dir", lambda: tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "app_settings.json").write_text(json.dumps({"tts_voices": {"gemini_live": "Puck"}, "app_theme": "#123456"}))
    nexus_setup.write_config(
        {"nvidia_api_key": "nvapi", "default_ai_provider": "NVIDIA", "elevenlabs_api_key": "xi"},
        {"tts_engine": "elevenlabs", "tts_voices": {"elevenlabs": "abc"}},
    )
    settings = json.loads((cfg / "app_settings.json").read_text())
    assert settings["default_ai_provider"] == "NVIDIA" and settings["app_theme"] == "#123456"
    assert settings["tts_engine"] == "elevenlabs"
    assert settings["tts_voices"] == {"gemini_live": "Puck", "elevenlabs": "abc"}
    assert json.loads((cfg / "api_keys.json").read_text())["elevenlabs_api_key"] == "xi"
