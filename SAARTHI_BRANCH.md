# Saarthi branch — real-estate WhatsApp agent

This branch (`saarthi`) turns the ava/upaai WhatsApp agent into **Saarthi**, the
AI property assistant for [saarthi-website](https://saarthi-website-ten.vercel.app).
It keeps the same infrastructure (FastAPI + LangGraph + Azure OpenAI gpt-5-chat +
Qdrant memory + SQLite checkpoints + WhatsApp Cloud API) and swaps the brain:
puja/booking → real-estate lead qualification.

## How it connects to the website

The **website is the single source of truth** (Neon Postgres CRM). This bot is
the conversation brain. Every tool call goes through the website's **Agent API**
(`/api/agent/*`, bearer-auth), so matching rules, status transitions, the
never-same-day visit rule, and broker/coordinator alerts live in one place and
the admin CRM reflects the WhatsApp conversation live.

```
WhatsApp ⇄ cx-agent (this, on Azure)
                │  Authorization: Bearer SAARTHI_API_KEY
                ▼
        saarthi-website /api/agent/*  ──►  Neon Postgres (CRM)
```

### The loop, per inbound message
1. `load_session_context_node` → `POST /api/agent/context` upserts the lead,
   records the inbound message in the CRM transcript, and returns live context
   (requirements, status, properties already sent, open visit, earliest visit
   slot). This is injected into the system prompt as "Lead CRM context".
2. `conversation_node` (gpt-5-chat + 4 tools) runs the qualify → match → visit
   journey. Tools:
   - `update_lead_requirements` → `POST /api/agent/update-lead`
   - `search_properties` → `POST /api/agent/search` (records matches + URLs)
   - `schedule_property_visit` → `POST /api/agent/visit` (server clamps to
     tomorrow-or-later, alerts the coordinator)
   - `mark_lead_warm` → `POST /api/agent/update-lead` (fires broker alert)
3. The webhook sends the reply on WhatsApp and mirrors it to the CRM via
   `POST /api/agent/outbound`.

The lead's phone is taken from the LangGraph `thread_id` (the WhatsApp number) —
never an LLM argument, so identities can't be hallucinated.

## Config (env)

In addition to the existing keys (Azure OpenAI, Qdrant, WhatsApp), set:

```
SAARTHI_API_URL="https://saarthi-website-ten.vercel.app"
SAARTHI_API_KEY="<same value as the website's AGENT_API_KEY>"
```

On the **website** (Vercel) set the matching `AGENT_API_KEY`, and make sure
`NEXT_PUBLIC_SITE_URL` is the production domain at build time (the Agent API
builds property links from it).

## What changed vs upaaibot

- New module `modules/saarthi/` (`client.py`, `tools.py`).
- `core/prompts.py` → Saarthi persona + real-estate qualification journey.
- `core/knowledge.py` → Saarthi business facts.
- `graph/state.py` → `lead_context` replaces payment/product/schedule fields.
- `graph/nodes.py` + `graph/graph.py` → dropped payment/product/intent nodes;
  flow is memory → context → conversation ⇄ tools → summarize. Memory is now
  best-effort (a Qdrant outage no longer blocks a lead).
- `graph/utils/chains.py` → binds Saarthi tools; injects lead context.
- `graph/utils/helpers.py` → gpt-5 fix: send `max_completion_tokens` (not
  `max_tokens`) and pin `temperature=1` (the only value gpt-5-chat accepts).
- WhatsApp webhook passes the WhatsApp profile name and mirrors replies to CRM.

## Verified end-to-end (local, against Neon)
qualify → `search_properties` (matches recorded with links) → pick → availability
→ `schedule_property_visit` → CRM shows `VISIT_SCHEDULED` with a tentative slot
that is never same-day, coordinator alerted. (`mark_lead_warm` path also fires
the broker alert.)

## Deploy
Same as other branches (Azure Container App). Point the WhatsApp number's webhook
at `/whatsapp_response`, set the two `SAARTHI_*` env vars, and the matching
`AGENT_API_KEY` on the website. See `deploy-azure-simple.sh` / `update-azure.sh`.
