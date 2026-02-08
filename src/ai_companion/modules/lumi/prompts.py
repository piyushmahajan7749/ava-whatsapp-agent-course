"""
Lumi persona and stage-specific messages for the onboarding flow.
"""

from pathlib import Path

from ai_companion.modules.lumi.state import OnboardingStage

# Load FAQ knowledge from file
_FAQ_PATH = Path(__file__).parent / "FAQ.md"
_FAQ_CONTENT = _FAQ_PATH.read_text() if _FAQ_PATH.exists() else ""

FAQ_SYSTEM_PROMPT_SECTION = f"""
You have access to the following FAQ knowledge about Feel Your Best.
If the user asks a question that can be answered from this FAQ, answer it naturally
and conversationally in 2-3 sentences. Do NOT advance the onboarding stage when answering a FAQ.
After answering, gently guide them back to the current stage question.

=== FAQ Knowledge ===
{_FAQ_CONTENT}
=== End FAQ ===
"""

# Lumi's persona for any AI-generated responses
LUMI_PERSONA = """
You are Lumi, a warm, empathetic AI assistant for Feel Your Best mental health platform.

Personality:
- Use friendly, supportive tone
- Keep messages concise and conversational
- Never diagnose or provide medical advice
- Always maintain confidentiality
- Be patient and non-judgmental
- Acknowledge feelings before moving forward. But don't validate everything they say blindly.

Communication style:
- One question at a time
- Short sentences (1-2 max)
- Mix of warmth and professionalism
- Gentle encouragement
- Vary your sentence structure and openings. Never start two consecutive messages the same way
- Do NOT repeat phrases, questions, sign-offs, or patterns from your previous messages
- Never use em dashes or long dashes. Use commas, periods, or colons instead

Emoji rules:
- Most messages should have ZERO emojis. Let your words carry the warmth
- Only use an emoji when it genuinely adds something (e.g. a wave on first hello, or a celebration at booking)
- Never use the same emoji twice in a conversation
- Never end messages with an emoji as a sign-off habit
- When in doubt, skip the emoji
"""

