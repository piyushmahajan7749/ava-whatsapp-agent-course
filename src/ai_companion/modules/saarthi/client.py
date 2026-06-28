"""HTTP client for the Saarthi website's Agent API.

The Next.js app (saarthi-website) is the single source of truth for the CRM:
leads, properties, matches, visits, statuses, broker/coordinator alerts. This
bot is the conversation brain; every tool call goes through these endpoints so
business rules (matching scores, status transitions, the never-same-day visit
rule) live in exactly one place and the admin CRM reflects the conversation
live.

Auth: `Authorization: Bearer <SAARTHI_API_KEY>` (set the same value as the
website's AGENT_API_KEY env var).

The lead's identity is NEVER an LLM-provided argument: tools read the phone
from the LangGraph config (thread_id == WhatsApp number), which the runtime
injects — hallucination-proof.
"""

import logging
from typing import Any

import httpx

from ai_companion.settings import settings

logger = logging.getLogger(__name__)


def phone_from_config(config: Any) -> str | None:
    """thread_id is the WhatsApp number (set by the webhook). Returns digits or None."""
    try:
        thread_id = (config or {}).get("configurable", {}).get("thread_id")
    except AttributeError:
        thread_id = None
    if not thread_id:
        return None
    digits = "".join(ch for ch in str(thread_id) if ch.isdigit())
    return digits if len(digits) >= 10 else None


class SaarthiAPIError(Exception):
    """Raised when the Agent API rejects or fails a request."""


class SaarthiClient:
    def __init__(self) -> None:
        self.base_url = (settings.SAARTHI_API_URL or "").rstrip("/")
        self.api_key = settings.SAARTHI_API_KEY

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise SaarthiAPIError("Saarthi API not configured (set SAARTHI_API_URL and SAARTHI_API_KEY).")
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.HTTPError as exc:
            logger.error("Saarthi API unreachable: %s %s -> %s", path, payload.get("phone"), exc)
            raise SaarthiAPIError(f"Saarthi API unreachable: {exc}") from exc
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("error", "")
            except Exception:
                detail = resp.text[:200]
            logger.error("Saarthi API %s -> %s: %s", path, resp.status_code, detail)
            raise SaarthiAPIError(f"Saarthi API {path} failed ({resp.status_code}): {detail}")
        return resp.json()

    # ---- endpoints --------------------------------------------------------

    def get_context(self, phone: str, profile_name: str | None = None, inbound_text: str | None = None) -> dict:
        """Ensure the lead exists, record the inbound message, return CRM context."""
        return self._post(
            "/api/agent/context",
            {"phone": phone, "profileName": profile_name, "inboundText": inbound_text},
        )

    def search_properties(self, phone: str, requirements: dict[str, Any], limit: int = 3) -> dict:
        """Persist requirements, find + record top matches, return them with URLs."""
        return self._post("/api/agent/search", {"phone": phone, "requirements": requirements, "limit": limit})

    def update_lead(
        self,
        phone: str,
        requirements: dict[str, Any] | None = None,
        ai_summary: str | None = None,
        score: int | None = None,
        lead_name: str | None = None,
        mark_warm: bool = False,
        mark_cold: bool = False,
    ) -> dict:
        payload: dict[str, Any] = {"phone": phone, "markWarm": mark_warm, "markCold": mark_cold}
        if requirements:
            payload["requirements"] = requirements
        if ai_summary:
            payload["aiSummary"] = ai_summary
        if score is not None:
            payload["score"] = score
        if lead_name:
            payload["leadName"] = lead_name
        return self._post("/api/agent/update-lead", payload)

    def schedule_visit(
        self,
        phone: str,
        property_ids: list[str] | None = None,
        slot_iso: str | None = None,
        availability_text: str | None = None,
    ) -> dict:
        """Tentative visit. Server clamps to tomorrow-or-later and alerts the coordinator."""
        return self._post(
            "/api/agent/visit",
            {"phone": phone, "propertyIds": property_ids or [], "slotISO": slot_iso, "availabilityText": availability_text},
        )

    def record_outbound(self, phone: str, text: str) -> dict:
        """Mirror a bot reply into the CRM transcript (delivery happens here, in cx-agent)."""
        return self._post("/api/agent/outbound", {"phone": phone, "text": text})


_client: SaarthiClient | None = None


def get_saarthi_client() -> SaarthiClient:
    global _client
    if _client is None:
        _client = SaarthiClient()
    return _client


def format_lead_context(ctx: dict) -> str:
    """Compact, prompt-ready summary of the CRM context returned by /api/agent/context."""
    lines: list[str] = []
    name = ctx.get("name")
    lines.append(f"- Lead: {name or 'name unknown'} | status: {ctx.get('status')} | score: {ctx.get('score')}/100")

    # Durable transcript from the CRM — the source of truth for what's been said,
    # so the bot never re-asks even if its short-term memory was reset.
    transcript = ctx.get("transcript") or []
    if transcript:
        lines.append("- Conversation so far (already said — do NOT ask any of this again, continue from here):")
        for m in transcript[-12:]:
            who = "Buyer" if m.get("role") == "user" else "You"
            text = str(m.get("content", "")).replace("\n", " ").strip()[:220]
            if text:
                lines.append(f"    {who}: {text}")

    req = ctx.get("requirements") or {}
    if req:
        bits = []
        if req.get("listingFor"):
            bits.append("wants to " + ("RENT" if req["listingFor"] == "RENT" else "BUY"))
        if req.get("bhk"):
            bits.append(f"{req['bhk']} BHK")
        if req.get("type"):
            bits.append(str(req["type"]).lower())
        if req.get("budgetMax"):
            bits.append(f"budget up to ₹{int(req['budgetMax']):,}")
        if req.get("localities"):
            bits.append("in " + ", ".join(req["localities"]))
        if req.get("timeline"):
            bits.append(f"timeline: {req['timeline']}")
        lines.append(f"- Known requirements: {'; '.join(bits) if bits else 'none yet'}")
    else:
        lines.append("- Known requirements: none yet (start qualifying)")

    if ctx.get("aiSummary"):
        lines.append(f"- Summary so far: {ctx['aiSummary']}")

    matches = ctx.get("sentMatches") or []
    if matches:
        lines.append(f"- Properties ALREADY sent ({len(matches)}) — don't resend, refer by name:")
        for m in matches[:6]:
            lines.append(f"    • {m.get('title')} ({m.get('priceLabel')}, {m.get('locality')}) [property_id: {m.get('id')}] {m.get('url')}")
    else:
        lines.append("- No properties sent yet.")

    visit = ctx.get("openVisit")
    if visit:
        lines.append(f"- Open visit: {visit.get('status')} for {visit.get('scheduledFor') or 'time TBD'} — handle changes via schedule_property_visit.")

    if ctx.get("tomorrowISO"):
        lines.append(f"- Today is {ctx.get('todayLabel')}. EARLIEST allowed visit slot: {ctx['tomorrowISO']} (never today).")
    return "\n".join(lines)
