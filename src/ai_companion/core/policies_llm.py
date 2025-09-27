from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from ai_companion.graph.utils.helpers import get_small_chat_model


logger = logging.getLogger(__name__)


class PolicyIntent(BaseModel):
    intent: str = Field(
        description=(
            "One of: 'none', 'enquiry', 'consult_info', 'consult_payment_verified',"
            " 'consult_slot_confirmed', 'kalawa_info', 'kalawa_payment_confirmed', 'kalawa_dispatch'"
        )
    )
    first_name: Optional[str] = Field(default=None, description="User first name if known")
    date: Optional[str] = Field(default=None, description="Date string for appointment if applicable")
    time: Optional[str] = Field(default=None, description="Time string for appointment if applicable")
    tracking: Optional[str] = Field(default=None, description="Tracking number or URL if applicable")


LLM_POLICY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a deterministic classifier for a WhatsApp sales/support agent named UMA.\n"
                "Given the recent conversation messages, decide which policy/template to use.\n"
                "Return a strict JSON with fields defined by the schema.\n\n"
                "Valid intents:\n"
                "- enquiry: first-contact interest in services.\n"
                "- consult_info: user expresses desire to book consultation / call.\n"
                "- consult_payment_verified: user likely shared payment proof (image or mentions payment).\n"
                "- consult_slot_confirmed: user says 'ASAP' or no preference for time.\n"
                "- kalawa_info: user asks about/buys Kalawa.\n"
                "- kalawa_payment_confirmed: kalawa payment proof provided.\n"
                "- kalawa_dispatch: tracking number/link provided.\n"
                "- none: if nothing above applies.\n\n"
                "Notes:\n"
                "- Messages may include an image analysis line like '[Image Analysis: ...]'.\n"
                "- Be conservative; choose 'none' if uncertain.\n"
            ),
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)


@dataclass
class PolicyResult:
    text: str
    meta: Dict[str, Any] | None = None


