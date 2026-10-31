"""Secure screenshot intake: size/type/dimension validation, metadata stripping, random storage names."""
import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.exceptions import ValidationFailed

Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard
MAGIC = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
MIN_W, MIN_H, MAX_SIDE = 320, 200, 8000


@dataclass
class StoredImage:
    path: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    content_type: str
    filename: str


def _sniff(data: bytes) -> str | None:
    for sig, ct in MAGIC.items():
        if data.startswith(sig):
            return ct
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def safe_filename(name: str | None) -> str:
    base = Path(name or "upload").name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:100]
    return base or "upload"


def validate_and_store(data: bytes, filename: str | None, user_id: int) -> StoredImage:
    s = get_settings()
    if not data:
        raise ValidationFailed("Empty upload")
    if len(data) > s.max_upload_bytes:
        raise ValidationFailed(f"File too large (max {s.max_upload_bytes // 1_000_000} MB)")
    ct = _sniff(data)
    if ct is None:
        raise ValidationFailed("Unsupported file type: only PNG, JPEG and WebP images are accepted")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as exc:
        raise ValidationFailed("File is not a valid image") from exc
    w, h = img.size
    if w < MIN_W or h < MIN_H or max(w, h) > MAX_SIDE:
        raise ValidationFailed(f"Image dimensions {w}x{h} outside accepted range ({MIN_W}x{MIN_H} to {MAX_SIDE}px)")
    directory = Path(s.upload_dir) / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}.png"
    clean = img.convert("RGB")  # re-encode: drops EXIF/ICC/embedded payloads
    clean.save(path, format="PNG")
    return StoredImage(str(path), hashlib.sha256(data).hexdigest(), len(data), w, h, ct, safe_filename(filename))
