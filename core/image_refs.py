"""Reference images for image generation: local files, attachments, and images found on the web.

Everything is normalised to small JPEG files so providers get a modest upload and no
large base64 blob ever ends up in the model's context.
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger("ImageRefs")

MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
MAX_SIDE = 1280
MAX_REFERENCES = 4
_URL_RE = re.compile(r"^https?://", re.I)


def cache_dir() -> Path:
    from core.user_paths import get_user_data_dir

    d = Path(get_user_data_dir()) / "cache" / "reference_images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _normalise(raw: bytes) -> bytes:
    """Decode any common image, downscale to MAX_SIDE and return JPEG bytes."""
    from PIL import Image

    img = Image.open(io.BytesIO(raw))
    img.load()
    if img.mode not in ("RGB", "L"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    elif img.mode == "L":
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()


def download_image(url: str, session: Any = None) -> Optional[Path]:
    """Download a public http(s) image into the cache. Returns None when it is not a usable image."""
    if not _URL_RE.match(url or ""):
        return None
    import requests

    getter = session or requests
    try:
        resp = getter.get(url, timeout=20, stream=True, headers={"User-Agent": "Mozilla/5.0 NexusCore/1.0"})
        resp.raise_for_status()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if ctype and not ctype.startswith("image/") and "octet-stream" not in ctype:
            return None
        data = b""
        for chunk in resp.iter_content(65536):
            data += chunk
            if len(data) > MAX_DOWNLOAD_BYTES:
                return None
        jpeg = _normalise(data)
    except Exception as exc:
        logger.info("skipping %s: %s", url, exc)
        return None
    path = cache_dir() / f"web_{hashlib.sha1(url.encode()).hexdigest()[:12]}.jpg"
    path.write_bytes(jpeg)
    return path


def resolve_references(items: Iterable[str] | str | None, limit: int = MAX_REFERENCES) -> list[Path]:
    """Turn paths / URLs into normalised local JPEG files. Silently drops unusable entries."""
    if items is None:
        return []
    if isinstance(items, str):
        items = [p for p in re.split(r"[\n;,]\s*(?=(?:https?://|/|~|[A-Za-z]:[\\/]))", items) if p.strip()]
    out: list[Path] = []
    for item in items:
        item = str(item).strip().strip("'\"")
        if not item:
            continue
        path: Optional[Path] = None
        if _URL_RE.match(item):
            path = download_image(item)
        else:
            p = Path(item).expanduser()
            if p.is_file():
                try:
                    cached = cache_dir() / f"local_{hashlib.sha1(str(p.resolve()).encode()).hexdigest()[:12]}.jpg"
                    cached.write_bytes(_normalise(p.read_bytes()))
                    path = cached
                except Exception as exc:
                    logger.info("not an image %s: %s", p, exc)
        if path and path not in out:
            out.append(path)
        if len(out) >= limit:
            break
    return out


def to_data_uri(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def search_image_urls(query: str, limit: int = 6) -> list[str]:
    """Image URLs for a topic: Tavily (if configured) then DuckDuckGo images."""
    urls: list[str] = []
    try:
        from core.search_providers import get_search_provider

        tav = get_search_provider("tavily")
        if tav and tav.available:
            res = tav.search(query, include_images=True)
            for u in res.get("images") or []:
                u = u.get("url") if isinstance(u, dict) else u
                if u and u not in urls:
                    urls.append(u)
    except Exception as exc:
        logger.info("tavily image search failed: %s", exc)
    if len(urls) < limit:
        try:
            try:
                from ddgs import DDGS
            except Exception:
                from duckduckgo_search import DDGS
            with DDGS() as d:
                for r in d.images(query, max_results=limit):
                    u = r.get("image")
                    if u and u not in urls:
                        urls.append(u)
        except Exception as exc:
            logger.info("duckduckgo image search failed: %s", exc)
    return urls[: max(limit, 1)]


def fetch_reference_for_topic(query: str, count: int = 1) -> list[Path]:
    """Search the web for `query`, download the first usable image(s)."""
    found: list[Path] = []
    for url in search_image_urls(query, limit=count + 6):
        p = download_image(url)
        if p:
            found.append(p)
        if len(found) >= count:
            break
    return found
