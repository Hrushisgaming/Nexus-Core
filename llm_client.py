"""
llm_client.py - provider-agnostic AI client for Nexus Core.

Every cloud provider (Gemini, NVIDIA NIM, Groq, OpenRouter, Custom
OpenAI-compatible) and the local Ollama/LM Studio backend are reachable
through one dispatcher, so the primary provider chosen in Settings (or in
first-run setup) is honoured everywhere that goes through this module.

Failure handling:
  * the primary provider is tried first;
  * if "auto_provider_switch" is on (default) every other provider that has a
    key is tried next, then the local model;
  * if everything fails a RuntimeError is raised that lists *why* each provider
    failed (bad key, unknown model, rate limit, timeout...) instead of the old
    behaviour of silently returning an empty string.
"""
from core.user_paths import get_user_data_dir
from core.api_keys import get_api_key
import json
import logging
import re
import time
import requests
from pathlib import Path
from typing import Optional

logger = logging.getLogger("llm_client")


def _get_base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR = _get_base_dir()
SETTINGS_PATH = get_user_data_dir() / "config" / "app_settings.json"

# --------------------------------------------------------------------------
# Provider constants
# --------------------------------------------------------------------------
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# First entry is the default; the rest are tried automatically when a model id
# is rejected as unknown/unavailable for the account. Override the first one
# with "nvidia_model" / "nvidia_vision_model" in app_settings.json.
NVIDIA_CHAT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
]
NVIDIA_VISION_MODELS = [
    "meta/llama-3.2-90b-vision-instruct",
    "meta/llama-3.2-11b-vision-instruct",
    "microsoft/phi-3.5-vision-instruct",
]
GROQ_CHAT_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
GROQ_VISION_MODELS = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"

DEFAULT_SYSTEM = "You are a helpful assistant."
REQUEST_TIMEOUT = 90

_PROVIDER_ALIASES = {
    "gemini": "Gemini",
    "google gemini": "Gemini",
    "google": "Gemini",
    "openrouter": "OpenRouter",
    "open router": "OpenRouter",
    "nvidia": "NVIDIA",
    "nvidia nim": "NVIDIA",
    "nim": "NVIDIA",
    "groq": "Groq",
    "custom": "Custom",
    "local": "Local",
    "ollama": "Local",
}

# Order used when falling back from a failed primary provider.
_FALLBACK_ORDER = ["NVIDIA", "Groq", "OpenRouter", "Gemini", "Custom"]


def normalize_provider(name: Optional[str]) -> str:
    """Map any spelling used in settings/UI to a canonical provider name."""
    raw = (name or "").strip().lower()
    return _PROVIDER_ALIASES.get(raw, "OpenRouter" if not raw else (name or "").strip())


class _AuthError(Exception):
    """The provider rejected the API key - trying other models will not help."""


class _ModelUnavailable(Exception):
    """The model id is unknown / not enabled for this key - try the next model."""


def _strip_reasoning(text: str) -> str:
    """Remove <think>...</think> blocks emitted by reasoning models."""
    if not text:
        return text
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _clean_json_text(raw: str) -> str:
    clean = (raw or "").strip()
    if clean.startswith("```"):
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.lower().startswith("json"):
            clean = clean[4:]
    return clean.strip().rstrip("`").strip()


