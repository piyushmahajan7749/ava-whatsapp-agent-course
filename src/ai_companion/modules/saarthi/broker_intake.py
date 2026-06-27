"""Broker listing intake — handles WhatsApp messages from known broker numbers.

When a broker posts in the group:
- Text message  → AI-parse listing → create ACTIVE property in Saarthi DB
- Image message → download from Meta → upload to Saarthi → attach to last listing

Photo grouping: we keep an in-memory map of (broker_phone → (listing_id, ts)).
Any image sent by the same broker within PHOTO_WINDOW_SECONDS of the last text
listing is attached to that listing. After the window, photos are dropped with a
warning logged (broker should send photos right after the listing text).
"""

import io
import logging
import time
from typing import Optional

import httpx

from ai_companion.settings import settings

logger = logging.getLogger(__name__)

PHOTO_WINDOW_SECONDS = 30 * 60  # 30 minutes

# in-memory: broker_phone -> (listing_id, created_at_ts)
_pending: dict[str, tuple[str, float]] = {}


def get_broker_set() -> set[str]:
    """Return the set of known broker phone numbers (digits only)."""
    raw = (settings.BROKER_PHONE_NUMBERS or "").strip()
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def is_broker(phone: str) -> bool:
    digits = "".join(c for c in phone if c.isdigit())
    return digits in get_broker_set()


def _saarthi_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.SAARTHI_API_KEY}", "Content-Type": "application/json"}


def _wa_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}


# ---------------------------------------------------------------------------
# Text listing
# ---------------------------------------------------------------------------

def handle_broker_text(phone: str, text: str, sender_name: Optional[str] = None) -> str:
    """Parse a broker's text message as a listing. Returns reply string."""
    if not settings.SAARTHI_API_KEY or not settings.SAARTHI_API_URL:
        logger.warning("[broker_intake] Saarthi API not configured — skipping intake.")
        return "❌ Listing intake not configured."

    base = settings.SAARTHI_API_URL.rstrip("/")
    try:
        resp = httpx.post(
            f"{base}/api/agent/intake",
            json={"text": text, "senderName": sender_name, "senderPhone": phone},
            headers=_saarthi_headers(),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("[broker_intake] intake API error: %s", exc)
        return "⚠️ Error saving listing. Try again."

    listing_id: str = data.get("listingId", "")
    title: str = data.get("title", "Listing")

    # Remember this listing for incoming photos
    _pending[phone] = (listing_id, time.monotonic())

    return f"✅ Got it! *{title}* saved. Send photos to add them 📸"


# ---------------------------------------------------------------------------
# Image / media
# ---------------------------------------------------------------------------

def handle_broker_image(phone: str, media_id: str, mime_type: str = "image/jpeg") -> str:
    """Download WhatsApp media, upload to Saarthi, attach to pending listing."""
    if not settings.WHATSAPP_ACCESS_TOKEN:
        logger.warning("[broker_intake] WHATSAPP_ACCESS_TOKEN not set — cannot download media.")
        return ""

    # Check if there's a pending listing for this broker
    entry = _pending.get(phone)
    if not entry:
        logger.info("[broker_intake] image from %s but no pending listing — ignoring.", phone)
        return ""

    listing_id, created_at = entry
    if time.monotonic() - created_at > PHOTO_WINDOW_SECONDS:
        logger.info("[broker_intake] photo window expired for %s — ignoring image.", phone)
        _pending.pop(phone, None)
        return ""

    # 1. Get media download URL from Meta
    try:
        meta_resp = httpx.get(
            f"https://graph.facebook.com/v21.0/{media_id}",
            headers=_wa_headers(),
            timeout=15,
        )
        meta_resp.raise_for_status()
        download_url = meta_resp.json().get("url")
        if not download_url:
            raise ValueError("No url in media metadata response")
    except Exception as exc:
        logger.error("[broker_intake] failed to get media URL for %s: %s", media_id, exc)
        return ""

    # 2. Download the media bytes
    try:
        img_resp = httpx.get(download_url, headers=_wa_headers(), timeout=30)
        img_resp.raise_for_status()
        img_bytes = img_resp.content
    except Exception as exc:
        logger.error("[broker_intake] failed to download media %s: %s", media_id, exc)
        return ""

    # 3. Upload to Saarthi (which stores to Azure Blob)
    base = (settings.SAARTHI_API_URL or "").rstrip("/")
    ext = mime_type.split("/")[-1].replace("jpeg", "jpg")
    filename = f"listing-{listing_id[:8]}.{ext}"
    try:
        upload_resp = httpx.post(
            f"{base}/api/agent/upload",
            headers={"Authorization": f"Bearer {settings.SAARTHI_API_KEY}"},
            files={"file": (filename, io.BytesIO(img_bytes), mime_type)},
            timeout=60,
        )
        upload_resp.raise_for_status()
        photo_url = upload_resp.json().get("url", "")
        if not photo_url:
            raise ValueError("No url in upload response")
    except Exception as exc:
        logger.error("[broker_intake] upload failed for listing %s: %s", listing_id, exc)
        return ""

    # 4. Attach URL to the listing
    try:
        patch_resp = httpx.patch(
            f"{base}/api/agent/listings/{listing_id}/media",
            json={"photoUrls": [photo_url]},
            headers=_saarthi_headers(),
            timeout=15,
        )
        patch_resp.raise_for_status()
        count = patch_resp.json().get("imageCount", "?")
    except Exception as exc:
        logger.error("[broker_intake] patch media failed for listing %s: %s", listing_id, exc)
        return ""

    logger.info("[broker_intake] photo %d attached to listing %s", count, listing_id)
    return f"📸 Photo {count} added!"
