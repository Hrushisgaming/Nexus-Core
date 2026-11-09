"""
actions/image_generator.py
Neural AI Image Generation Engine for Nexus Core.
Powered by Pollinations AI & FLUX / SDXL Neural Diffusion.

Generates high-resolution digital art, photorealistic portraits,
3D renders, and concept designs directly from natural language prompts.
Saves to Desktop/Nexus_Images, displays on the Circuit HUD, and opens automatically.
"""

import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.user_paths import get_user_data_dir

logger = logging.getLogger("ImageGenerator")
logger.setLevel(logging.INFO)

PLUGIN = {
    "name": "generate_image",
    "description": (
        "Generates stunning AI images, concept art, photorealistic photos, and 3D renders from text prompts. "
        "Saves the high-resolution image to Desktop, shows a preview on the HUD, and opens it automatically. "
        "Use whenever the user asks to generate, create, draw, paint, or visualize an image or picture."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Detailed text description of the image to generate."
            },
            "style": {
                "type": "STRING",
                "description": "Style: 'photorealistic', 'cyberpunk', 'anime', 'cinematic_3d', 'digital_art', 'concept_art', 'fantasy', or 'minimalist' (default: photorealistic)."
            },
            "aspect_ratio": {
                "type": "STRING",
                "description": "Aspect ratio: '1:1' (square), '16:9' (landscape), '9:16' (portrait) (default: 1:1)."
            },
            "destination": {
                "type": "STRING",
                "description": "Optional custom folder path to save the generated image."
            }
        },
        "required": ["prompt"]
    }
}

STYLE_PROMPT_ENHANCERS = {
    "photorealistic": "8k uhd, photorealistic, cinematic lighting, sharp focus, master photography, professional camera, highly detailed texture",
    "cyberpunk": "cyberpunk style, neon lights, volumetric smoke, futuristic city aesthetics, vibrant cyan and magenta glow, ultra detailed",
    "anime": "studio anime aesthetic, vibrant colors, makoto shinkai style, dynamic lighting, beautiful detailed composition",
    "cinematic_3d": "octane render, unreal engine 5, 3d render, dramatic cinematic illumination, ray tracing, volumetric fog, hyper-detailed",
    "digital_art": "artstation trending, digital painting, expressive brushwork, intricate details, vivid atmosphere",
    "concept_art": "sci-fi concept art, matte painting, epic scale, atmospheric depth, cinematic frame, award winning",
    "fantasy": "high fantasy, magical ethereal glow, mystical atmosphere, majestic composition, highly ornate details",
    "minimalist": "minimalist aesthetic, clean lines, elegant typography, modern graphic design, high contrast"
}


