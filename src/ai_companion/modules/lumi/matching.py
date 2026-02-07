"""
Therapist matching module for Lumi onboarding.

Currently returns mock therapist data.
TODO: Replace with real matching API integration.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from ai_companion.modules.lumi.state import LumiUserState

logger = logging.getLogger(__name__)


@dataclass
class Therapist:
    """Therapist profile data."""

    id: str
    name: str
    photo_url: str
    credentials: str
    bio: str
    specializations: List[str]
    languages: List[str]
    style: str
    gender: str
    years_experience: int
    price_per_month: int


# Mock therapist data
MOCK_THERAPISTS = [
    Therapist(
        id="t1",
        name="Dr. Priya Sharma",
        photo_url="https://example.com/priya.jpg",
        credentials="Licensed Clinical Psychologist, PhD",
        bio="Dr. Priya has over 12 years of experience helping individuals navigate anxiety, depression, and life transitions. Her warm, empathetic approach creates a safe space for healing.",
        specializations=["Anxiety", "Depression", "Trauma & PTSD", "Life Transitions"],
        languages=["Hindi", "English"],
        style="Warm & nurturing",
        gender="woman",
        years_experience=12,
        price_per_month=4999,
    ),
    Therapist(
        id="t2",
        name="Dr. Arjun Menon",
        photo_url="https://example.com/arjun.jpg",
        credentials="Clinical Psychologist, MPhil",
        bio="Dr. Arjun specializes in helping high-achievers manage burnout and build sustainable success. His structured, goal-oriented approach gets results.",
        specializations=["Burnout", "Career Stress", "Self-Esteem", "ADHD"],
        languages=["English", "Malayalam", "Hindi"],
        style="Structured & direct",
        gender="man",
        years_experience=8,
        price_per_month=3999,
    ),
    Therapist(
        id="t3",
        name="Dr. Kavitha Reddy",
        photo_url="https://example.com/kavitha.jpg",
        credentials="Counseling Psychologist, MA",
        bio="Dr. Kavitha brings a holistic, culturally-aware perspective to therapy. She integrates mindfulness practices with evidence-based approaches.",
        specializations=["Relationship Issues", "Women's Mental Health", "Grief & Loss", "Cultural Identity"],
        languages=["Telugu", "English", "Hindi"],
        style="Holistic",
        gender="woman",
        years_experience=10,
        price_per_month=4499,
    ),
    Therapist(
        id="t4",
        name="Dr. Sanjay Kumar",
        photo_url="https://example.com/sanjay.jpg",
        credentials="Psychiatrist & Therapist, MD",
        bio="Dr. Sanjay provides integrated care for complex mental health needs, combining therapy with medication management when appropriate.",
        specializations=["Depression", "OCD", "Bipolar", "Medication Management"],
        languages=["Hindi", "English", "Punjabi"],
        style="Structured & direct",
        gender="man",
        years_experience=15,
        price_per_month=5999,
    ),
    Therapist(
        id="t5",
        name="Dr. Meera Iyer",
        photo_url="https://example.com/meera.jpg",
        credentials="Clinical Psychologist, PhD",
        bio="Dr. Meera creates an affirming, trauma-informed space for individuals exploring identity, relationships, and personal growth.",
        specializations=["LGBTQIA+", "Trauma & PTSD", "Identity & Purpose", "Relationship Issues"],
        languages=["English", "Tamil", "Hindi"],
        style="Queer-affirming",
        gender="woman",
        years_experience=9,
        price_per_month=4499,
    ),
]


def match_therapist(user_state: LumiUserState) -> Therapist:
    """
    Match a therapist based on user preferences and needs.

    Args:
        user_state: User's onboarding state with preferences

    Returns:
        Best matched Therapist

    TODO: Replace with real matching API call
    """
    logger.info(f"[MATCHING] Finding therapist for user {user_state.phone_number}")

    candidates = MOCK_THERAPISTS.copy()
    scores: Dict[str, int] = {t.id: 0 for t in candidates}

    # Score by language match
    if user_state.language:
        for t in candidates:
            if user_state.language in t.languages:
                scores[t.id] += 10
                logger.debug(f"[MATCHING] +10 language match: {t.name}")

    # Score by gender preference
    if user_state.therapist_gender_pref and user_state.therapist_gender_pref != "flexible":
        for t in candidates:
            if t.gender == user_state.therapist_gender_pref:
                scores[t.id] += 8
                logger.debug(f"[MATCHING] +8 gender match: {t.name}")

    # Score by concerns overlap
    if user_state.concerns:
        for t in candidates:
            overlap = set(user_state.concerns) & set(t.specializations)
            scores[t.id] += len(overlap) * 5
            if overlap:
                logger.debug(f"[MATCHING] +{len(overlap)*5} concerns match: {t.name} ({overlap})")

    # Score by style preference
    if user_state.therapist_style:
        for t in candidates:
            for style in user_state.therapist_style:
                if style.lower() in t.style.lower():
                    scores[t.id] += 6
                    logger.debug(f"[MATCHING] +6 style match: {t.name} ({style})")

    # Score for queer-affirming if flagged
    if user_state.queer_affirming_flag:
        for t in candidates:
            if "queer" in t.style.lower() or "LGBTQIA+" in t.specializations:
                scores[t.id] += 15
                logger.debug(f"[MATCHING] +15 queer-affirming: {t.name}")

    # Score for trauma-informed if flagged
    if user_state.trauma_flag:
        for t in candidates:
            if "Trauma" in t.specializations or "trauma" in t.style.lower():
                scores[t.id] += 10
                logger.debug(f"[MATCHING] +10 trauma-informed: {t.name}")

    # Find best match
    best_id = max(scores, key=scores.get)
    best_therapist = next(t for t in candidates if t.id == best_id)

    logger.info(
        f"[MATCHING] Best match: {best_therapist.name} (score: {scores[best_id]})"
    )

    return best_therapist


def get_alternative_therapists(
    user_state: LumiUserState,
    exclude_id: str,
    count: int = 2,
) -> List[Therapist]:
    """
    Get alternative therapist options.

    Args:
        user_state: User's onboarding state
        exclude_id: ID of therapist to exclude (already shown)
        count: Number of alternatives to return

    Returns:
        List of alternative Therapists
    """
    candidates = [t for t in MOCK_THERAPISTS if t.id != exclude_id]

    # Simple scoring for alternatives
    scores: Dict[str, int] = {t.id: 0 for t in candidates}

    if user_state.language:
        for t in candidates:
            if user_state.language in t.languages:
                scores[t.id] += 5

    if user_state.concerns:
        for t in candidates:
            overlap = set(user_state.concerns) & set(t.specializations)
            scores[t.id] += len(overlap) * 3

    # Sort by score and return top N
    sorted_candidates = sorted(candidates, key=lambda t: scores[t.id], reverse=True)
    return sorted_candidates[:count]


def format_therapist_card(therapist: Therapist, user_state: LumiUserState) -> str:
    """
    Format therapist info as a message card.

    Args:
        therapist: Therapist to format
        user_state: User state for personalized match reasons

    Returns:
        Formatted string for WhatsApp message
    """
    # Build match reasons based on user preferences
    match_reasons = []

    if user_state.concerns:
        matching_specs = set(user_state.concerns) & set(therapist.specializations)
        if matching_specs:
            specs_str = ", ".join(list(matching_specs)[:2])
            match_reasons.append(f"✓ Specializes in {specs_str}")

    match_reasons.append(f"✓ {therapist.style} approach")

    if user_state.language and user_state.language in therapist.languages:
        match_reasons.append(f"✓ Fluent in {user_state.language}")

    if user_state.queer_affirming_flag and "LGBTQIA+" in therapist.specializations:
        match_reasons.append("✓ Queer-affirming practice")

    if user_state.trauma_flag and "Trauma" in therapist.specializations:
        match_reasons.append("✓ Trauma-informed approach")

    match_reasons_str = "\n".join(match_reasons)

    return f"""Meet {therapist.name} 🌟

{therapist.credentials}

{therapist.bio}

---

Why I matched you:
{match_reasons_str}

---

Your Recommended Care Plan:

🧠 Weekly therapy sessions with {therapist.name}
🌱 Holistic lifestyle support (sleep, movement, nutrition, mindfulness)
💬 Access to your dedicated Care Specialist
📊 Progress tracking & personalized insights

Starting at ₹{therapist.price_per_month}/month"""


def format_alternative_card(therapist: Therapist) -> str:
    """
    Format alternative therapist as a compact card.

    Args:
        therapist: Therapist to format

    Returns:
        Formatted string
    """
    specs = ", ".join(therapist.specializations[:2])
    return f"""**{therapist.name}**
{therapist.credentials}
{therapist.bio[:100]}...

Why this match:
✓ Specializes in {specs}
✓ {therapist.style}"""
