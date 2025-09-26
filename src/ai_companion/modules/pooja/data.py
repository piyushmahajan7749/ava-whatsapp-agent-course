from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Pricing:
    single: int
    couple: int
    family: int
    consultation: int


@dataclass(frozen=True)
class Benefits:
    english: List[str]
    hindi: List[str]


@dataclass(frozen=True)
class Process:
    english: List[str]
    hindi: List[str]


@dataclass(frozen=True)
class WhenToPerform:
    english: str
    hindi: str


@dataclass(frozen=True)
class Pooja:
    id: str
    title: str
    englishDesc: str
    hindiDesc: str
    duration: str
    benefits: Benefits
    process: Process
    whenToPerform: WhenToPerform
    pricing: Pricing
    image: str


# Minimal schema carrying only essential fields for context. Populate incrementally.
NAVRATRI_POOJAS: List[Pooja] = [
    Pooja(
        id="bagalamukhi",
        title="Maa Bagalamukhi Maha Anushthan – Bagalamukhi Mandir",
        englishDesc=(
            "This powerful tantric ritual is dedicated to Goddess Bagalamukhi, revered for protection, victory in conflicts, and removal of negativity."
        ),
        hindiDesc=(
            "यह शक्तिशाली तांत्रिक अनुष्ठान माँ बगलामुखी को समर्पित है, जो शत्रु बाधा से रक्षा और विजय के लिए प्रसिद्ध हैं।"
        ),
        duration="16 hours",
        benefits=Benefits(
            english=[
                "Protects from negative energies",
                "Success in legal matters",
                "Removes obstacles",
            ],
            hindi=[
                "नकारात्मक ऊर्जा से रक्षा",
                "कानूनी मामलों में सफलता",
                "बाधाएँ दूर करता है",
            ],
        ),
        process=Process(
            english=[
                "Invocation of Maa Bagalamukhi",
                "Havan with tantric offerings",
                "Final aarti and blessings",
            ],
            hindi=[
                "मां बगलामुखी का आह्वान",
                "तांत्रिक सामग्री से हवन",
                "अंतिम आरती और आशीर्वाद",
            ],
        ),
        whenToPerform=WhenToPerform(
            english="Effective on Tuesdays/Thursdays and during Navratri",
            hindi="मंगल/गुरुवार तथा नवरात्रि में विशेष प्रभावी",
        ),
        pricing=Pricing(single=5100, couple=5501, family=6001, consultation=2100),
        image="/pooja-baglamukhi.webp",
    ),
    Pooja(
        id="durgaSaptashati",
        title="Durga Saptashati Path – Ujjain Temples",
        englishDesc=(
            "Nine-day chanting invoking the 9 forms of Goddess Durga for peace, protection, and strength."
        ),
        hindiDesc=(
            "नवरात्रि के नौ दिनों का पाठ जो देवी के नौ रूपों का आह्वान करता है—शांति, सुरक्षा और शक्ति के लिए।"
        ),
        duration="1-2 hours daily for 9 days",
        benefits=Benefits(
            english=["Removes fear", "Overcomes obstacles", "Spiritual strength"],
            hindi=["भय दूर करता है", "बाधाएँ हटाता है", "आध्यात्मिक शक्ति"],
        ),
        process=Process(
            english=["Daily sankalpa", "Chapter recitation", "Aarti"],
            hindi=["दैनिक संकल्प", "अध्याय पाठ", "आरती"],
        ),
        whenToPerform=WhenToPerform(
            english="Nine days of Navratri",
            hindi="नवरात्रि के नौ दिन",
        ),
        pricing=Pricing(single=1101, couple=1701, family=2201, consultation=2100),
        image="/pooja-tantra.webp",
    ),
]


