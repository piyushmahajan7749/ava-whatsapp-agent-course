"""Broker intake — handles WhatsApp messages from known broker numbers.

Two intake flows:
- Listing intake: broker posts a property (text + photos) → ACTIVE Property in DB
- Lead intake:   broker sends a lead referral (text or audio) → Lead in DB + outbound WA to lead

Detection:
- Image               → listing (with optional caption)
- Audio               → transcribe → AI classify → listing or lead
- Text                → AI classify → listing or lead
"""

import io
import json
import logging
import time
from typing import Optional

import httpx
from openai import AzureOpenAI

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


def _ai_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )


# ---------------------------------------------------------------------------
# AI classification + lead extraction
# ---------------------------------------------------------------------------

_CLASSIFY_PROMPT = (
    "You are classifying a WhatsApp message from a real-estate broker in Indore, India. "
    "Reply with ONLY one word.\n\n"
    "LISTING → the message is about a property available for sale/rent "
    "(has price, size, location of a property).\n"
    "LEAD → the message is about a client/buyer who is looking for property "
    "(mentions a person's name, phone number, or their requirements to BUY/RENT).\n\n"
    "Message: {text}"
)

_EXTRACT_LEAD_PROMPT = (
    "Extract lead (property buyer/renter) details from this broker message. "
    "The broker is referring a client who wants to buy or rent property in Indore.\n\n"
    "Return JSON with these exact fields (null if not found):\n"
    '{"name":string|null,"phone":string|null,'
    '"listingFor":"SALE"|"RENT"|null,'
    '"bhk":number|null,'
    '"type":"FLAT"|"HOUSE"|"VILLA"|"PLOT"|"COMMERCIAL"|null,'
    '"budgetMin":number|null,"budgetMax":number|null,'
    '"localities":string[],'
    '"timeline":string|null,'
    '"notes":string|null}'
)


def classify_broker_message(text: str) -> str:
    """Returns 'listing' or 'lead'. Defaults to 'listing' on error."""
    try:
        # gpt-5-mini is a reasoning model: it needs max_completion_tokens with
        # real headroom (reasoning eats the budget) and only the default
        # temperature. max_tokens=5 / temperature=0 made every call error out
        # and silently default to "listing".
        resp = _ai_client().chat.completions.create(
            model=settings.SMALL_TEXT_MODEL_NAME,
            messages=[{"role": "user", "content": _CLASSIFY_PROMPT.format(text=text[:600])}],
            max_completion_tokens=2000,
        )
        result = (resp.choices[0].message.content or "").strip().upper()
        return "lead" if "LEAD" in result else "listing"
    except Exception as exc:
        logger.warning("[broker_intake] classify failed, defaulting to listing: %s", exc)
        return "listing"


def _extract_lead(text: str) -> dict:
    """Extract structured lead info from broker referral text."""
    try:
        resp = _ai_client().chat.completions.create(
            model=settings.TEXT_MODEL_NAME,
            messages=[
                {"role": "system", "content": _EXTRACT_LEAD_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        logger.error("[broker_intake] lead extraction failed: %s", exc)
        return {}


def _send_whatsapp(to_number: str, text: str) -> None:
    """Fire-and-forget WhatsApp text message."""
    token = settings.WHATSAPP_ACCESS_TOKEN
    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
    if not token or not phone_id:
        logger.warning("[broker_intake] WA credentials not set — cannot send to %s", to_number)
        return
    try:
        httpx.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": text},
            },
            timeout=15,
        )
    except Exception as exc:
        logger.error("[broker_intake] WA send to %s failed: %s", to_number, exc)


# ---------------------------------------------------------------------------
# Lead intake
# ---------------------------------------------------------------------------

def handle_broker_lead(phone: str, text: str, sender_name: Optional[str] = None) -> str:
    """
    Parse broker's lead referral, create lead in CRM, send outbound WA to lead.
    Returns the reply string for the broker.
    """
    if not settings.SAARTHI_API_KEY or not settings.SAARTHI_API_URL:
        return "❌ Lead intake not configured."

    extracted = _extract_lead(text)

    # Normalize phone to digits with country code
    raw_phone = extracted.get("phone") or ""
    lead_phone: Optional[str] = None
    if raw_phone:
        digits = "".join(c for c in raw_phone if c.isdigit())
        if len(digits) == 10:
            digits = "91" + digits  # assume India
        if len(digits) >= 10:
            lead_phone = digits

    lead_name: Optional[str] = extracted.get("name")

    requirements: dict = {}
    for key in ("listingFor", "bhk", "type", "budgetMin", "budgetMax", "localities", "timeline", "notes"):
        val = extracted.get(key)
        if val is not None:
            requirements[key] = val

    # Save to CRM
    base = settings.SAARTHI_API_URL.rstrip("/")
    try:
        resp = httpx.post(
            f"{base}/api/agent/lead-intake",
            json={
                "phone": lead_phone or f"ref-{phone[-6:]}",
                "name": lead_name,
                "referredBy": phone,
                "referredByName": sender_name,
                "requirements": requirements or None,
                "rawText": text,
            },
            headers=_saarthi_headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("[broker_intake] lead-intake API error: %s", exc)
        return "⚠️ Error saving lead. Try again."

    is_new: bool = data.get("isNew", True)

    # Send outbound WA to lead if we have their number and they're new
    if lead_phone and is_new:
        bits = []
        if requirements.get("bhk"):
            bits.append(f"{requirements['bhk']} BHK")
        if requirements.get("localities"):
            bits.append(", ".join(requirements["localities"]))
        if requirements.get("budgetMax"):
            b = int(requirements["budgetMax"])
            bits.append(f"budget ₹{b // 100_000}L" if b >= 100_000 else f"budget ₹{b:,}")

        ref_line = f" {sender_name} ne mujhe aapke baare mein bataya" if sender_name else ""
        req_text = " ".join(bits) if bits else "property"
        greeting = f"Hi {lead_name}!" if lead_name else "Hi!"

        outbound = (
            f"{greeting} Main Ava hun, Saarthi Real Estate se 🏠{ref_line}.\n\n"
            f"Suna hai aap {req_text} dhundh rahe hain Indore mein — "
            f"main aapki help kar sakti hun sahi property find karne mein! "
            f"Thoda aur bataiye — kya specific area ya budget mein hain? 😊"
        )
        _send_whatsapp(lead_phone, outbound)

    # Reply to broker
    name_part = f" *{lead_name}*" if lead_name else ""
    phone_part = f" ({lead_phone})" if lead_phone else " (⚠️ no phone found)"
    action = "updated" if not is_new else "added"

    reply = f"✅ Lead{name_part}{phone_part} {action}!"
    if lead_phone and is_new:
        reply += "\nI've reached out to them on WhatsApp now 📲"
    elif not lead_phone:
        reply += "\nPhone number nahi mila — bhi share karein toh main reach out kar sakti hun."
    return reply


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

    return f"✅ Got it! {title} saved. Send 2-4 photos to add them 📸"


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