# Stage-specific messages
STAGE_MESSAGES = {
    # Stage 1: Welcome & Trust Building
    OnboardingStage.WELCOME: """Hey there! 👋 I'm Lumi.

I'm here to understand what brings you to Feel Your Best, so I can find the right therapist and support that truly works for you.

Everything you share with me is completely private and confidential. I'll only use it to match you with the care you need. Sound good?""",

    # Stage 2: Demographics
    OnboardingStage.DEMOGRAPHICS: """Let's start simple. Tell me a bit about yourself:

• How old are you?
• What gender do you identify as?""",

    # Stage 3: Understanding Their Story
    OnboardingStage.STORY: """So, what brings you here today?

Feel free to type it out or send me a voice note, whatever feels easier for you.""",

    # Stage 4: Therapy History
    OnboardingStage.THERAPY_HISTORY: """Have you tried therapy before?""",

    # Stage 5: Care Preferences
    OnboardingStage.CARE_PREFERENCES: """What kind of support feels right for you?""",

    # Stage 6: Medication History
    OnboardingStage.MEDICATION: """Quick question. Are you currently taking any medications for your mental health?""",

    # Stage 7: Concerns & Goals
    OnboardingStage.CONCERNS: """What are you hoping to work on? Select all that apply. Don't worry, there's no judgment here.

□ Anxiety
□ Depression
□ Grief & Loss
□ Trauma & PTSD
□ Relationship Issues
□ Self-Esteem & Confidence
□ Identity & Purpose
□ Emotional Regulation
□ OCD
□ Eating Disorders
□ Addiction & Substance Use
□ Sleep Issues
□ Chronic Illness & Pain
□ ADHD, Autism, or other neurodevelopmental concerns
□ Women's Mental Health
□ Parenting Stress & Family Dynamics
□ Cross-Cultural & Immigration Challenges
□ Body Image Concerns
□ Phobias
□ Something else (tell me more)""",

    # Stage 8: Language Preference
    OnboardingStage.LANGUAGE: """What language do you prefer for therapy?

• Hindi
• English
• Tamil
• Telugu
• Bengali
• Marathi
• Gujarati
• Kannada
• Malayalam
• Punjabi
• Other (please specify)""",

    # Stage 9: Therapist Style Preferences
    OnboardingStage.THERAPIST_STYLE: """Now, let's talk about therapist style. What feels right for you?

(Select all that resonate)

□ Warm & nurturing (gentle, empathetic, holds space for you)
□ Structured & direct (goal-oriented, keeps you on track)
□ A blend of both
□ Queer-affirming (understands LGBTQIA+ experiences)
□ Trauma-informed (works gently with past wounds)
□ Culturally aware (gets your background and identity)
□ Holistic (integrates mindfulness, movement, lifestyle practices)
□ Solution-focused (short-term, practical, results-driven)
□ I'm not sure, help me figure this out""",

    # Stage 10: Gender Preference
    OnboardingStage.GENDER_PREFERENCE: """Do you have a preference for your therapist's gender?""",

    # Stage 11: Personal Context - Relationship Status
    OnboardingStage.PERSONAL_CONTEXT: """Almost there! Just a few quick things.

What's your relationship status?""",

    # Stage 11b: DOB
    OnboardingStage.PERSONAL_DOB: """What's your date of birth?

(Please share in DD/MM/YYYY format)""",

    # Stage 11c: City
    OnboardingStage.PERSONAL_CITY: """Which city are you based in?""",

    # Stage 12: Processing
    OnboardingStage.PROCESSING: """Perfect. Give me just a moment while I find the right fit for you... ✨""",

    # Stage 13: Match Reveal - template with placeholders
    OnboardingStage.MATCH_REVEAL: """Okay, I've got someone really special for you.

Meet {therapist_name} 🌟

{therapist_bio}

---

Why I matched you:
{match_reasons}

---

Your Recommended Care Plan:

🧠 Weekly therapy sessions with {therapist_name}
🌱 Holistic lifestyle support (sleep, movement, nutrition, mindfulness)
💬 Access to your dedicated Care Specialist
📊 Progress tracking & personalized insights

Starting at ₹{price}/month

---

Does this feel right?""",

    # Stage 14: Booking
    OnboardingStage.BOOKING: """Amazing! Before we move forward, just one quick thing:

✅ I understand this is not a clinical diagnosis, and that Feel Your Best may contact me to support my care journey.

Please confirm to proceed.""",

    # Stage 15: Confirmed
    OnboardingStage.CONFIRMED: """🎉 You're all set!

Your first session with {therapist_name} is confirmed for:
📅 {date}
🕐 {time}

Here's what happens next:

1️⃣ You'll receive a calendar invite and session link via email
2️⃣ {care_specialist} will reach out in the next 24 hours to welcome you and answer any questions
3️⃣ Before your session, please fill out this quick prep form so {therapist_name} can make the most of your time together: {prep_link}

Got questions before your session? Just reply here. I'm always around.

Looking forward to supporting your journey! 🌱""",

    # Alternative therapists
    OnboardingStage.ALTERNATIVE_THERAPISTS: """No problem! Here are two other therapists who could also be a great match for you:

{therapist_options}

Still not sure?
• Talk to our Care team for guidance""",
}

# Conditional follow-up messages based on therapy history
THERAPY_HISTORY_FOLLOWUPS = {
    "new": """No worries! Here's what therapy with Feel Your Best looks like:

You'll meet with a licensed therapist who gets you. Your background, your challenges, your goals. They'll create a safe space where you can talk through what's on your mind, work through emotions, and build tools that actually help.

And here's what makes us different: we don't just stop at therapy. We look at your whole life: sleep, movement, nutrition, mindfulness. Because emotional wellbeing isn't just about talking. It's about living differently.

Does that sound like something you'd be open to?""",

    "didnt_stick": """I hear you. Sometimes the fit just isn't right, or the approach doesn't match what you actually need.

That's exactly why we take matching seriously. We want to find someone who truly gets you, and a plan that fits your life.""",

    "helped": """That's great to hear! It sounds like you already know the value of having the right support. Let's find you someone who can continue that journey with you.""",
}

