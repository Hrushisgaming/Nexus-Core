"""
core/image_providers.py
=====================
Multi-provider Image Generation for Nexus Core.

Supports:
- NVIDIA (cloud, high quality)
- Pollinations (free, no API key)
- Cloudflare Images (cloud, AI generation)

Common interface:
    generate(prompt: str, model: Optional[str] = None) -> dict
    Returns: {"image_url": str, "provider": str, "model": str}
"""

from __future__ import annotations

import json
import logging
import os
from core.api_keys import get_api_key
from typing import Optional

logger = logging.getLogger("ImageProviders")


def get_pollinations_api_key() -> str:
    """Pollinations key from env or the app's saved settings (empty string if none)."""
    env_key = (os.environ.get("POLLINATIONS_API_KEY") or "").strip()
    if env_key:
        return env_key
    try:
        from core.user_paths import get_user_data_dir
        cfg_dir = get_user_data_dir() / "config"
        for name in ("app_settings.json", "api_keys.json"):
            path = cfg_dir / name
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                key = str((data or {}).get("pollinations_api_key", "") or "").strip()
                if key:
                    return key
    except Exception:
        pass
    return ""


class ImageProvider:
    """Base class for image generation providers."""

    name: str = "base"
    available: bool = False
    init_error: Optional[str] = None
    models: list[str] = []

    def generate(self, prompt: str, model: Optional[str] = None) -> dict:
        raise NotImplementedError

    def get_models(self) -> list[str]:
        return self.models


# ══════════════════════════════════════════════════════════════════════════════
# NVIDIA NIM Image Generation
# ══════════════════════════════════════════════════════════════════════════════


class NVIDIAImageProvider(ImageProvider):
    """NVIDIA NIM hosted FLUX.3 Klein (text-to-image and reference-image editing)."""

    name = "nvidia"
    supports_references = True
    BASE_URL = "https://ai.api.nvidia.com/v1/genai/"
    # Output sizes must be multiples of 16 within 512..1568 and <= 1,062,400 pixels.
    SIZES = {"1:1": (1024, 1024), "16:9": (1344, 768), "9:16": (768, 1344), "4:3": (1152, 864), "3:4": (864, 1152)}

    def __init__(self, api_key: Optional[str] = None, model: str = "black-forest-labs/flux-3-image-klein"):
        self.api_key = get_api_key("nvidia_api_key", "NVIDIA_API_KEY", api_key)
        self.default_model = model
        self.models = [
            "black-forest-labs/flux-3-image-klein",
            "black-forest-labs/flux.1-dev",
            "black-forest-labs/flux.1-schnell",
        ]
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        if not self.api_key:
            self._init_error = "NVIDIA_API_KEY not set"
            logger.warning("NVIDIA Image unavailable: no API key")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def generate(self, prompt: str, model: Optional[str] = None, reference_images: Optional[list] = None,
                 aspect_ratio: str = "1:1") -> dict:
        """reference_images: list of data URIs ("data:image/jpeg;base64,...").

        Returns {"image_data": b64} on success, or {"error", "reference_rejected": bool}.
        """
        if not self._available:
            return {"error": self._init_error or "NVIDIA not configured", "provider": "nvidia"}
        try:
            import requests
            model_id = model or self.default_model
            width, height = self.SIZES.get(aspect_ratio, self.SIZES["1:1"])
            payload: dict = {"prompt": prompt[:2000], "width": width, "height": height}
            if reference_images and model_id.endswith("klein"):
                payload["image"] = list(reference_images)[:4]
            resp = requests.post(
                f"{self.BASE_URL}{model_id}",
                headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                json=payload, timeout=120,
            )
            if resp.status_code == 200:
                art = (resp.json().get("artifacts") or [{}])[0]
                if art.get("finishReason") == "CONTENT_FILTERED":
                    return {"error": "blocked by NVIDIA's content filter", "provider": "nvidia"}
                if art.get("base64"):
                    return {"image_data": art["base64"], "provider": "nvidia", "model": model_id}
                return {"error": "No image returned", "provider": "nvidia"}
            logger.error(f"NVIDIA Image error {resp.status_code}: {resp.text[:300]}")
            return {
                "error": f"HTTP {resp.status_code}: {resp.text[:160]}", "provider": "nvidia",
                # 422 with an image field = the hosted API refused the uploaded reference.
                "reference_rejected": bool(reference_images) and resp.status_code in (400, 422),
            }
        except Exception as exc:
            logger.error(f"NVIDIA Image error: {exc}")
            return {"error": str(exc), "provider": "nvidia"}

    def get_models(self) -> list[str]:
        return self.models