def _render_template(intent: str, slots: Dict[str, Any]) -> str:
    first_name = slots.get("first_name") or "ji"
    if intent == "enquiry":
        return (
            "Namaste 🙏\n"
            "Main UMA hoon, UPAAI par apki customer service agent.\n"
            "Aap UPAAI pe directly Guru Maa se sampark kar sakte hain in 3 services ke dwara:\n"
            "👉 Consultation booking (Guru Maa se phone par baat)\n"
            "👉 Siddha Products (Kalawa, Yantra etc.)\n"
            "👉 Special Pooja booking (Mandir mein Anushthaan)\n"
            "Please batayein aap kis service mein interested hain, main aapko next steps batati hu 🙏"
        )

    if intent == "consult_info":
        return (
            "Ji bilkul 🙏\n"
            "Guru Maa se baat karne ke liye aap consultation call book kar sakte hain.\n"
            "Ye ek audio phone call hoti hai jisme aapki direct Guru Maa se 20–30 minutes tak baat hogi.\n"
            "Charges – ₹2100\n"
            "Payment options:\n"
            "👉 UPI – neeche diye gaye QR code se\n"
            "👉 Website link – https://www.upaai.in/hi/booking\n"
            "Payment karne ke baad screenshot isi number par bhej dijiye.\n"
            "Aur sath hi apna full name aur date of birth type karke bhej dein.\n"
            "Main aapki booking confirm kar dungi ✅\n"
            "Dhanyavaad 🌸"
        )

    if intent == "consult_payment_verified":
        return (
            f"Dhanyavaad {first_name},\n"
            "Aapka payment verify ho gaya hai ✅\n"
            "Ab main aapke liye Guru Maa ke calendar me next available appointment check kar rahi hoon.\n"
            "Kya aapka appointment ke liye koi preference hai — morning time ya evening time?\n"
            "Ya aapke mind mein koi specific date hai jo aap book karna chahte hain?\n"
            "Main aapki preference ke aur appointment availability ke hisaab se slot confirm karungi🌸"
        )

    if intent == "consult_slot_confirmed":
        date = slots.get("date") or "[Date]"
        time = slots.get("time") or "[Time]"
        return (
            f"Ji {first_name} 🙏\n"
            "Guru Maa se baat karne ke liye next available appointment hai:\n"
            f"📅 {date} ⏰ {time}\n"
            "Maine aapke liye ye slot confirm kar diya hai ✅\n"
            "Kripya apna phone available rakhein.\n"
            "Jab aapke call ka time ho, to aap is number par call karein - +91-9479373709 \n"
            "Aur Guru Maa aapki consultation attend karengi.\n"
            "Agar kisi wajah se koi problem ya delay ho jaye, to aap turant mujhse sampark karein.\n"
            "Main aapki help karungi taaki aapka issue solve ho sake 🌸\n"
            "Dhanyavaad 🙏"
        )

    if intent == "kalawa_info":
        return (
            "Namaste ji 🙏\n"
            "Apamarg Jad Kalawa book karne ke liye aap is link par jaa sakte hain:\n"
            "👉 https://www.upaai.in/product/apamargJadKalawa\n"
            "Ya phir neeche diye gaye QR code se payment kar sakte hain.\n"
            "Ye kalawa Guru Maa aapke naam se sharard purnima (October 7) par siddh karengi,\n"
            "aur uske ke baad aapke address par ship kiya jaayega 📦\n"
            "Kripya apna full name, gotra (agar pata ho to) aur postal address bhej dein\n"
            "taaki hum siddhi aur shipping ki poori vyavastha kar saken 🌸\n"
            "Dhanyavaad 🙏\n"
            "– UPAAI Team"
        )

    if intent == "kalawa_payment_confirmed":
        return (
            "Namaste ji 🙏\n"
            "Aapka Apamarg Kalawa order ka payment prapt ho gaya hai ✅\n"
            "🗓️ 7 October – Sharad Purnima ke pavitra din, Guru Maa aapke liye kalawa ko mantra-siddh karengi.\n"
            "Pooja ke baad aapka parcel DTDC se dispatch kiya jaayega,\n"
            "jo 6–7 din ke andar aap tak pahunch jaayega 📦\n"
            "Guru Maa is kalawa ko vishesh mantraon se aapke naam se abhimantrit karengi –\n"
            "yeh aapke jeevan mein raksha, shanti aur akarshan laane mein sahayak hoga ✨\n"
            "Guru Maa ki kripa se yeh pavitra uphaar aap tak surakshit aur samay par pahunch jaaye –\n"
            "yahi humari prarthana hai 🌸\n"
            "Team UPAAI 🔱"
        )

    if intent == "kalawa_dispatch":
        tracking = slots.get("tracking") or "[Tracking Number / Tracking Link]"
        return (
            "Namaste ji 🙏\n"
            "Aapka Apamarg Kalawa Guru Maa dwara siddh karke ab dispatch ho chuka hai ✅\n"
            f"Courier details: {tracking}\n"
            "Is link se aap apna parcel track kar sakte hain 📦\n"
            "Aapko ye kalawa jaldi hi receive ho jaayega.\n"
            "Jab ye aapke paas pohonche, to kripya naha-dhokar\n"
            "apne seedhe haath ki kalai par ise pehniye.\n"
            "Isse aapko Guru Maa ke siddh mantron ki raksha aur shakti prapt hogi 🌸\n"
            "Dhanyavaad 🙏\n"
            "– Team UPAAI 🔱"
        )

    return ""


async def run_llm_policy(messages) -> Optional[PolicyIntent]:
    model = get_small_chat_model(temperature=0.0).with_structured_output(PolicyIntent)
    chain = LLM_POLICY_PROMPT | model
    try:
        logger.debug("Policy LLM invoked with %d messages; last='%s'", len(messages) if messages else 0, (messages[-1].content[:200] if messages else ""))
        result: PolicyIntent = await chain.ainvoke({"messages": messages})
        logger.debug("Policy LLM result: intent=%s slots=%s", getattr(result, "intent", None), result.model_dump())
        return result
    except Exception:
        logger.exception("Policy LLM classification failed")
        return None


async def maybe_apply_policy(messages) -> Optional[PolicyResult]:
    logger.debug("maybe_apply_policy: evaluating messages=%d", len(messages) if messages else 0)
    intent = await run_llm_policy(messages)
    if not intent or intent.intent == "none":
        logger.debug("maybe_apply_policy: no applicable policy")
        return None
    text = _render_template(intent.intent, intent.model_dump())
    if not text:
        logger.debug("maybe_apply_policy: template rendering produced empty text for intent=%s", intent.intent)
        return None
    logger.info("Policy applied: intent=%s", intent.intent)
    return PolicyResult(text=text, meta=intent.model_dump())


