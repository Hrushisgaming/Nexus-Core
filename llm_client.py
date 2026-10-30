from core.user_paths import get_user_data_dir
import json
import logging
import os
import requests
from pathlib import Path
from typing import Optional
from or_client import client as openrouter_client

logger = logging.getLogger("llm_client")

def _get_base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR = _get_base_dir()
SETTINGS_PATH = get_user_data_dir() / "config" / "app_settings.json"

class UnifiedAIClient:
    def __init__(self):
        self._provider = "OpenRouter"
        self._local_url = "http://localhost:11434/v1"
        self._local_model = "llama3.2"
        self.reload_settings()

    def reload_settings(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._provider = data.get("default_ai_provider", "OpenRouter")
            self._local_url = data.get("local_ai_url", "http://localhost:11434/v1").rstrip("/")
            self._local_model = data.get("local_ai_model", "llama3.2")
        except Exception as e:
            logger.error(f"[LLM Client] Failed to load settings: {e}")

    def _local_chat_completion(self, messages: list[dict], temperature: float = 0.7, response_format: Optional[dict] = None) -> Optional[str]:
        payload = {
            "model": self._local_model,
            "messages": messages,
            "temperature": temperature
        }
        if response_format:
            payload["response_format"] = response_format

        endpoint = f"{self._local_url}/chat/completions"
        try:
            resp = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=120
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content.strip() if content else None
            else:
                logger.error(f"[LLM Client] Local AI Error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"[LLM Client] Local AI Request Failed: {e}")
            return None

    def _get_gemini_client(self):
        try:
            from google import genai
            api_keys_path = get_user_data_dir() / "config" / "api_keys.json"
            if not api_keys_path.exists():
                return None
            with open(api_keys_path, "r", encoding="utf-8") as f:
                key = json.load(f).get("gemini_api_key", "").strip()
            if not key:
                return None
            return genai.Client(api_key=key, http_options={"api_version": "v1beta"})
        except Exception as e:
            logger.error(f"[LLM Client] Failed to init Gemini client: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # API key loaders
    # ═══════════════════════════════════════════════════════════════════

    def _load_api_key_from_file(self, key_name: str) -> str:
        """Generic loader for any key from api_keys.json."""
        try:
            api_keys_path = get_user_data_dir() / "config" / "api_keys.json"
            if api_keys_path.exists():
                with open(api_keys_path, "r", encoding="utf-8") as f:
                    key = json.load(f).get(key_name, "").strip()
                if key:
                    return key
        except Exception as e:
            logger.error(f"[LLM Client] Failed reading {key_name}: {e}")
        return ""

    def _load_nvidia_key(self) -> str:
        """Load NVIDIA API key from env or api_keys.json."""
        import os
        env_key = os.environ.get("NVIDIA_API_KEY", "").strip()
        if env_key:
            return env_key
        return self._load_api_key_from_file("nvidia_api_key")

    def _load_groq_key(self) -> str:
        """Load Groq API key from env or api_keys.json."""
        import os
        env_key = os.environ.get("GROQ_API_KEY", "").strip()
        if env_key:
            return env_key
        return self._load_api_key_from_file("groq_api_key")

    def _get_custom_provider_settings(self) -> dict:
        """Load custom OpenAI-compatible provider settings from app_settings.json."""
        try:
            data = {}
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
        return {
            "base_url": (data.get("custom_ai_base_url") or "").strip().rstrip("/"),
            "api_key": self._load_api_key_from_file("custom_ai_api_key")
            or os.environ.get("CUSTOM_AI_API_KEY", "").strip(),
            "model": (data.get("custom_ai_model") or "custom-model").strip(),
        }

    # ═══════════════════════════════════════════════════════════════════
    # Generic OpenAI-compatible chat / vision (used by NVIDIA, Groq, Custom)
    # ════════════════════════════════════════════════════════════════════

    def _openai_compatible_chat_completion(
        self,
        messages: list[dict],
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Optional[str]:
        """Chat completion via any OpenAI-compatible API endpoint."""
        if not api_key or not base_url:
            return None
        try:
            import requests
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
                timeout=120,
            )
            if resp.status_code == 200:
                data = resp.json()
                return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            logger.error(
                f"[LLM Client] OpenAI-compatible API error {resp.status_code}: {resp.text[:200]}"
            )
            return None
        except Exception as e:
            logger.error(f"[LLM Client] OpenAI-compatible request failed: {e}")
            return None

    def _openai_compatible_vision(
        self,
        prompt: str,
        image_b64: str,
        base_url: str,
        api_key: str,
        model: str,
        mime: str = "image/png",
        system: str = "Analyze the image.",
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Vision via any OpenAI-compatible API endpoint."""
        if not api_key or not base_url:
            return None
        try:
            import requests
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                            ],
                        },
                    ],
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
                timeout=120,
            )
            if resp.status_code == 200:
                data = resp.json()
                return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            logger.error(
                f"[LLM Client] OpenAI-compatible vision error {resp.status_code}: {resp.text[:200]}"
            )
            return None
        except Exception as e:
            logger.error(f"[LLM Client] OpenAI-compatible vision failed: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # Provider-specific wrappers
    # ═══════════════════════════════════════════════════════════════════

    def _nvidia_chat_completion(
        self, messages: list[dict], temperature: float = 0.7, model: str = "nvidia/nemotron-3-super-120b-a12b", max_tokens: int = 4096
    ) -> Optional[str]:
        """Chat completion via NVIDIA NIM API."""
        return self._openai_compatible_chat_completion(
            messages,
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self._load_nvidia_key(),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _nvidia_vision(
        self,
        prompt: str,
        image_b64: str,
        mime: str = "image/png",
        system: str = "Analyze the image.",
        model: str = "nvidia/nemotron-3-super-120b-a12b",
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Vision via NVIDIA NIM API."""
        return self._openai_compatible_vision(
            prompt,
            image_b64,
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self._load_nvidia_key(),
            model=model,
            mime=mime,
            system=system,
            max_tokens=max_tokens,
        )

    def _groq_chat_completion(
        self, messages: list[dict], temperature: float = 0.7, model: str = "llama-3.1-8b-instant", max_tokens: int = 4096
    ) -> Optional[str]:
        """Chat completion via Groq API."""
        return self._openai_compatible_chat_completion(
            messages,
            base_url="https://api.groq.com/openai/v1",
            api_key=self._load_groq_key(),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _groq_vision(
        self,
        prompt: str,
        image_b64: str,
        mime: str = "image/png",
        system: str = "Analyze the image.",
        model: str = "llama-3.2-11b-vision-preview",
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Vision via Groq API."""
        return self._openai_compatible_vision(
            prompt,
            image_b64,
            base_url="https://api.groq.com/openai/v1",
            api_key=self._load_groq_key(),
            model=model,
            mime=mime,
            system=system,
            max_tokens=max_tokens,
        )

    def _custom_chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Optional[str]:
        """Chat completion via a custom OpenAI-compatible endpoint."""
        settings = self._get_custom_provider_settings()
        if not settings["base_url"] or not settings["api_key"]:
            return None
        return self._openai_compatible_chat_completion(
            messages,
            base_url=settings["base_url"],
            api_key=settings["api_key"],
            model=model or settings["model"],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _custom_vision(
        self,
        prompt: str,
        image_b64: str,
        mime: str = "image/png",
        system: str = "Analyze the image.",
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Vision via a custom OpenAI-compatible endpoint."""
        settings = self._get_custom_provider_settings()
        if not settings["base_url"] or not settings["api_key"]:
            return None
        return self._openai_compatible_vision(
            prompt,
            image_b64,
            base_url=settings["base_url"],
            api_key=settings["api_key"],
            model=model or settings["model"],
            mime=mime,
            system=system,
            max_tokens=max_tokens,
        )

    def _gemini_chat_completion(self, messages: list[dict], temperature: float = 0.7, json_mode: bool = False) -> Optional[str]:
        client = self._get_gemini_client()
        if not client:
            return None
        try:
            from google.genai import types
            sys_parts = [m["content"] for m in messages if m["role"] == "system"]
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
                response_mime_type="application/json" if json_mode else None
            )
            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=contents,
                config=config
            )
            return resp.text.strip() if resp and resp.text else None
        except Exception as e:
            logger.error(f"[LLM Client] Gemini request failed: {e}")
            return None

    def chat(self, prompt: str, system: str = "You are a helpful assistant.", history: Optional[list[dict]] = None, model: Optional[str] = None, max_tokens: int = 4096, temperature: float = 0.7) -> str:
        self.reload_settings()
        provider = self._provider
        nvidia_model = model or "nvidia/nemotron-3-super-120b-a12b"
        groq_model = model or "llama-3.1-8b-instant"

        if provider in ("Gemini", "Google Gemini"):
            messages = [{"role": "system", "content": system}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})
            result = self._gemini_chat_completion(messages, temperature)
            if result:
                return result
            try:
                return openrouter_client.chat(prompt, system, history, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        elif provider == "NVIDIA":
            messages = [{"role": "system", "content": system}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})
            result = self._nvidia_chat_completion(messages, temperature, nvidia_model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.chat(prompt, system, history, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        elif provider == "Groq":
            messages = [{"role": "system", "content": system}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})
            result = self._groq_chat_completion(messages, temperature, groq_model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.chat(prompt, system, history, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        elif provider == "Custom":
            messages = [{"role": "system", "content": system}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})
            result = self._custom_chat_completion(messages, temperature, model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.chat(prompt, system, history, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        elif self._provider == "Local":
            messages = [{"role": "system", "content": system}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})
            result = self._local_chat_completion(messages, temperature)
            if result:
                return result
            else:
                raise RuntimeError("Local AI request failed. Please check if Ollama or LM Studio is running.")
        else:
            return openrouter_client.chat(prompt, system, history, model, max_tokens, temperature)

    def chat_json(self, prompt: str, system: str = "Return ONLY valid JSON.", model: Optional[str] = None, max_tokens: int = 4096) -> dict:
        self.reload_settings()
        provider = self._provider
        nvidia_model = model or "nvidia/nemotron-3-super-120b-a12b"
        groq_model = model or "llama-3.1-8b-instant"

        if provider in ("Gemini", "Google Gemini"):
            messages = [
                {"role": "system", "content": system + " Output valid JSON only, without any markdown formatting."},
                {"role": "user", "content": prompt}
            ]
            raw = self._gemini_chat_completion(messages, temperature=0.2, json_mode=True)
            if not raw:
                try:
                    return openrouter_client.chat_json(prompt, system, model, max_tokens)
                except Exception:
                    pass
                raw = self._local_chat_completion(messages, temperature=0.2, response_format={"type": "json_object"})
            if not raw:
                raise RuntimeError("AI request failed for JSON generation.")
            
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip().rstrip("`").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError as e:
                raise ValueError(f"Gemini model returned unparseable JSON: {e}\nRaw output: {raw[:200]}")
        elif provider == "NVIDIA":
            messages = [
                {"role": "system", "content": system + " Output valid JSON only, without any markdown formatting."},
                {"role": "user", "content": prompt}
            ]
            raw = self._nvidia_chat_completion(messages, temperature=0.2, model=nvidia_model, max_tokens=max_tokens)
            if not raw:
                try:
                    return openrouter_client.chat_json(prompt, system, model, max_tokens)
                except Exception:
                    pass
                raw = self._local_chat_completion(messages, temperature=0.2, response_format={"type": "json_object"})
            if not raw:
                raise RuntimeError("NVIDIA request failed for JSON generation.")
            
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip().rstrip("`").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError as e:
                raise ValueError(f"NVIDIA model returned unparseable JSON: {e}\nRaw output: {raw[:200]}")
        elif provider == "Groq":
            messages = [
                {"role": "system", "content": system + " Output valid JSON only, without any markdown formatting."},
                {"role": "user", "content": prompt}
            ]
            raw = self._groq_chat_completion(messages, temperature=0.2, model=groq_model, max_tokens=max_tokens)
            if not raw:
                try:
                    return openrouter_client.chat_json(prompt, system, model, max_tokens)
                except Exception:
                    pass
                raw = self._local_chat_completion(messages, temperature=0.2, response_format={"type": "json_object"})
            if not raw:
                raise RuntimeError("Groq request failed for JSON generation.")
            
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip().rstrip("`").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError as e:
                raise ValueError(f"Groq model returned unparseable JSON: {e}\nRaw output: {raw[:200]}")
        elif provider == "Custom":
            messages = [
                {"role": "system", "content": system + " Output valid JSON only, without any markdown formatting."},
                {"role": "user", "content": prompt}
            ]
            raw = self._custom_chat_completion(messages, temperature=0.2, model=model, max_tokens=max_tokens)
            if not raw:
                try:
                    return openrouter_client.chat_json(prompt, system, model, max_tokens)
                except Exception:
                    pass
                raw = self._local_chat_completion(messages, temperature=0.2, response_format={"type": "json_object"})
            if not raw:
                raise RuntimeError("Custom provider request failed for JSON generation.")
            
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip().rstrip("`").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError as e:
                raise ValueError(f"Custom model returned unparseable JSON: {e}\nRaw output: {raw[:200]}")
        elif self._provider == "Local":
            messages = [
                {"role": "system", "content": system + " Output valid JSON only, without any markdown formatting."},
                {"role": "user", "content": prompt}
            ]
            raw = self._local_chat_completion(messages, temperature=0.2, response_format={"type": "json_object"})
            if not raw:
                raise RuntimeError("Local AI request failed.")
            
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip().rstrip("`").strip()
            
            try:
                return json.loads(clean)
            except json.JSONDecodeError as e:
                raise ValueError(f"Local model returned unparseable JSON: {e}\nRaw output: {raw[:200]}")
        else:
            return openrouter_client.chat_json(prompt, system, model, max_tokens)

    def vision(self, prompt: str, image_b64: str, mime: str = "image/png", system: str = "Analyze the image.", model: Optional[str] = None, max_tokens: int = 1024) -> str:
        self.reload_settings()
        provider = self._provider
        nvidia_model = model or "nvidia/nemotron-3-super-120b-a12b"
        groq_model = model or "llama-3.2-11b-vision-preview"

        if provider == "NVIDIA":
            result = self._nvidia_vision(prompt, image_b64, mime, system, nvidia_model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.vision(prompt, image_b64, mime, system, model, max_tokens)
            except Exception:
                pass
            raise RuntimeError("NVIDIA vision request failed.")
        elif provider == "Groq":
            result = self._groq_vision(prompt, image_b64, mime, system, groq_model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.vision(prompt, image_b64, mime, system, model, max_tokens)
            except Exception:
                pass
            raise RuntimeError("Groq vision request failed.")
        elif provider == "Custom":
            result = self._custom_vision(prompt, image_b64, mime, system, model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.vision(prompt, image_b64, mime, system, model, max_tokens)
            except Exception:
                pass
            raise RuntimeError("Custom provider vision request failed.")
        if provider in ("Gemini", "Google Gemini"):
            client = self._get_gemini_client()
            if client:
                try:
                    import base64
                    from google.genai import types
                    image_bytes = base64.b64decode(image_b64)
                    resp = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type=mime),
                            prompt
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=system,
                            max_output_tokens=max_tokens
                        )
                    )
                    if resp and resp.text:
                        return resp.text.strip()
                except Exception as e:
                    logger.error(f"[LLM Client] Gemini vision request failed: {e}")
            try:
                return openrouter_client.vision(prompt, image_b64, mime, system, model, max_tokens)
            except Exception:
                pass
            raise RuntimeError("Vision request failed with Gemini provider.")
        elif self._provider == "Local":
            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            result = self._local_chat_completion(messages, temperature=0.2)
            if result:
                return result
            raise RuntimeError("Local AI vision request failed.")
        else:
            return openrouter_client.vision(prompt, image_b64, mime, system, model, max_tokens)

    def vision_from_file(self, prompt: str, image_path: str, system: str = "Analyze the image.", model: Optional[str] = None, max_tokens: int = 1024) -> str:
        self.reload_settings()
        provider = self._provider
        if provider in ("NVIDIA", "Groq", "Custom"):
            import base64
            path = Path(image_path)
            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
            mime = mime_map.get(path.suffix.lower(), "image/png")
            with open(path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            return self.vision(prompt, image_b64, mime, system, model, max_tokens)
        if provider in ("Local", "Gemini", "Google Gemini"):
            import base64
            path = Path(image_path)
            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
            mime = mime_map.get(path.suffix.lower(), "image/png")
            with open(path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            return self.vision(prompt, image_b64, mime, system, model, max_tokens)
        else:
            return openrouter_client.vision_from_file(prompt, image_path, system, model, max_tokens)

    def multi_turn(self, messages: list[dict], model: Optional[str] = None, max_tokens: int = 4096, temperature: float = 0.7) -> str:
        self.reload_settings()
        provider = self._provider
        nvidia_model = model or "nvidia/nemotron-3-super-120b-a12b"
        groq_model = model or "llama-3.1-8b-instant"

        if provider == "NVIDIA":
            result = self._nvidia_chat_completion(messages, temperature, nvidia_model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.multi_turn(messages, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        elif provider == "Groq":
            result = self._groq_chat_completion(messages, temperature, groq_model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.multi_turn(messages, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        elif provider == "Custom":
            result = self._custom_chat_completion(messages, temperature, model, max_tokens)
            if result:
                return result
            try:
                return openrouter_client.multi_turn(messages, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        if provider in ("Gemini", "Google Gemini"):
            result = self._gemini_chat_completion(messages, temperature)
            if result:
                return result
            try:
                return openrouter_client.multi_turn(messages, model, max_tokens, temperature)
            except Exception:
                pass
            return self._local_chat_completion(messages, temperature) or ""
        elif self._provider == "Local":
            result = self._local_chat_completion(messages, temperature)
            if result:
                return result
            raise RuntimeError("Local AI request failed.")
        else:
            return openrouter_client.multi_turn(messages, model, max_tokens, temperature)

client = UnifiedAIClient()
LLMClient = UnifiedAIClient
