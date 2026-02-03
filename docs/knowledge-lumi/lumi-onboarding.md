---

## Entry Point & Authentication

**Trigger:** User clicks Meta ad → Redirected to WhatsApp chat

```
System checks mobile number against existing client database
├─ Existing paying client → Route to client support flow
└─ New/non-paying user → Activate Lumi onboarding

```

---

## **Stage 1: Welcome & Trust Building**

**Lumi:**

```
Hey there! 👋 I'm Lumi.

I'm here to understand what brings you to Feel Your Best, so I can find the right therapist and support that truly works for you.

Everything you share with me is completely private and confidential. I'll only use it to match you with the care you need. Sound good?

```

_[Wait for user acknowledgment]_

---

## **Stage 2: Getting to Know You**

**Lumi:**

```
Let's start simple. Tell me a bit about yourself:

• How old are you?
• What gender do you identify as?

```

_[Capture: Age, Gender identity]_

_[System flag: If user identifies as trans/non-binary/prefer not to say → Flag for queer-affirming therapist match]_

---

## **Stage 3: Understanding Their Story**

**Lumi:**

```
So, what brings you here today?

Feel free to type it out or send me a voice note — whatever feels easier for you.

```

_[Accept text or voice note. If voice: transcribe and analyze sentiment]_

**[Empathetic acknowledgment based on response]**

Examples:

- If anxiety mentioned: *"That sounds really overwhelming. You're not alone in this."*
- If relationship issues: *"Relationships can be incredibly complex. I'm glad you're here."*
- If burnout: *"Burnout is real, especially for high-achievers. Let's find you support."*
- If trauma/abuse: *"Thank you for trusting me with this. What you've experienced matters, and you deserve support."*

_[System check: Crisis language detection → If detected, immediate escalation to human + crisis resources]_

---

## **Stage 4: Therapy History**

**Lumi:**

```
Have you tried therapy before?

Just tap one:
• Yes, but it didn't stick
• Yes, and it helped
• No, I'm new to this

```

_[Capture response]_

---

### **[If "No, I'm new to this"]**

**Lumi:**

```
No worries! Here's what therapy with Feel Your Best looks like:

You'll meet with a licensed therapist who gets you — your background, your challenges, your goals. They'll create a safe space where you can talk through what's on your mind, work through emotions, and build tools that actually help.

And here's what makes us different: we don't just stop at therapy. We look at your whole life — sleep, movement, nutrition, mindfulness — because emotional wellbeing isn't just about talking. It's about living differently.

Does that sound like something you'd be open to?

```

_[Wait for response]_

---

### **[If "Yes, but it didn't stick"]**

**Lumi:**

```
I hear you. Sometimes the fit just isn't right, or the approach doesn't match what you actually need.

That's exactly why we take matching seriously — we want to find someone who truly gets you, and a plan that fits your life.

```

---

### **[If "Yes, and it helped"]**

**Lumi:**

```
That's great to hear! It sounds like you already know the value of having the right support. Let's find you someone who can continue that journey with you.

```

---

## **Stage 5: Care Preferences**

**Lumi:**

```
What kind of support feels right for you?

• Full care plan (therapy + lifestyle support for sleep, movement, nutrition)
• Just therapy for now
• Honestly, I'm not sure yet

```

_[Capture preference]_

---

### **[If "I'm not sure yet"]**

**Lumi:**

```
That's okay! A lot of people aren't sure at first. Based on what you share with me, I'll recommend what I think would work best for you. You can always adjust later.

```

---

## **Stage 6: Medication History**

**Lumi:**

```
Quick question — are you currently taking any medications for your mental health?

• Yes
• No

```

---

### **[If Yes]**

**Lumi:**

```
Got it. Can you share which medication(s) and how long you've been on them?

This helps us match you with a therapist who understands your journey.

```

_[Free text capture]_

_[System flag: If multiple medications or long-term psychiatric care mentioned → Consider offering human handoff after next 1-2 questions]_

---

## **Stage 7: Concerns & Goals**

**Lumi:**

```
What are you hoping to work on? Select all that apply — and don't worry, there's no judgment here.

□ Anxiety
□ Depression
□ Grief & Loss
□ Trauma & PTSD
□ Relationship Issues
□ Self-Esteem & Confidence
□ Identity & Purpose
□ Emotional Regulation (managing big feelings)
□ OCD
□ Eating Disorders
□ Addiction & Substance Use
□ Sleep Issues
□ Chronic Illness & Pain
□ ADHD, Autism, or other neurodevelopmental concerns
□ Women's Mental Health (postpartum, PCOS, perimenopause, etc.)
□ Parenting Stress & Family Dynamics
□ Cross-Cultural & Immigration Challenges
□ Body Image Concerns
□ Phobias
□ Something else (tell me more)

```