class UnifiedAIClient:
    def __init__(self):
        self._provider = "OpenRouter"
        self._settings: dict = {}
        self._local_url = "http://localhost:11434/v1"
        self._local_model = "llama3.2"
        # provider -> last human-readable failure, for logs / error messages
        self.last_errors: dict[str, str] = {}
        # model ids a provider told us it does not have (per process)
        self._bad_models: set[tuple[str, str]] = set()
        self.reload_settings()

    # ======================================================================
    # Settings & keys
    # ======================================================================
    def reload_settings(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except Exception as e:
            logger.error(f"[LLM Client] Failed to load settings: {e}")
            data = {}
        self._settings = data if isinstance(data, dict) else {}
        self._provider = normalize_provider(self._settings.get("default_ai_provider", "OpenRouter"))
        self._local_url = str(self._settings.get("local_ai_url", "http://localhost:11434/v1")).rstrip("/")
        self._local_model = self._settings.get("local_ai_model", "llama3.2")

    def _setting(self, name: str, default: str = "") -> str:
        return str(self._settings.get(name) or default).strip()

    def _load_api_key_from_file(self, key_name: str) -> str:
        """Key from api_keys.json or app_settings.json (what the Settings UI writes)."""
        try:
            return get_api_key(key_name)
        except Exception as e:
            logger.error(f"[LLM Client] Failed reading {key_name}: {e}")
            return ""

    def _load_nvidia_key(self) -> str:
        return self._clean_key(get_api_key("nvidia_api_key", "NVIDIA_API_KEY"))

    def _load_groq_key(self) -> str:
        return self._clean_key(get_api_key("groq_api_key", "GROQ_API_KEY"))

    @staticmethod
    def _clean_key(key: str) -> str:
        key = (key or "").strip().strip('"').strip("'")
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        return key

    def _get_custom_provider_settings(self) -> dict:
        return {
            "base_url": self._setting("custom_ai_base_url").rstrip("/"),
            "api_key": self._clean_key(get_api_key("custom_ai_api_key", "CUSTOM_AI_API_KEY")),
            "model": self._setting("custom_ai_model", "custom-model"),
        }

    def _get_gemini_key(self) -> str:
        return self._clean_key(get_api_key("gemini_api_key", "GEMINI_API_KEY"))

    def _openrouter_key(self) -> str:
        return self._clean_key(get_api_key("openrouter_api_key", "OPENROUTER_API_KEY"))

    # ======================================================================
    # Provider availability / chain
    # ======================================================================
    def has_key(self, provider: str) -> bool:
        provider = normalize_provider(provider)
        if provider == "Gemini":
            return bool(self._get_gemini_key())
        if provider == "NVIDIA":
            return bool(self._load_nvidia_key())
        if provider == "Groq":
            return bool(self._load_groq_key())
        if provider == "OpenRouter":
            return bool(self._openrouter_key())
        if provider == "Custom":
            s = self._get_custom_provider_settings()
            return bool(s["base_url"] and s["api_key"])
        if provider == "Local":
            return True
        return False

    def active_provider(self) -> str:
        """The provider the user picked as primary (re-read from settings)."""
        self.reload_settings()
        return self._provider

    def provider_chain(self) -> list[str]:
        """Providers to try, in order, for the current settings."""
        self.reload_settings()
        if bool(self._settings.get("offline_mode_enabled", False)) or self._provider == "Local":
            return ["Local"]
        chain = [self._provider]
        if bool(self._settings.get("auto_provider_switch", True)):
            for p in _FALLBACK_ORDER:
                if p not in chain and self.has_key(p):
                    chain.append(p)
            chain.append("Local")
        return chain

    # ======================================================================
    # Low-level transports
    # ======================================================================
    def _local_chat_completion(self, messages: list[dict], temperature: float = 0.7, response_format: Optional[dict] = None) -> Optional[str]:
        payload = {"model": self._local_model, "messages": messages, "temperature": temperature}
        if response_format:
            payload["response_format"] = response_format
        try:
            resp = requests.post(
                f"{self._local_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if resp.status_code == 200:
                content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                return _strip_reasoning(content) if content else None
            self.last_errors["Local"] = f"HTTP {resp.status_code}: {resp.text[:160]}"
            logger.error(f"[LLM Client] Local AI Error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            self.last_errors["Local"] = f"not reachable at {self._local_url} ({e.__class__.__name__})"
            logger.error(f"[LLM Client] Local AI Request Failed: {e}")
        return None

    @staticmethod
    def _extract_content(data: dict) -> str:
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):  # some servers return content parts
            content = "".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        return _strip_reasoning(content or "")

    def _post_openai_compatible(
        self,
        label: str,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> Optional[str]:
        """One request to an OpenAI-compatible /chat/completions endpoint.

        Returns text, or None for a transient failure. Raises _AuthError /
        _ModelUnavailable for failures that call for a different strategy.
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode and label not in ("NVIDIA",):
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{base_url.rstrip('/')}/chat/completions"

        for attempt in (1, 2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                self.last_errors[label] = f"timed out after {REQUEST_TIMEOUT}s ({model})"
                logger.warning(f"[LLM Client] {label} timeout ({model}) attempt {attempt}")
                continue
            except requests.exceptions.RequestException as e:
                self.last_errors[label] = f"network error: {e.__class__.__name__}: {e}"
                logger.error(f"[LLM Client] {label} network error: {e}")
                return None

            status = resp.status_code
            if status == 200:
                try:
                    text = self._extract_content(resp.json())
                except ValueError:
                    self.last_errors[label] = "invalid JSON in response"
                    return None
                if text:
                    return text
                self.last_errors[label] = (
                    f"{model} returned an empty reply (a reasoning model may have used up max_tokens)"
                )
                return None

            body = (resp.text or "")[:240].replace("\n", " ")
            if status in (401, 403):
                self.last_errors[label] = f"HTTP {status} - API key rejected or not allowed for {model}. {body}"
                raise _AuthError(self.last_errors[label])
            if status == 404 or (status in (400, 422) and re.search(r"model|not found|does not exist|unknown", body, re.I)):
                self.last_errors[label] = f"model '{model}' unavailable (HTTP {status}). {body}"
                raise _ModelUnavailable(self.last_errors[label])
            if status == 429:
                self.last_errors[label] = f"rate limited (HTTP 429) on {model}"
                logger.warning(f"[LLM Client] {label} rate limited on {model}")
                return None
            if status >= 500 and attempt == 1:
                time.sleep(1.5)
                continue
            self.last_errors[label] = f"HTTP {status}: {body}"
            logger.error(f"[LLM Client] {label} error {status}: {body}")
            return None
        return None

    def _try_models(
        self,
        label: str,
        base_url: str,
        api_key: str,
        models: list[str],
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> Optional[str]:
        if not api_key or not base_url:
            self.last_errors[label] = "no API key configured"
            return None
        seen = set()
        for model in models:
            if not model or model in seen or (label, model) in self._bad_models:
                continue
            seen.add(model)
            try:
                result = self._post_openai_compatible(
                    label, base_url, api_key, model, messages, temperature, max_tokens, json_mode
                )
            except _AuthError:
                return None
            except _ModelUnavailable:
                self._bad_models.add((label, model))
                logger.warning(f"[LLM Client] {label}: model {model} unavailable, trying next")
                continue
            if result:
                self.last_errors.pop(label, None)
                return result
        return None

    # -- legacy helpers kept for compatibility -----------------------------
    def _openai_compatible_chat_completion(
        self, messages, base_url, api_key, model, temperature=0.7, max_tokens=4096
    ) -> Optional[str]:
        return self._try_models("Custom", base_url, api_key, [model], messages, temperature, max_tokens)

    def _openai_compatible_vision(
        self, prompt, image_b64, base_url, api_key, model, mime="image/png",
        system="Analyze the image.", max_tokens=1024,
    ) -> Optional[str]:
        return self._try_models(
            "Custom", base_url, api_key, [model],
            self._vision_messages(prompt, image_b64, mime, system), 0.2, max_tokens,
        )

    @staticmethod
    def _vision_messages(prompt: str, image_b64: str, mime: str, system: str) -> list[dict]:
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                ],
            },
        ]

    # ======================================================================
    # Provider-specific text completion  (messages -> text or None)
    # ======================================================================
    def _nvidia_models(self, override: Optional[str], vision: bool = False) -> list[str]:
        if vision:
            chosen = override or self._setting("nvidia_vision_model")
            return [chosen] + NVIDIA_VISION_MODELS if chosen else list(NVIDIA_VISION_MODELS)
        chosen = override or self._setting("nvidia_model")
        return [chosen] + NVIDIA_CHAT_MODELS if chosen else list(NVIDIA_CHAT_MODELS)

    def _nvidia_chat_completion(self, messages, temperature=0.7, model=None, max_tokens=4096, json_mode=False):
        return self._try_models(
            "NVIDIA", NVIDIA_BASE_URL, self._load_nvidia_key(),
            self._nvidia_models(model), messages, temperature, max_tokens, json_mode,
        )

    def _nvidia_vision(self, prompt, image_b64, mime="image/png", system="Analyze the image.", model=None, max_tokens=1024):
        return self._try_models(
            "NVIDIA", NVIDIA_BASE_URL, self._load_nvidia_key(),
            self._nvidia_models(model, vision=True),
            self._vision_messages(prompt, image_b64, mime, system), 0.2, max_tokens,
        )

    def _groq_models(self, override: Optional[str], vision: bool = False) -> list[str]:
        base = GROQ_VISION_MODELS if vision else GROQ_CHAT_MODELS
        chosen = override or self._setting("groq_vision_model" if vision else "groq_model")
        return [chosen] + base if chosen else list(base)

    def _groq_chat_completion(self, messages, temperature=0.7, model=None, max_tokens=4096, json_mode=False):
        return self._try_models(
            "Groq", GROQ_BASE_URL, self._load_groq_key(),
            self._groq_models(model), messages, temperature, max_tokens, json_mode,
        )

    def _groq_vision(self, prompt, image_b64, mime="image/png", system="Analyze the image.", model=None, max_tokens=1024):
        return self._try_models(
            "Groq", GROQ_BASE_URL, self._load_groq_key(),
            self._groq_models(model, vision=True),
            self._vision_messages(prompt, image_b64, mime, system), 0.2, max_tokens,
        )

    def _custom_chat_completion(self, messages, temperature=0.7, model=None, max_tokens=4096, json_mode=False):
        s = self._get_custom_provider_settings()
        if not s["base_url"] or not s["api_key"]:
            self.last_errors["Custom"] = "base URL or API key not set"
            return None
        return self._try_models(
            "Custom", s["base_url"], s["api_key"], [model or s["model"]],
            messages, temperature, max_tokens, json_mode,
        )

    def _custom_vision(self, prompt, image_b64, mime="image/png", system="Analyze the image.", model=None, max_tokens=1024):
        s = self._get_custom_provider_settings()
        if not s["base_url"] or not s["api_key"]:
            self.last_errors["Custom"] = "base URL or API key not set"
            return None
        return self._try_models(
            "Custom", s["base_url"], s["api_key"], [model or s["model"]],
            self._vision_messages(prompt, image_b64, mime, system), 0.2, max_tokens,
        )

    def _get_gemini_client(self):
        key = self._get_gemini_key()
        if not key:
            return None
        try:
            from google import genai
            return genai.Client(api_key=key, http_options={"api_version": "v1beta"})
        except Exception as e:
            self.last_errors["Gemini"] = f"client init failed: {e}"
            logger.error(f"[LLM Client] Failed to init Gemini client: {e}")
            return None

    def _gemini_model(self) -> str:
        return self._setting("gemini_model", GEMINI_DEFAULT_MODEL)

    def _gemini_chat_completion(self, messages: list[dict], temperature: float = 0.7, json_mode: bool = False,
                                model: Optional[str] = None, **_ignored) -> Optional[str]:
        client = self._get_gemini_client()
        if not client:
            self.last_errors.setdefault("Gemini", "no API key configured")
            return None
        try:
            from google.genai import types
            sys_parts = [str(m["content"]) for m in messages if m["role"] == "system"]
            system_instruction = "\n".join(sys_parts) if sys_parts else None

            contents = []
            for m in messages:
                if m["role"] == "system":
                    continue
                role = "user" if m["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=str(m["content"]))]))

            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction,
                response_mime_type="application/json" if json_mode else None,
            )
            resp = client.models.generate_content(model=model or self._gemini_model(), contents=contents, config=config)
            if resp and resp.text:
                self.last_errors.pop("Gemini", None)
                return resp.text.strip()
            self.last_errors["Gemini"] = "empty reply"
        except Exception as e:
            self.last_errors["Gemini"] = str(e)[:240]
            logger.error(f"[LLM Client] Gemini request failed: {e}")
        return None

    def _openrouter_complete(self, messages, temperature, max_tokens, model, json_mode=False) -> Optional[str]:
        from or_client import client as or_client
        try:
            result = or_client.multi_turn(messages, model, max_tokens, temperature)
            self.last_errors.pop("OpenRouter", None)
            return result
        except Exception as e:
            self.last_errors["OpenRouter"] = str(e)[:240]
            return None

    # ======================================================================
    # Dispatcher
    # ======================================================================
    def _complete_with(
        self, provider: str, messages: list[dict], temperature: float,
        max_tokens: int, model: Optional[str], json_mode: bool,
    ) -> Optional[str]:
        if provider == "Gemini":
            return self._gemini_chat_completion(messages, temperature, json_mode)
        if provider == "NVIDIA":
            return self._nvidia_chat_completion(messages, temperature, model, max_tokens, json_mode)
        if provider == "Groq":
            return self._groq_chat_completion(messages, temperature, model, max_tokens, json_mode)
        if provider == "Custom":
            return self._custom_chat_completion(messages, temperature, model, max_tokens, json_mode)
        if provider == "Local":
            return self._local_chat_completion(
                messages, temperature, {"type": "json_object"} if json_mode else None
            )
        return self._openrouter_complete(messages, temperature, max_tokens, model, json_mode)

    def _explain_failures(self, tried: list[str]) -> str:
        parts = []
        for p in tried:
            if not self.has_key(p) and p != "Local":
                parts.append(f"{p}: no API key configured")
            else:
                parts.append(f"{p}: {self.last_errors.get(p, 'failed')}")
        return "; ".join(parts)

    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        json_mode: bool = False,
        skip: tuple = (),
    ) -> str:
        """Run a chat completion on the primary provider, falling back as configured.

        `skip` lists providers that already failed for this request and should
        not be retried (e.g. Gemini just failed in a code path of its own).
        """
        skip_set = {normalize_provider(s) for s in skip}
        chain = [p for p in self.provider_chain() if p not in skip_set] or ["Local"]
        tried: list[str] = []
        for provider in chain:
            if provider != "Local" and not self.has_key(provider):
                tried.append(provider)
                continue
            tried.append(provider)
            # An explicit model id only makes sense for the primary provider.
            use_model = model if provider == chain[0] else None
            result = self._complete_with(provider, messages, temperature, max_tokens, use_model, json_mode)
            if result:
                if provider != chain[0]:
                    logger.warning(f"[LLM Client] {chain[0]} failed; answered by {provider}")
                return result
        raise RuntimeError("All AI providers failed - " + self._explain_failures(tried))

    # ======================================================================
    # Public API
    # ======================================================================
    def chat(self, prompt: str, system: str = DEFAULT_SYSTEM, history: Optional[list[dict]] = None,
             model: Optional[str] = None, max_tokens: int = 4096, temperature: float = 0.7,
             skip: tuple = ()) -> str:
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        return self.complete(messages, temperature, max_tokens, model, skip=skip)

    def ask(self, prompt: str, system: str = DEFAULT_SYSTEM, gemini_model: Optional[str] = None,
            temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """One-shot text generation that honours the user's primary provider.

        For modules that historically called Gemini directly: when Gemini is the
        primary provider the given `gemini_model` is used first; when any other
        provider is primary (NVIDIA, Groq, ...) that provider answers. Failures
        fall through the normal provider chain.
        """
        self.reload_settings()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        if (
            self._provider == "Gemini"
            and not bool(self._settings.get("offline_mode_enabled", False))
            and self.has_key("Gemini")
        ):
            result = self._gemini_chat_completion(messages, temperature, model=gemini_model)
            if result:
                return result
            return self.complete(messages, temperature, max_tokens, skip=("Gemini",))
        return self.complete(messages, temperature, max_tokens)

    def multi_turn(self, messages: list[dict], model: Optional[str] = None,
                   max_tokens: int = 4096, temperature: float = 0.7) -> str:
        return self.complete(messages, temperature, max_tokens, model)

    def chat_json(self, prompt: str, system: str = "Return ONLY valid JSON.",
                  model: Optional[str] = None, max_tokens: int = 4096) -> dict:
        messages = [
            {"role": "system", "content": system + " Output valid JSON only, without any markdown formatting."},
            {"role": "user", "content": prompt},
        ]
        raw = self.complete(messages, 0.2, max_tokens, model, json_mode=True)
        clean = _clean_json_text(raw)
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            # Models sometimes wrap JSON in prose; pull out the outermost object/array.
            m = re.search(r"(\{.*\}|\[.*\])", clean, flags=re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Model returned unparseable JSON: {e}\nRaw output: {raw[:200]}")

    def vision(self, prompt: str, image_b64: str, mime: str = "image/png",
               system: str = "Analyze the image.", model: Optional[str] = None,
               max_tokens: int = 1024) -> str:
        chain = self.provider_chain()
        tried: list[str] = []
        for provider in chain:
            if provider not in ("Local",) and not self.has_key(provider):
                tried.append(provider)
                continue
            tried.append(provider)
            use_model = model if provider == chain[0] else None
            result = None
            if provider == "NVIDIA":
                result = self._nvidia_vision(prompt, image_b64, mime, system, use_model, max_tokens)
            elif provider == "Groq":
                result = self._groq_vision(prompt, image_b64, mime, system, use_model, max_tokens)
            elif provider == "Custom":
                result = self._custom_vision(prompt, image_b64, mime, system, use_model, max_tokens)
            elif provider == "Gemini":
                result = self._gemini_vision(prompt, image_b64, mime, system, max_tokens)
            elif provider == "Local":
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                        {"type": "text", "text": prompt},
                    ]},
                ]
                result = self._local_chat_completion(messages, temperature=0.2)
            else:  # OpenRouter
                from or_client import client as or_client
                try:
                    result = or_client.vision(prompt, image_b64, mime, system, use_model, max_tokens)
                except Exception as e:
                    self.last_errors["OpenRouter"] = str(e)[:240]
            if result:
                return result
        raise RuntimeError("Vision request failed on all providers - " + self._explain_failures(tried))

    def _gemini_vision(self, prompt, image_b64, mime, system, max_tokens) -> Optional[str]:
        client = self._get_gemini_client()
        if not client:
            return None
        try:
            import base64
            from google.genai import types
            resp = client.models.generate_content(
                model=self._gemini_model(),
                contents=[types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type=mime), prompt],
                config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens),
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            self.last_errors["Gemini"] = str(e)[:240]
            logger.error(f"[LLM Client] Gemini vision request failed: {e}")
        return None

    def vision_from_file(self, prompt: str, image_path: str, system: str = "Analyze the image.",
                         model: Optional[str] = None, max_tokens: int = 1024) -> str:
        import base64
        path = Path(image_path)
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".webp": "image/webp", ".gif": "image/gif"}
        mime = mime_map.get(path.suffix.lower(), "image/png")
        with open(path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
        return self.vision(prompt, image_b64, mime, system, model, max_tokens)

    # ======================================================================
    # Connectivity test (used by Settings -> "Test")
    # ======================================================================
    def test_provider(self, provider: str) -> tuple[bool, str]:
        """Send a tiny request to one provider and report success/failure."""
        provider = normalize_provider(provider)
        self.reload_settings()
        if provider != "Local" and not self.has_key(provider):
            return False, f"{provider}: no API key configured"
        self.last_errors.pop(provider, None)
        msgs = [{"role": "user", "content": "Reply with the single word: ok"}]
        result = self._complete_with(provider, msgs, 0.0, 16 if provider != "NVIDIA" else 256, None, False)
        if result:
            return True, f"{provider}: connected"
        return False, f"{provider}: {self.last_errors.get(provider, 'no response')}"


client = UnifiedAIClient()
LLMClient = UnifiedAIClient