AMAVASYA_POOJAS: List[Pooja] = [
    Pooja(
        id="pitraDosh",
        title="Pitra Dosh Nivaran Pooja – Siddha Nath Mandir",
        englishDesc="Pacifies ancestors and removes effects of unresolved ancestral karma.",
        hindiDesc="पितरों की शांति और पितृ दोष से मुक्ति के लिए।",
        duration="2-3 hours",
        benefits=Benefits(
            english=["Resolves family problems", "Improves health", "Financial stability"],
            hindi=["परिवार की समस्याएँ हल", "स्वास्थ्य में सुधार", "आर्थिक स्थिरता"],
        ),
        process=Process(
            english=["Tila tarpan", "Pinda daan", "Final prayers"],
            hindi=["तिल तर्पण", "पिंड दान", "अंतिम प्रार्थनाएँ"],
        ),
        whenToPerform=WhenToPerform(
            english="Amavasya, Shraddha, eclipses",
            hindi="अमावस्या, श्राद्ध, ग्रहण",
        ),
        pricing=Pricing(single=5100, couple=1201, family=1801, consultation=2100),
        image="/pooja-ganga.webp",
    ),
]


REGULAR_POOJAS: List[Pooja] = [
    Pooja(
        id="mahamrityunjaya",
        title="Mahamrityunjaya Pooja",
        englishDesc="Protection from untimely death, accidents, and serious health issues.",
        hindiDesc="अकाल मृत्यु, दुर्घटनाओं और गंभीर स्वास्थ्य समस्याओं से रक्षा।",
        duration="2-3 hours",
        benefits=Benefits(
            english=["Longevity", "Good health", "Spiritual strength"],
            hindi=["दीर्घायु", "अच्छा स्वास्थ्य", "आध्यात्मिक शक्ति"],
        ),
        process=Process(
            english=["Sankalpa", "Mantra japa", "Havan"],
            hindi=["संकल्प", "मंत्र जाप", "हवन"],
        ),
        whenToPerform=WhenToPerform(
            english="Any auspicious day",
            hindi="किसी भी शुभ दिन",
        ),
        pricing=Pricing(single=5100, couple=1201, family=1801, consultation=2100),
        image="/pooja-ganga.webp",
    )
]


ALL_POOJAS: List[Pooja] = [*NAVRATRI_POOJAS, *AMAVASYA_POOJAS, *REGULAR_POOJAS]


NAME_INDEX: Dict[str, Pooja] = {p.id.lower(): p for p in ALL_POOJAS}


ALIAS_INDEX: Dict[str, str] = {
    # common spellings / aliases for matching
    "baglamukhi": "bagalamukhi",
    "bagla mukhi": "bagalamukhi",
    "mahamrityunjaya": "mahamrityunjaya",
    "maha mrityunjaya": "mahamrityunjaya",
    "pitra dosh": "pitraDosh",
    "pitra dosh nivaran": "pitraDosh",
    "durga saptashati": "durgaSaptashati",
}


def find_pooja_by_text(text: str) -> Optional[Pooja]:
    """Best-effort lookup for a pooja mentioned in free-form user text.

    Performs simple case-insensitive substring matching against ids, titles, and aliases.
    """
    if not text:
        return None
    t = text.lower()

    # alias pass
    for alias, canonical in ALIAS_INDEX.items():
        if alias in t:
            # alias may map to canonical id or direct id depending on capitalization
            pooja = NAME_INDEX.get(canonical.lower()) or NAME_INDEX.get(canonical)
            if pooja:
                return pooja

    # id or title pass
    for p in ALL_POOJAS:
        if p.id.lower() in t or p.title.lower() in t:
            return p

    return None


def format_pooja_context(pooja: Pooja) -> str:
    """Compact, bilingual context string for prompt injection."""
    return (
        f"Suggested Pooja: {pooja.title}\n"
        f"English: {pooja.englishDesc}\n"
        f"Hindi: {pooja.hindiDesc}\n"
        f"Duration: {pooja.duration}\n"
        f"When to perform: {pooja.whenToPerform.english} / {pooja.whenToPerform.hindi}\n"
        f"Pricing (INR): single {pooja.pricing.single}, couple {pooja.pricing.couple}, family {pooja.pricing.family}, consult {pooja.pricing.consultation}"
    )


