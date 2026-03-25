# Rabbi Goldsteyn — Full Funnel Architecture

## Flow Overview

```
Instagram Post
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  TRIGGER LAYER                                               │
│                                                              │
│  Option A: n8n Schedule (every 15 min)                       │
│    └─ Polls comments via Instagram Graph API                 │
│                                                              │
│  Option B: Instagram Webhook (real-time)                     │
│    └─ Requires Meta App Review [PENDING]                     │
└─────────────────┬───────────────────────────────────────────┘
                  │ Comment with keyword ("link", "info", etc.)
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  DEDUP LAYER                                                  │
│                                                              │
│  Google Sheets: ig_dm_sent                                   │
│  Columns: comment_id | username | ts | step                  │
│  → Skip if comment_id already processed                      │
└─────────────────┬───────────────────────────────────────────┘
                  │ New comment only
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  AI GENERATION LAYER — Modal                                 │
│                                                              │
│  POST /generate                                              │
│  https://elenz66enez--rabbi-goldsteyn-dm-agent-webhook       │
│              .modal.run/generate                             │
│                                                              │
│  step=teaser → 2-3 sentence curiosity DM (no link)          │
│  step=full   → 4-5 sentence DM with product link            │
│                                                              │
│  Internally: Claude claude-sonnet-4-6 via Anthropic API      │
│  Config: min_containers=1 (always warm, <1s latency)         │
│          @modal.concurrent(max_inputs=20)                    │
└─────────────────┬───────────────────────────────────────────┘
                  │ Generated DM text
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  DM DELIVERY LAYER  ✅ RESOLVED                              │
│                                                              │
│  ManyChat Pro (confirmed) — official Meta Business Partner  │
│  No App Review needed. Real-time comment trigger.           │
│                                                              │
│  Flow 1 (Comment → Teaser):                                  │
│    Comment Trigger → External Request /generate?step=teaser │
│    → Set Custom Field teaser_sent=true → Send DM            │
│                                                              │
│  Flow 2 (Reply → Full DM):                                   │
│    DM Trigger → Check teaser_sent=true → External Request   │
│    /generate?step=full → Send Full DM → full_sent=true      │
│                                                              │
│  Dedup: ManyChat Custom User Fields (no Google Sheets needed)│
│  Config: manychat-flow.md                                    │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  REPLY TRACKING LAYER                                        │
│                                                              │
│  n8n polls DM inbox every 5 min                              │
│  → User replied to Teaser?                                   │
│    → Generate Full DM (step=full)                            │
│    → Send Full DM with product link                          │
│  → Log step=full to Google Sheets                            │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### Modal App (`instagram-agent/app.py`)
- **URL:** `https://elenz66enez--rabbi-goldsteyn-dm-agent-webhook.modal.run`
- **Endpoints:**
  - `POST /generate` — AI DM generation (teaser + full)
  - `GET /dashboard` — live activity dashboard
  - `POST /webhook` — Instagram webhook receiver
  - `GET /verify` — webhook verification
- **Storage:** Modal Volume (`rabbi-goldsteyn-logs`)
- **Secrets:** Modal Secret (`rabbi-goldsteyn-secrets`)
- **Config:** `min_containers=1`, `@modal.concurrent(max_inputs=20)`

### n8n Workflow (`instagram-agent/n8n-workflow.json`)
- **Flow A:** Schedule → Get Comments → Dedup → AI Teaser → Log
- **Flow B:** Schedule → Get DM Replies → Check State → AI Full → Log
- **Error handling:** Retry on fail (3x), Wait node with exponential backoff

### Google Sheets (Dedup + Tracking)
- **Sheet:** `ig_dm_sent`
- **Columns:** `comment_id`, `username`, `ts`, `step`
- **Purpose:** Prevent double-sends, track funnel conversion

## Open Issues

| # | Issue | Priority | Status |
|---|-------|----------|--------|
| 1 | DM delivery layer — ManyChat Pro as delivery layer | HIGH | ✅ Resolved |
| 2 | Meta App Review for Instagram webhooks | MEDIUM | Pending submission |
| 3 | n8n workflow not yet live (manual setup remaining) | HIGH | Setup pending |
| 4 | upload-post.com account not created | HIGH | Manual step |

## Decision Needed: DM Delivery

**Recommended path:** Use **ManyChat** (already on Pro?) with the existing `/generate` endpoint as External Request.
- ManyChat handles Instagram DM delivery natively
- `/generate` already returns ManyChat-compatible format (`version: v2`)
- No additional service needed

**Fallback:** Direct Instagram Graph API (requires Meta App Review).