_[Allow multiple selections. If "Something else" selected, capture free text]_

---

### **[FRICTION CHECKPOINT 1: After 4-5 questions, if user seems stuck/hesitant]**

_[System detects: Very short answers, long pauses, "I don't know" responses, or evasive language]_

**Lumi:**

```
I'm noticing you might be feeling a bit stuck. That happens!

Would it help to have someone from our team walk through this with you, or should we keep going together?

• Keep going with Lumi
• Talk to someone from the team

```

---

## **Stage 8: Language Preference**

**Lumi:**

```
What language do you prefer for therapy?

[Dropdown menu:]
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
• Other (please specify)

```

_[Capture selection]_

---

## **Stage 9: Therapist Style Preferences**

**Lumi:**

```
Now, let's talk about therapist style. What feels right for you?

(Select all that resonate)

□ Warm & nurturing (gentle, empathetic, holds space for you)
□ Structured & direct (goal-oriented, keeps you on track)
□ A blend of both
□ Queer-affirming (understands LGBTQIA+ experiences)
□ Trauma-informed (works gently with past wounds)
□ Culturally aware (gets your background and identity)
□ Holistic (integrates mindfulness, movement, lifestyle practices)
□ Solution-focused (short-term, practical, results-driven)
□ I'm not sure — help me figure this out

```

_[Capture selections]_

---

### **[If "I'm not sure" selected]**

**Lumi:**

```
No problem! Based on what you've shared, I'll recommend someone who I think would be a great fit. You can always adjust later.

```

---

## **Stage 10: Gender Preference**

**Lumi:**

```
Do you have a preference for your therapist's gender?

• Man
• Woman
• I'm flexible

```

_[Capture preference]_

---

## **Stage 11: Personal Context**

**Lumi:**

```
Almost there! Just a few quick things:

What's your relationship status?

• Single
• Married
• In a relationship
• Separated/Divorced
• Widowed
• Prefer not to say

```

_[Capture response]_

---

**Lumi:**

```
What's your date of birth?

[Date picker: DD/MM/YYYY]

```

_[Capture DOB]_

---

**Lumi:**

```
Which city are you based in?

[Free text field]

```

_[Capture city]_

---

## **Stage 12: Processing & Match**

**Lumi:**

```
Perfect. Give me just a moment while I find the right fit for you...

[Loading animation: 3-5 seconds]

```

_[System runs matching algorithm based on:]_

- _Concerns/specializations_
- _Language_
- _Gender preference_
- _Style preferences_
- _Therapist availability_
- _Queer-affirming flag (if applicable)_
- _Trauma specialization (if applicable)_
- _Location/timezone_

---

## **Stage 13: Therapist & Care Plan Reveal**

**Lumi:**

```
Okay, I've got someone really special for you.

Meet [Therapist Name] 🌟

[Therapist photo + credentials badge]

[Brief bio: 2-3 sentences highlighting relevant experience]

---

Why I matched you:
✓ Specializes in [user's top 2 concerns]
✓ [Style match - e.g., "Warm, nurturing approach with gentle accountability"]
✓ Fluent in [language]
✓ [Additional relevant match - e.g., "Has deep experience with cross-cultural challenges" or "Queer-affirming practice"]

---

Your Recommended Care Plan:

🧠 Weekly therapy sessions with [Therapist Name]
🌱 Holistic lifestyle support (sleep, movement, nutrition, mindfulness)
💬 Access to your dedicated Care Specialist
📊 Progress tracking & personalized insights

Starting at ₹[price]/month

---

Does this feel right?

• Yes, let's book my first session
• Show me other therapist options

```

---

## **Stage 14a: If User Selects "Yes, let's book"**

**Lumi:**

```
Amazing! Before we move forward, just one quick thing:

✅ I understand this is not a clinical diagnosis, and that Feel Your Best may contact me to support my care journey.

[Checkbox to confirm]

```

_[User checks box]_

---

**Lumi:**

```
Perfect! Tap below to choose your first session time and complete your booking.

[CTA Button: Book My First Session →]

```

_[Redirect to web-based booking page with pre-filled info: Name, DOB, City, Therapist selection, Care plan selection]_

---

### **Booking Page Elements:**

- Calendar view with therapist's availability
- Session time slots
- Payment gateway (Razorpay/Stripe)
- Confirmation page with:
  - Session details
  - Therapist intro video/welcome message
  - Pre-session prep questionnaire link
  - WhatsApp confirmation sent automatically

---

## **Stage 14b: If User Selects "Show me other options"**

**Lumi:**