def _get_output_directory(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        out = Path(custom_path)
    else:
        # Default: Desktop/Nexus_Images (renamed from the old Desktop/Brahma_Images)
        images_root = Path.home() / "Desktop"
        out = images_root / "Nexus_Images"
        legacy = images_root / "Brahma_Images"
        if legacy.exists() and not out.exists():
            try:
                legacy.rename(out)  # carry over images generated before the rename
            except OSError as exc:
                logger.warning("Could not rename legacy image folder %s: %s", legacy, exc)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _open_generated_image(image_file: Path) -> None:
    """Open a generated image with the platform's default image viewer."""
    try:
        if sys.platform == "win32":
            os.startfile(str(image_file))
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", str(image_file)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(image_file)])
    except Exception as exc:
        logger.debug("Could not open generated image: %s", exc)


def _build_enhanced_prompt(prompt: str, style: str = "photorealistic") -> str:
    cleaned = re.sub(r"\s+", " ", prompt.strip())
    style_key = style.lower().strip().replace(" ", "_").replace("-", "_")
    enhancer = STYLE_PROMPT_ENHANCERS.get(style_key, STYLE_PROMPT_ENHANCERS["photorealistic"])
    
    # Avoid duplicating style terms if user already provided them
    if any(tok in cleaned.lower() for tok in ("photorealistic", "cyberpunk", "anime", "cinematic", "octane")):
        return cleaned
    return f"{cleaned}, {enhancer}"


def _selected_settings() -> Dict[str, Any]:
    try:
        import json
        from core.user_paths import get_user_data_dir
        path = get_user_data_dir() / "config" / "app_settings.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _render_with_providers(prompt: str, forced: Optional[str] = None) -> tuple:
    """Try the engine chosen in Settings first, then the others. Returns (bytes, provider_id)."""
    import base64
    import requests
    from core.image_providers import get_image_provider

    settings = _selected_settings()
    chosen = (forced or settings.get("image_engine") or "pollinations").strip().lower()
    order = [chosen] + [p for p in ("pollinations", "nvidia", "cloudflare") if p != chosen]
    errors = []
    for pid in order:
        provider = get_image_provider(pid)
        if provider is None or not provider.available:
            errors.append(f"{pid}: not configured")
            continue
        per = settings.get("image_models") if isinstance(settings.get("image_models"), dict) else {}
        model = (per.get(pid) or (settings.get("image_model") if pid == "pollinations" else None) or None)
        result = provider.generate(prompt, model=model) or {}
        if result.get("error"):
            errors.append(f"{pid}: {result['error']}")
            continue
        try:
            if result.get("image_data"):
                return base64.b64decode(result["image_data"]), pid
            if result.get("image_url"):
                resp = requests.get(result["image_url"], timeout=60,
                                    headers={"User-Agent": "NexusCore/1.0"})
                resp.raise_for_status()
                return resp.content, pid
            errors.append(f"{pid}: empty result")
        except Exception as exc:
            errors.append(f"{pid}: {exc}")
    raise RuntimeError("; ".join(errors) or "no image provider available")


def generate_image(
    parameters: Optional[Dict[str, Any]] = None,
    player: Any = None,
    speak: Any = None,
    **kwargs: Any
) -> str:
    """
    Main image synthesis entrypoint.
    Downloads the neural diffusion image from Pollinations and saves it locally.
    """
    params = dict(parameters or {})
    params.update(kwargs)

    raw_prompt = (params.get("prompt") or params.get("query") or params.get("description") or "").strip()
    if not raw_prompt:
        return "Error: Please provide a description of the image to generate."

    style = (params.get("style") or "photorealistic").lower().strip()
    aspect_ratio = params.get("aspect_ratio", "1:1")
    destination = params.get("destination")

    enhanced_prompt = _build_enhanced_prompt(raw_prompt, style)
    out_dir = _get_output_directory(destination)

    # Prepare file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_slug = re.sub(r"[^a-zA-Z0-9_]", "_", raw_prompt[:25]).strip("_") or "artwork"
    image_file = out_dir / f"nexus_{clean_slug}_{timestamp}.jpg"

    if player and hasattr(player, "write_log"):
        player.write_log(f"🎨 [ImageGen] Synthesizing image: '{raw_prompt}' ({style})...")
    if speak:
        speak(f"Synthesizing your image, sir. Rendering with {style} neural diffusion.")

    t0 = time.time()
    try:
        image_bytes, used_provider = _render_with_providers(enhanced_prompt, params.get("provider"))

        elapsed = round(time.time() - t0, 1)
        logger.info(f"[ImageGen] Rendered by {used_provider}")

        # Write to disk
        with open(image_file, "wb") as f:
            f.write(image_bytes)

        kb_size = round(len(image_bytes) / 1024, 1)
        logger.info(f"[ImageGen] Saved {image_file} ({kb_size} KB in {elapsed}s)")

        # Render deliverable on Circuit HUD if available
        if player and hasattr(player, "show_hud_deliverable"):
            try:
                player.show_hud_deliverable(
                    title=f"AI Image: {raw_prompt[:25]}",
                    summary=f"Style: {style.title()}\nSize: {kb_size} KB\nSaved to: {image_file.name}",
                    file_path=str(image_file.resolve()),
                    kind="image"
                )
            except Exception:
                pass

        if player and hasattr(player, "write_log"):
            player.write_log(f"✅ [ImageGen] Image rendered successfully ({kb_size} KB in {elapsed}s).\nSaved to: {image_file}")

        # Open with the default image viewer on the current platform.
        _open_generated_image(image_file.resolve())

        if speak:
            speak("Your image has been generated and saved to your desktop, sir.")

        return (
            f"✅ **Image Generated Successfully**\n\n"
            f"- **Prompt**: {raw_prompt}\n"
            f"- **Style**: {style.title()}\n"
            f"- **File Path**: `{image_file}`\n"
            f"- **Resolution**: High-Res ({kb_size} KB)\n"
            f"- **Render Time**: {elapsed}s\n\n"
            f"The image has been opened on your screen!"
        )

    except Exception as exc:
        err_msg = f"Failed to generate image: {exc}"
        logger.error(f"[ImageGen] {err_msg}")
        if player and hasattr(player, "write_log"):
            player.write_log(f"ERR: [ImageGen] {err_msg}")
        if speak:
            speak("There was an issue rendering the image, sir. Please check the logs.")
        return f"Error: {err_msg}"
