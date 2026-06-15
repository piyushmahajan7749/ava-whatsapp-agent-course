"""Real-estate tools for the Saarthi WhatsApp agent.

Each tool receives the LangGraph RunnableConfig (injected by the runtime, never
visible to the LLM) and derives the lead's phone from thread_id — so the model
cannot hallucinate identities. All reads/writes go through the Saarthi
website's Agent API, keeping CRM rules in one place.

Tool surface (replaces upaaibot's calendar/payment/products tools):
  - update_lead_requirements: persist what the buyer wants as you learn it
  - search_properties:        find matching live listings + website links
  - schedule_property_visit:  tentative visit (server enforces never-same-day)
  - mark_lead_warm:           flag a serious buyer so a human broker calls
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ai_companion.modules.saarthi.client import (
    SaarthiAPIError,
    get_saarthi_client,
    phone_from_config,
)

logger = logging.getLogger(__name__)

_NO_PHONE = (
    "ERROR: lead phone unavailable in this session — do not retry; "
    "apologize briefly and ask the user to message again."
)


def _requirements_payload(
    listing_for: str | None,
    property_type: str | None,
    bhk: int | None,
    budget_min: float | None,
    budget_max: float | None,
    localities: list[str] | None,
    timeline: str | None = None,
    purpose: str | None = None,
    notes: str | None = None,
) -> dict:
    req: dict = {}
    if listing_for in ("SALE", "RENT"):
        req["listingFor"] = listing_for
    if property_type in ("FLAT", "HOUSE", "VILLA", "PLOT", "COMMERCIAL", "OFFICE", "SHOP", "PG"):
        req["type"] = property_type
    if bhk:
        req["bhk"] = int(bhk)
    if budget_min:
        req["budgetMin"] = float(budget_min)
    if budget_max:
        req["budgetMax"] = float(budget_max)
    if localities:
        req["localities"] = [loc.strip() for loc in localities if loc and loc.strip()]
    if timeline:
        req["timeline"] = timeline
    if purpose:
        req["purpose"] = purpose
    if notes:
        req["notes"] = notes
    return req


@tool
def update_lead_requirements(
    config: RunnableConfig,
    listing_for: str | None = None,
    property_type: str | None = None,
    bhk: int | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    localities: list[str] | None = None,
    timeline: str | None = None,
    purpose: str | None = None,
    notes: str | None = None,
    lead_name: str | None = None,
    summary: str | None = None,
    qualification_score: int | None = None,
) -> str:
    """Save what you have learned about the buyer to the CRM. Call this whenever the
    user shares NEW information (budget, BHK, locality, name, timeline, etc.).

    Args:
        listing_for: 'SALE' (buying) or 'RENT' (renting).
        property_type: One of FLAT, HOUSE, VILLA, PLOT, COMMERCIAL, OFFICE, SHOP, PG.
        bhk: Number of bedrooms wanted (e.g. 3).
        budget_min: Minimum budget in absolute rupees (75 lakh = 7500000).
        budget_max: Maximum budget in absolute rupees. Rent budgets are per month.
        localities: Preferred areas, e.g. ["Vijay Nagar", "Nipania"].
        timeline: When they want to move/buy, e.g. "1-3 months", "asap".
        purpose: "self-use" or "investment".
        notes: Any other relevant detail in one line.
        lead_name: The buyer's name if they shared it.
        summary: One-sentence running summary of who this lead is and what they want.
        qualification_score: 0-100, how serious/qualified this lead looks.
    """
    phone = phone_from_config(config)
    if not phone:
        return _NO_PHONE
    req = _requirements_payload(
        listing_for, property_type, bhk, budget_min, budget_max, localities, timeline, purpose, notes
    )
    try:
        get_saarthi_client().update_lead(
            phone, requirements=req or None, ai_summary=summary, score=qualification_score, lead_name=lead_name
        )
        return "Saved to CRM."
    except SaarthiAPIError as exc:
        return f"ERROR saving lead info (continue the conversation anyway): {exc}"


@tool
def search_properties(
    config: RunnableConfig,
    listing_for: str | None = None,
    property_type: str | None = None,
    bhk: int | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    localities: list[str] | None = None,
    limit: int = 3,
) -> str:
    """Search Saarthi's live property inventory for this buyer and record the matches
    in the CRM. Returns numbered matches WITH website links — share title, price,
    locality and the link for each in your reply. Call when you know at least:
    buy-or-rent + budget + (BHK or property type) + one locality. Also call again
    when the user asks for more/different options (already-sent properties are
    excluded automatically).

    Args:
        listing_for: 'SALE' or 'RENT'.
        property_type: FLAT, HOUSE, VILLA, PLOT, COMMERCIAL, OFFICE, SHOP or PG.
        bhk: Bedrooms wanted.
        budget_min: Minimum budget in rupees.
        budget_max: Maximum budget in rupees (rent: per month).
        localities: Preferred areas, e.g. ["Vijay Nagar"].
        limit: How many matches to return (1-5, default 3).
    """
    phone = phone_from_config(config)
    if not phone:
        return _NO_PHONE
    req = _requirements_payload(listing_for, property_type, bhk, budget_min, budget_max, localities)
    try:
        data = get_saarthi_client().search_properties(phone, req, limit=max(1, min(int(limit or 3), 5)))
    except SaarthiAPIError as exc:
        return f"ERROR searching properties: {exc}"

    matches = data.get("matches", [])
    if not matches:
        return (
            "NO new matching properties right now. Tell the user honestly that nothing matches "
            "their exact requirement yet, their requirement is saved, and you'll send options "
            "as soon as something comes in. Optionally ask if they can flex budget or locality."
        )
    lines = [f"FOUND {len(matches)} matching properties (already recorded in CRM — share these with links):"]
    for i, m in enumerate(matches, 1):
        bits = [m.get("priceLabel", "Price on request")]
        if m.get("bhk"):
            bits.append(f"{m['bhk']} BHK")
        if m.get("area"):
            bits.append(m["area"])
        if m.get("locality"):
            bits.append(m["locality"])
        lines.append(f"{i}. {m.get('title')} — {' · '.join(bits)}")
        if m.get("reasons"):
            lines.append(f"   Why: {', '.join(m['reasons'][:2])}")
        lines.append(f"   Link: {m.get('url')}")
        lines.append(f"   (property_id: {m.get('id')})")
    lines.append("Use the property_id values when calling schedule_property_visit.")
    return "\n".join(lines)


@tool
def schedule_property_visit(
    property_ids: list[str],
    config: RunnableConfig,
    preferred_datetime_iso: str | None = None,
    availability_text: str | None = None,
) -> str:
    """Schedule a TENTATIVE site visit once the buyer likes specific properties and
    has shared their availability. NEVER promise same-day visits — the earliest
    slot is tomorrow (the server enforces this too). Our team confirms the final
    time with the listing broker, so always present the slot as tentative.

    Args:
        property_ids: property_id values (from search_properties results) the buyer wants to visit.
        preferred_datetime_iso: Concrete tentative slot in ISO-8601 with IST offset,
            e.g. 2026-06-13T17:00:00+05:30. Must be TOMORROW OR LATER. Omit if unsure.
        availability_text: The buyer's availability in their own words, e.g. "Saturday evening".
    """
    phone = phone_from_config(config)
    if not phone:
        return _NO_PHONE
    try:
        data = get_saarthi_client().schedule_visit(
            phone,
            property_ids=property_ids,
            slot_iso=preferred_datetime_iso,
            availability_text=availability_text,
        )
    except SaarthiAPIError as exc:
        return f"ERROR scheduling the visit: {exc}"
    titles = ", ".join(data.get("propertyTitles", [])) or "the selected property"
    return (
        f"VISIT TENTATIVELY SCHEDULED for {data.get('slotText')} — properties: {titles}. "
        f"Our team has been alerted and will confirm the final time with the property broker. "
        f"Tell the buyer this slot is tentative and the team will confirm shortly."
    )


@tool
def mark_lead_warm(reason: str, config: RunnableConfig) -> str:
    """Flag this buyer as WARM so a human broker calls them. Use when the buyer is
    clearly serious (asks to talk to someone, ready to finalize, urgent timeline)
    but a visit is not scheduled yet. Do NOT use for casual browsers.

    Args:
        reason: One line on why this lead is warm, e.g. "Wants to close within 2 weeks".
    """
    phone = phone_from_config(config)
    if not phone:
        return _NO_PHONE
    try:
        data = get_saarthi_client().update_lead(phone, ai_summary=f"WARM: {reason}", mark_warm=True)
    except SaarthiAPIError as exc:
        return f"ERROR marking lead warm: {exc}"
    if data.get("brokerAlerted"):
        return (
            "Lead marked WARM — a broker has been alerted on WhatsApp and will call them. "
            "Tell the buyer someone from our team will call shortly."
        )
    return "Lead marked WARM in the CRM. Tell the buyer our team will reach out shortly."


def get_saarthi_tools():
    """All tools bound to the conversation model on the saarthi branch."""
    return [update_lead_requirements, search_properties, schedule_property_visit, mark_lead_warm]