```
No problem! Here are two other therapists who could also be a great match for you:

---

**[Therapist 2 Name]**
[Photo + credentials]
[2-sentence bio]

Why this match:
✓ [Key specialization]
✓ [Style difference from first match]

[Button: Learn More] [Button: Choose This Therapist]

---

**[Therapist 3 Name]**
[Photo + credentials]
[2-sentence bio]

Why this match:
✓ [Key specialization]
✓ [Style difference from first match]

[Button: Learn More] [Button: Choose This Therapist]

---

Still not sure?
• Talk to our Care team for guidance

```

---

### **[FRICTION CHECKPOINT 2: If user cycles through options 2+ times]**

**Lumi:**

```
I can see you're weighing your options carefully — which is great!

If it would help to talk through what you're looking for with someone from our Care team, I can connect you. They might have insights I don't have access to.

• Let's talk to the Care team
• Show me one more option

```

---

### **[If user selects "Talk to our Care team"]**

**Lumi:**

```
Of course! I'm connecting you with [Care Specialist Name] from our team now. They'll be with you in just a moment.

[Handoff to human agent]
[Internal note passed to Care team with full context: user responses, concerns, therapist matches shown, hesitation points]

```

---

## **Stage 15: Post-Booking Confirmation (Automated)**

_[After successful booking on web]_

**Lumi (WhatsApp message):**

```
🎉 You're all set!

Your first session with [Therapist Name] is confirmed for:
📅 [Date]
🕐 [Time]

Here's what happens next:

1️⃣ You'll receive a calendar invite and session link via email
2️⃣ [Care Specialist Name] will reach out in the next 24 hours to welcome you and answer any questions
3️⃣ Before your session, please fill out this quick prep form so [Therapist Name] can make the most of your time together: [Link]

Got questions before your session? Just reply here — I'm always around.

Looking forward to supporting your journey! 🌱

```

---

## **Edge Cases & Crisis Handling**

### **Crisis Language Detected (Any Stage)**

_[System detects: Suicidal ideation, self-harm, immediate danger]_

**Lumi:**

```
I'm really glad you reached out. What you're feeling sounds incredibly painful, and I want to make sure you get the right support immediately.

I'm connecting you with someone from our Care team right now.

While I do that, please know these resources are available 24/7:

🆘 Vandrevala Foundation: 1860-2662-345
🆘 iCall (Tata Institute): 9152987821
🆘 AASRA: 91-9820466726

[Immediate escalation to human Care team member]
[Internal alert sent with full conversation context]

```

---

### **User Asks About Pricing Mid-Flow**

**Lumi:**

```
Great question! Our care plans start at ₹[base price]/month.

I'll share the full pricing details once I understand what support would work best for you — that way I can show you exactly what's included. Cool?

```

---

### **User Asks About Insurance/Refunds/Policy Questions**

**Lumi:**

```
That's a great question about [insurance/refunds/scheduling]. Let me connect you with our Care team who can give you the most accurate answer.

[Button: Talk to Care Team]

```

_[Handoff to human with context]_

---

### **User Becomes Unresponsive Mid-Flow**

_[If no response for 2 hours]_

**Lumi (Automated nudge):**

```
Hey! Just checking in — I'm here whenever you're ready to continue. No rush at all.

Reply anytime and we'll pick up right where we left off.

```

_[If no response for 24 hours]_

**Lumi (Second nudge):**

```
Hi again! I wanted to follow up one more time.

If now's not the right time, that's totally okay. When you're ready, just send me a message and we'll find the right support for you.

Take care 💙

```

_[If no response for 72 hours → conversation archived, user can restart anytime]_

---

## Technical Implementation Notes

### **AI Agent (Lumi) Capabilities:**

- NLP for sentiment analysis on voice notes and open text
- Crisis language detection with immediate escalation protocols
- Conditional logic for dynamic follow-ups
- Empathetic response generation based on user concerns
- Friction detection (short answers, hesitation, confusion)
- Matching algorithm integration

### **Data Capture & Security:**

- All responses stored in HIPAA-compliant encrypted database
- Structured format for matching algorithm
- Conversation tagging for quality assurance
- High-risk flag system for human review
- User can request data deletion anytime

### **Handoff Protocols:**

- Crisis → Immediate human + resources
- Complex psychiatric history → Offer human after Stage 6
- Repeated hesitation → Offer human at checkpoints
- Technical/policy questions → Auto-route to human
- Post-booking → Transition to Care Specialist within 24 hours

---

## Success Metrics to Track

**Conversion Metrics:**

- % who complete full onboarding
- Drop-off points (which stage)
- Time to complete onboarding
- % who book after match reveal
- % who request human handoff (and when)

**Quality Metrics:**

- User satisfaction with Lumi (post-booking survey)
- Match accuracy (did first therapist work out?)
- % who send voice notes vs. text
- Average concerns selected (depth of sharing)

**Engagement Metrics:**

- % who use "Show other options"
- % who complete booking same day vs. return later
- Response time per message
- Re-engagement rate after drop-off nudges

---
