from unittest import mock

from core import tts_providers, voice_output, voice_settings


def test_gemini_live_is_first_and_default():
    ids = list(tts_providers._PROVIDER_REGISTRY)
    assert ids[0] == "gemini_live"
    assert ids[1:] == ["elevenlabs", "groq_tts", "fish_audio"]
    assert voice_settings.engine({}) == "gemini_live"


def test_gemini_voice_and_model_from_settings():
    s = {"tts_voices": {"gemini_live": "puck"}, "tts_models": {"gemini_live": "gemini-3.1-flash-live-preview"}}
    assert voice_settings.gemini_voice_name(s) == "Puck"
    assert voice_settings.gemini_live_model(s) == "models/gemini-3.1-flash-live-preview"
    assert voice_settings.gemini_voice_name({}) == "Charon"
    assert voice_settings.gemini_live_model({}) == ""


def test_providers_list_has_labels_models_and_native_flag():
    with mock.patch("core.tts_providers.get_api_key", return_value="k"):
        info = {p["id"]: p for p in tts_providers.get_available_tts_providers()}
    assert info["gemini_live"]["native"] and info["gemini_live"]["available"]
    assert any(v["id"] == "Charon" for v in info["gemini_live"]["voices"])
    for pid in ("elevenlabs", "groq_tts", "fish_audio"):
        assert info[pid]["models"] and info[pid]["label"]


def test_model_is_passed_to_provider_and_used_in_request():
    prov = tts_providers.ElevenLabsTTSProvider(api_key="k", model="eleven_multilingual_v2")
    with mock.patch("requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.content = b"mp3"
        assert prov.synthesize("hi", voice_id="abc") == b"mp3"
    assert post.call_args.kwargs["json"]["model_id"] == "eleven_multilingual_v2"


def test_gemini_engine_never_uses_external_path():
    with mock.patch.object(voice_settings, "load", return_value={"tts_engine": "gemini_live"}):
        assert voice_output.external_voice_ready() is False
        assert voice_output.speak_external("hello") is False


def test_external_failure_returns_false_for_fallback():
    fake = mock.Mock(available=True, native=False, voice_id="v")
    fake.synthesize.return_value = b""
    with mock.patch.object(voice_settings, "load", return_value={"tts_engine": "groq_tts"}), \
         mock.patch.object(voice_output, "build_provider", return_value=fake):
        assert voice_output.speak_external("hello") is False
