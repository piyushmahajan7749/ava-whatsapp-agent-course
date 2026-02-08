"""
Expert matching module for Lumi onboarding.

Loads real expert data from experts_data.json and uses a multi-factor
scoring algorithm to find the best therapist/coach matches for users.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ai_companion.modules.lumi.state import LumiUserState

logger = logging.getLogger(__name__)

# Load expert data from JSON
_DATA_PATH = Path(__file__).parent / "experts_data.json"

with open(_DATA_PATH) as f:
    _EXPERTS_DATA = json.load(f)

# Concern aliases: maps keyword variants to normalized concern keys
CONCERN_ALIASES: Dict[str, List[str]] = _EXPERTS_DATA["concern_aliases"]

# UI label → normalized key mapping
CONCERN_MAP: Dict[str, str] = _EXPERTS_DATA["concern_map"]

# Pricing data
PRICING: dict = _EXPERTS_DATA["pricing"]

# Severity ordering for comparison
SEVERITY_ORDER = {"mild": 1, "moderate": 2, "severe": 3, "all": 3}


@dataclass
class Expert:
    """Expert profile data."""

    id: str
    name: str
    expert_type: str  # clinical_psychologist, counselling_psychologist, yms_coach, nutrition_coach
    gender: str
    location: str
    years_experience: Optional[int]
    tier: Optional[str]  # early_career, developing, established, senior
    max_severity: str  # mild, moderate, severe, all
    languages: List[str]
    concerns: List[str]  # normalized concern keys
    queer_affirming: bool
    price_per_session: int
    client_age_min: Optional[int]
    client_age_max: Optional[int]
    status: str
    slots_available: bool
    bio: str


# Keep Therapist as an alias for backward compatibility
Therapist = Expert


def _load_experts() -> List[Expert]:
    """Load experts from JSON data."""
    experts = []
    for data in _EXPERTS_DATA["experts"]:
        experts.append(
            Expert(
                id=data["id"],
                name=data["name"],
                expert_type=data["expert_type"],
                gender=data["gender"],
                location=data["location"],
                years_experience=data.get("years_experience"),
                tier=data.get("tier"),
                max_severity=data.get("max_severity", "moderate"),
                languages=data.get("languages", []),
                concerns=data.get("concerns", []),
                queer_affirming=data.get("queer_affirming", False),
                price_per_session=data.get("price_per_session", 0),
                client_age_min=data.get("client_age_min"),
                client_age_max=data.get("client_age_max"),
                status=data.get("status", "active"),
                slots_available=data.get("slots_available", False),
                bio=data.get("bio", ""),
            )
        )
    return experts


ALL_EXPERTS = _load_experts()


def normalize_concern(raw: str) -> Optional[str]:
    """
    Normalize a user concern string to a canonical concern key.

    Handles both UI label strings ("Anxiety", "Grief & Loss") and
    keyword-detected strings ("anxiety", "burnout", "grief").
    """
    # Direct match in concern map (UI labels)
    if raw in CONCERN_MAP:
        return CONCERN_MAP[raw]

    raw_lower = raw.lower().strip()

    # Direct match on normalized key
    if raw_lower in CONCERN_ALIASES:
        return raw_lower

    # Search through aliases
    for key, aliases in CONCERN_ALIASES.items():
        if raw_lower in aliases or raw_lower == key:
            return key

    return raw_lower  # fallback: return as-is


def _get_therapists(include_unavailable: bool = False) -> List[Expert]:
    """Get active therapists (clinical + counselling psychologists)."""
    return [
        e
        for e in ALL_EXPERTS
        if e.status == "active"
        and e.expert_type in ("clinical_psychologist", "counselling_psychologist")
        and (include_unavailable or e.slots_available)
    ]


def _get_yms_coaches() -> List[Expert]:
    """Get active YMS coaches with available slots."""
    return [
        e
        for e in ALL_EXPERTS
        if e.status == "active" and e.expert_type == "yms_coach" and e.slots_available
    ]


def _get_nutrition_coaches() -> List[Expert]:
    """Get active nutrition coaches with available slots."""
    return [
        e
        for e in ALL_EXPERTS
        if e.status == "active"
        and e.expert_type == "nutrition_coach"
        and e.slots_available
    ]


def _user_severity(user_state: LumiUserState) -> str:
    """
    Infer the user's severity level from their state.

    Uses flags, concerns, and other signals to estimate severity.
    """
    if user_state.complex_psychiatric_flag:
        return "severe"
    if user_state.trauma_flag:
        return "severe"

    severe_concerns = {"trauma", "addiction", "bipolar", "ocd", "eating_disorders"}
    user_concerns = {normalize_concern(c) for c in user_state.concerns}
    if user_concerns & severe_concerns:
        return "moderate"

    mild_concerns = {"stress", "sleep", "career", "self_esteem"}
    if user_concerns and user_concerns <= mild_concerns:
        return "mild"

    return "moderate"  # default


def match_therapist(user_state: LumiUserState) -> Expert:
    """
    Match a therapist based on user preferences and needs.

    Scoring factors (weights):
    - Concern overlap:     5 pts per match (max ~100)
    - Language match:      15 pts
    - Gender preference:   12 pts
    - Severity fit:        10-20 pts
    - Queer-affirming:     20 pts (when needed)
    - Trauma-informed:     15 pts (when flagged)
    - Age compatibility:   8 pts
    - Slot availability:   10 pts (bonus)
    - Style preference:    8 pts per match
    """
    logger.info(f"[MATCHING] Finding therapist for user {user_state.phone_number}")

    candidates = _get_therapists(include_unavailable=True)
    if not candidates:
        logger.warning("[MATCHING] No candidates available, using all experts")
        candidates = [
            e
            for e in ALL_EXPERTS
            if e.expert_type in ("clinical_psychologist", "counselling_psychologist")
        ]

    scores: Dict[str, float] = {t.id: 0 for t in candidates}
    reasons: Dict[str, List[str]] = {t.id: [] for t in candidates}

    # Normalize user concerns
    user_concerns = {normalize_concern(c) for c in user_state.concerns}
    user_severity = _user_severity(user_state)

    for t in candidates:
        # --- Concern overlap (5 pts each) ---
        if user_concerns:
            expert_concerns = set(t.concerns)
            overlap = user_concerns & expert_concerns
            concern_score = len(overlap) * 5
            scores[t.id] += concern_score
            if overlap:
                reasons[t.id].append(f"concerns:{','.join(sorted(overlap))}")
                logger.debug(
                    f"[MATCHING] +{concern_score} concerns: {t.name} ({overlap})"
                )

        # --- Language match (15 pts) ---
        if user_state.language:
            user_lang = user_state.language.strip().capitalize()
            expert_langs_normalized = [l.strip().capitalize() for l in t.languages]
            if user_lang in expert_langs_normalized:
                scores[t.id] += 15
                reasons[t.id].append(f"language:{user_lang}")
                logger.debug(f"[MATCHING] +15 language: {t.name}")

        # --- Gender preference (12 pts) ---
        if (
            user_state.therapist_gender_pref
            and user_state.therapist_gender_pref != "flexible"
        ):
            if t.gender == user_state.therapist_gender_pref:
                scores[t.id] += 12
                reasons[t.id].append("gender_match")
                logger.debug(f"[MATCHING] +12 gender: {t.name}")

        # --- Severity fit (10-20 pts) ---
        expert_sev = SEVERITY_ORDER.get(t.max_severity, 2)
        user_sev = SEVERITY_ORDER.get(user_severity, 2)

        if expert_sev >= user_sev:
            # Expert can handle the user's severity level
            if expert_sev == user_sev:
                scores[t.id] += 20  # exact match is best
                reasons[t.id].append("severity_exact")
            else:
                scores[t.id] += 10  # can handle but overqualified
                reasons[t.id].append("severity_capable")
            logger.debug(
                f"[MATCHING] +{20 if expert_sev == user_sev else 10} severity: {t.name}"
            )
        else:
            # Expert can't handle this severity - penalize heavily
            scores[t.id] -= 30
            logger.debug(f"[MATCHING] -30 severity mismatch: {t.name}")

        # --- Queer-affirming (20 pts when needed) ---
        if user_state.queer_affirming_flag:
            if t.queer_affirming or "lgbtq" in t.concerns:
                scores[t.id] += 20
                reasons[t.id].append("queer_affirming")
                logger.debug(f"[MATCHING] +20 queer-affirming: {t.name}")

        # --- Trauma-informed (15 pts when flagged) ---
        if user_state.trauma_flag:
            if "trauma" in t.concerns:
                scores[t.id] += 15
                reasons[t.id].append("trauma_informed")
                logger.debug(f"[MATCHING] +15 trauma: {t.name}")

        # --- Age compatibility (8 pts) ---
        if user_state.age:
            age_ok = True
            if t.client_age_min is not None and user_state.age < t.client_age_min:
                age_ok = False
            if t.client_age_max is not None and user_state.age > t.client_age_max:
                age_ok = False
            if age_ok:
                scores[t.id] += 8
                reasons[t.id].append("age_fit")
                logger.debug(f"[MATCHING] +8 age fit: {t.name}")
            else:
                scores[t.id] -= 20  # outside age range is a hard penalty
                logger.debug(f"[MATCHING] -20 age mismatch: {t.name}")

        # --- Slot availability (10 pts bonus) ---
        if t.slots_available:
            scores[t.id] += 10
            logger.debug(f"[MATCHING] +10 slots available: {t.name}")

        # --- Style preference (8 pts per match) ---
        if user_state.therapist_style:
            for style in user_state.therapist_style:
                style_lower = style.lower()
                if "queer" in style_lower and (
                    t.queer_affirming or "lgbtq" in t.concerns
                ):
                    scores[t.id] += 8
                    reasons[t.id].append("style:queer")
                elif "trauma" in style_lower and "trauma" in t.concerns:
                    scores[t.id] += 8
                    reasons[t.id].append("style:trauma")
                elif "warm" in style_lower and t.expert_type == "counselling_psychologist":
                    scores[t.id] += 8
                    reasons[t.id].append("style:warm")
                elif "structured" in style_lower and t.expert_type == "clinical_psychologist":
                    scores[t.id] += 8
                    reasons[t.id].append("style:structured")

    # Find best match
    best_id = max(scores, key=scores.get)
    best = next(t for t in candidates if t.id == best_id)

    logger.info(
        f"[MATCHING] Best match: {best.name} "
        f"(score: {scores[best_id]}, reasons: {reasons[best_id]})"
    )

    # Log top 3 for debugging
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
    for eid, score in sorted_scores:
        expert = next(t for t in candidates if t.id == eid)
        logger.info(
            f"[MATCHING]   #{sorted_scores.index((eid, score))+1} {expert.name}: "
            f"{score} ({reasons[eid]})"
        )

    return best


def get_alternative_therapists(
    user_state: LumiUserState,
    exclude_id: str,
    count: int = 2,
) -> List[Expert]:
    """
    Get alternative therapist options, excluding the primary match.

    Uses the same scoring logic but returns the next-best candidates.
    """
    candidates = [
        e
        for e in _get_therapists(include_unavailable=True)
        if e.id != exclude_id
    ]

    if not candidates:
        return []

    user_concerns = {normalize_concern(c) for c in user_state.concerns}
    scores: Dict[str, float] = {t.id: 0 for t in candidates}

    for t in candidates:
        if user_concerns:
            overlap = user_concerns & set(t.concerns)
            scores[t.id] += len(overlap) * 5

        if user_state.language:
            user_lang = user_state.language.strip().capitalize()
            if user_lang in [l.strip().capitalize() for l in t.languages]:
                scores[t.id] += 15

        if (
            user_state.therapist_gender_pref
            and user_state.therapist_gender_pref != "flexible"
        ):
            if t.gender == user_state.therapist_gender_pref:
                scores[t.id] += 12

        if user_state.queer_affirming_flag and (
            t.queer_affirming or "lgbtq" in t.concerns
        ):
            scores[t.id] += 20

        if user_state.trauma_flag and "trauma" in t.concerns:
            scores[t.id] += 15

        if t.slots_available:
            scores[t.id] += 10

    sorted_candidates = sorted(candidates, key=lambda t: scores[t.id], reverse=True)
    return sorted_candidates[:count]


def get_recommended_plan(user_state: LumiUserState, therapist: Expert) -> dict:
    """
    Get the recommended care plan and pricing based on user preferences and matched therapist.

    Returns a dict with plan details and pricing.
    """
    tier = therapist.tier or "developing"

    if user_state.care_preference == "full_care":
        deep_care = PRICING["deep_care_12_week"].get(tier, {})
        return {
            "plan_type": "deep_care_12_week",
            "plan_name": "12-Week Deep Care Plan",
            "total_price": deep_care.get("total_price"),
            "per_month": deep_care.get("per_month"),
            "savings_pct": deep_care.get("savings_pct"),
            "includes": PRICING["deep_care_12_week"].get("includes", ""),
            "therapist_tier": tier,
        }

    if user_state.care_preference == "just_therapy":
        tier_pricing = PRICING["therapy_single_session"].get(tier, {})
        bundle_pricing = PRICING["therapy_bundle_4"].get(tier, {})
        return {
            "plan_type": "therapy_only",
            "plan_name": "Therapy Sessions",
            "single_session_price": tier_pricing.get("discounted_price"),
            "bundle_4_price": bundle_pricing.get("discounted_price"),
            "bundle_4_savings": bundle_pricing.get("savings_pct"),
            "therapist_tier": tier,
        }

    # Default / "not_sure" - show single session price
    tier_pricing = PRICING["therapy_single_session"].get(tier, {})
    return {
        "plan_type": "single_session",
        "plan_name": "Single Session",
        "price": tier_pricing.get("discounted_price", therapist.price_per_session),
        "therapist_tier": tier,
    }


def format_therapist_card(therapist: Expert, user_state: LumiUserState) -> str:
    """
    Format therapist info as a message card for WhatsApp.
    """
    match_reasons = []

    # Concern matches
    if user_state.concerns:
        user_concerns = {normalize_concern(c) for c in user_state.concerns}
        matching_concerns = user_concerns & set(therapist.concerns)
        if matching_concerns:
            # Map back to human-readable labels
            reverse_map = {v: k for k, v in CONCERN_MAP.items()}
            labels = [
                reverse_map.get(c, c.replace("_", " ").title())
                for c in sorted(matching_concerns)
            ][:3]
            match_reasons.append(f"Specializes in {', '.join(labels)}")

    # Expert type
    type_labels = {
        "clinical_psychologist": "Clinical Psychologist",
        "counselling_psychologist": "Counselling Psychologist",
    }
    type_label = type_labels.get(therapist.expert_type, therapist.expert_type)
    match_reasons.append(f"{type_label} with {therapist.years_experience or 'several'} years experience")

    # Language
    if user_state.language:
        user_lang = user_state.language.strip().capitalize()
        if user_lang in [l.strip().capitalize() for l in therapist.languages]:
            match_reasons.append(f"Fluent in {user_lang}")

    # Queer-affirming
    if user_state.queer_affirming_flag and (
        therapist.queer_affirming or "lgbtq" in therapist.concerns
    ):
        match_reasons.append("Queer-affirming practice")

    # Trauma
    if user_state.trauma_flag and "trauma" in therapist.concerns:
        match_reasons.append("Trauma-informed approach")

    match_reasons_str = "\n".join(f"- {r}" for r in match_reasons)

    # Get pricing
    plan = get_recommended_plan(user_state, therapist)

    if plan["plan_type"] == "deep_care_12_week":
        pricing_line = f"12-Week Deep Care Plan starting at Rs.{plan['per_month']}/month"
    elif plan["plan_type"] == "therapy_only" and plan.get("bundle_4_price"):
        pricing_line = (
            f"Rs.{plan['single_session_price']}/session | "
            f"4-session bundle: Rs.{plan['bundle_4_price']} ({plan['bundle_4_savings']}% off)"
        )
    else:
        pricing_line = f"Starting at Rs.{plan.get('price', therapist.price_per_session)}/session"

    return f"""Meet {therapist.name}

{therapist.bio}

Why I matched you:
{match_reasons_str}

Your Recommended Care:
- Weekly therapy sessions with {therapist.name}
- Holistic lifestyle support (sleep, movement, nutrition, mindfulness)
- Access to your dedicated Care Specialist
- Progress tracking & personalized insights

{pricing_line}"""


def format_alternative_card(therapist: Expert) -> str:
    """
    Format alternative therapist as a compact card.
    """
    type_labels = {
        "clinical_psychologist": "Clinical Psychologist",
        "counselling_psychologist": "Counselling Psychologist",
    }
    type_label = type_labels.get(therapist.expert_type, therapist.expert_type)
    langs = ", ".join(therapist.languages[:3])

    return f"""{therapist.name}
{type_label} | {therapist.years_experience or 'Several'} yrs exp
{therapist.bio[:120]}...
Languages: {langs}
Rs.{therapist.price_per_session}/session"""