# ══════════════════════════════════════════════════════════════════════════════
# Pollinations Image Generation (works without a key; an API key unlocks gen.pollinations.ai)
# ══════════════════════════════════════════════════════════════════════════════


class PollinationsImageProvider(ImageProvider):
    name = "pollinations"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = (api_key or get_pollinations_api_key()).strip()
        self.default_model = model or "community/scriptsnsenses-sys/flux-2-dev-free"
        self.models = [
            "flux",
            "flux-pro",
            "flux-dev",
            "turbo",
            "community/scriptsnsenses-sys/flux-2-dev-free",
        ]
        self._available = True
        self._init_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    supports_references = True
    UPLOAD_URL = "https://media.pollinations.ai/upload"
    # Editing-capable models tried (in order) when a reference image is given.
    EDIT_MODELS = ["kontext", "klein", "black-forest-labs/flux.2-klein-4b"]

    def _upload_reference(self, data_uri: str) -> Optional[str]:
        """Upload one reference (data URI) to Pollinations' media store; returns its public URL."""
        import base64
        import requests
        try:
            raw = base64.b64decode(data_uri.split(",", 1)[1])
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            resp = requests.post(self.UPLOAD_URL, files={"file": ("reference.jpg", raw, "image/jpeg")},
                                 headers=headers, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("url") or (f"https://media.pollinations.ai/{data['id']}" if data.get("id") else None)
            logger.error(f"Pollinations upload error {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            logger.error(f"Pollinations upload error: {exc}")
        return None

    def generate(self, prompt: str, model: Optional[str] = None, reference_images: Optional[list] = None,
                 aspect_ratio: str = "1:1") -> dict:
        if not self._available:
            return {"error": self._init_error or "Pollinations not available", "provider": "pollinations"}
        try:
            import requests
            width, height = {"16:9": (1344, 768), "9:16": (768, 1344)}.get(aspect_ratio, (1024, 1024))
            params = {"width": width, "height": height, "nologo": "true"}
            models = [model or self.default_model]
            if reference_images:
                urls = [u for u in (self._upload_reference(r) for r in reference_images[:4]) if u]
                if not urls:
                    return {"error": "couldn't upload the reference image", "provider": "pollinations",
                            "reference_rejected": True}
                params["image"] = "|".join(urls)
                models = [m for m in dict.fromkeys(self.EDIT_MODELS + models)]
            headers = {}
            if self.api_key:
                # Keyed requests go through the unified endpoint with Bearer auth
                url = f"https://gen.pollinations.ai/image/{prompt}"
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                url = f"https://image.pollinations.ai/prompt/{prompt}"
            last = "no model answered"
            for model_id in models:
                resp = requests.get(url, params={**params, "model": model_id}, headers=headers, timeout=90)
                if resp.status_code == 200 and (resp.headers.get("Content-Type", "image/").startswith("image/")):
                    return {"image_url": resp.url, "provider": "pollinations", "model": model_id}
                last = f"HTTP {resp.status_code} ({model_id})"
                logger.error(f"Pollinations error {resp.status_code} on {model_id}: {resp.text[:200]}")
            return {"error": last, "provider": "pollinations", "reference_rejected": bool(reference_images)}
        except Exception as exc:
            logger.error(f"Pollinations error: {exc}")
            return {"error": str(exc), "provider": "pollinations"}

    def get_models(self) -> list[str]:
        return self.models


# ══════════════════════════════════════════════════════════════════════════════
# Cloudflare Images (Cloudflare AI)
# ══════════════════════════════════════════════════════════════════════════════


class CloudflareImageProvider(ImageProvider):
    name = "cloudflare"

    def __init__(self, api_key: Optional[str] = None, account_id: Optional[str] = None, model: str = "@cf/stabilityai/stable-diffusion-xl-base-1.0"):
        self.api_key = get_api_key("cloudflare_api_key", "CLOUDFLARE_API_KEY", api_key)
        self.account_id = get_api_key("cloudflare_account_id", "CLOUDFLARE_ACCOUNT_ID", account_id)
        self.default_model = model
        self.models = [
            "@cf/stabilityai/stable-diffusion-xl-base-1.0",
            "@cf/lykon/dreamshaper-8-lcm",
        ]
        self._available = bool(self.api_key and self.account_id)
        self._init_error: Optional[str] = None
        if not self.api_key or not self.account_id:
            self._init_error = "CLOUDFLARE_API_KEY and CLOUDFLARE_ACCOUNT_ID not set"
            logger.warning("Cloudflare Images unavailable: missing credentials")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def generate(self, prompt: str, model: Optional[str] = None) -> dict:
        if not self._available:
            return {"error": self._init_error or "Cloudflare not configured", "provider": "cloudflare"}
        try:
            import requests
            model_id = model or self.default_model
            url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{model_id}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "prompt": prompt,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    result = data.get("result", {})
                    image_data = result.get("image", "")
                    return {
                        "image_data": image_data,
                        "provider": "cloudflare",
                        "model": model_id,
                        "format": "base64",
                    }
                return {"error": data.get("errors", ["Unknown error"]), "provider": "cloudflare"}
            logger.error(f"Cloudflare Image error {resp.status_code}: {resp.text[:200]}")
            return {"error": f"HTTP {resp.status_code}", "provider": "cloudflare"}
        except Exception as exc:
            logger.error(f"Cloudflare Image error: {exc}")
            return {"error": str(exc), "provider": "cloudflare"}

    def get_models(self) -> list[str]:
        return self.models


# ══════════════════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════════════════


_PROVIDER_REGISTRY: dict[str, type[ImageProvider]] = {
    "nvidia": NVIDIAImageProvider,
    "pollinations": PollinationsImageProvider,
    "cloudflare": CloudflareImageProvider,
}


def get_image_provider(provider_id: str, **kwargs) -> Optional[ImageProvider]:
    """Instantiate an image provider by ID."""
    cls = _PROVIDER_REGISTRY.get(provider_id)
    if cls is None:
        logger.error(f"Unknown image provider: {provider_id}")
        return None
    try:
        return cls(**kwargs)
    except Exception as exc:
        logger.error(f"Failed to instantiate image {provider_id}: {exc}")
        return None


def get_available_image_providers() -> list[dict]:
    """Return list of image providers with availability status."""
    providers = []
    for pid, cls in _PROVIDER_REGISTRY.items():
        try:
            instance = cls()
            providers.append({
                "id": pid,
                "name": cls.name,
                "available": instance.available,
                "init_error": instance.init_error,
                "models": instance.models,
            })
        except Exception as exc:
            providers.append({
                "id": pid,
                "name": cls.name,
                "available": False,
                "init_error": str(exc),
                "models": [],
            })
    return providers


# Default instance manager
_default_provider: Optional[ImageProvider] = None


def get_default_image_provider() -> Optional[ImageProvider]:
    """Get the default image provider (Pollinations preferred - free, then NVIDIA, then Cloudflare)."""
    global _default_provider
    if _default_provider is None:
        for pid in ("pollinations", "nvidia", "cloudflare"):
            provider = get_image_provider(pid)
            if provider and provider.available:
                _default_provider = provider
                break
    return _default_provider