# Empathetic acknowledgments based on story content
STORY_ACKNOWLEDGMENTS = {
    "anxiety": "That sounds really overwhelming. You're not alone in this.",
    "depression": "I'm really glad you reached out. What you're feeling is valid, and support can help.",
    "relationship": "Relationships can be incredibly complex. I'm glad you're here.",
    "burnout": "Burnout is real, especially for high-achievers. Let's find you support.",
    "trauma": "Thank you for trusting me with this. What you've experienced matters, and you deserve support.",
    "grief": "I'm so sorry for your loss. Grief is one of the hardest things to navigate alone.",
    "stress": "It sounds like you're carrying a lot right now. Let's find you the right support.",
    "default": "Thank you for sharing that with me. It takes courage to open up.",
}

# Care preference follow-up for "not sure"
CARE_PREFERENCE_NOT_SURE = """That's okay! A lot of people aren't sure at first. Based on what you share with me, I'll recommend what I think would work best for you. You can always adjust later."""

# Medication follow-up
MEDICATION_YES_FOLLOWUP = """Got it. Can you share which medication(s) and how long you've been on them?

This helps us match you with a therapist who understands your journey."""

# Therapist style "not sure" response
THERAPIST_STYLE_NOT_SURE = """No problem! Based on what you've shared, I'll recommend someone who I think would be a great fit. You can always adjust later."""

# Friction checkpoint messages
FRICTION_CHECKPOINT = """I'm noticing you might be feeling a bit stuck. That happens!

Would it help to have someone from our team walk through this with you, or should we keep going together?"""

FRICTION_CYCLING_OPTIONS = """I can see you're weighing your options carefully, which is great!

If it would help to talk through what you're looking for with someone from our Care team, I can connect you. They might have insights I don't have access to."""

# Human handoff message
HUMAN_HANDOFF_MESSAGE = """Of course! You can book a time with our Care Specialist directly.

Pick a slot that works for you: https://calendar.app.google/G3vT4RjcN9P4cH7M7

They'll walk you through everything and answer any questions you have."""

# Crisis response
CRISIS_RESPONSE = """I'm really glad you reached out. What you're feeling sounds incredibly painful, and I want to make sure you get the right support immediately.

I'm connecting you with someone from our Care team right now.

While I do that, please know these resources are available 24/7:

🆘 Vandrevala Foundation: 1860-2662-345
🆘 Tele-MANAS: 14416 / 1-800-891-4416
🆘 AASRA: 91-9820466726"""

# Re-engagement nudges
NUDGE_1 = """Hey! Just checking in. I'm here whenever you're ready to continue. No rush at all.

Reply anytime and we'll pick up right where we left off."""

NUDGE_2 = """Hi again! I wanted to follow up one more time.

If now's not the right time, that's totally okay. When you're ready, just send me a message and we'll find the right support for you.

Take care 💙"""

# Pricing question response
PRICING_RESPONSE = """Great question! Our care plans start at ₹{base_price}/month.

I'll share the full pricing details once I understand what support would work best for you. That way I can show you exactly what's included. Cool?"""

# Policy/refund question response
POLICY_HANDOFF = """That's a great question about {topic}. Let me connect you with our Care team who can give you the most accurate answer."""

# WhatsApp Community CTA (for drop-off prevention)
WHATSAPP_COMMUNITY_CTA = """You're welcome to join our safe space on WhatsApp for regular check-ins, tools, online events, and a judgment-free space for your emotional wellbeing.

Join here: https://chat.whatsapp.com/LklnvbTjMm7LXexSEh7LGG?mode=gi_t

No pressure, just support when you need it."""

# FYB Vitality Score CTA (for engagement during friction)
VITALITY_SCORE_CTA = """While you're here, want to try something?

Take the FYB Vitality Score: https://client.feelyourbest.co/quiz

It's a complete view of your mind and body, a true measure of how you're doing. As you work on yourself, this score grows with you."""

# Expert Directory CTA
EXPERT_DIRECTORY_CTA = """Want to explore all our experts yourself?

Browse the full directory here: https://client.feelyourbest.co/expert-directory"""
