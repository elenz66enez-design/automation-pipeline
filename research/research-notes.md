# Automation Pipeline — Research Notes

## 1. Infinite Talk (Modal)

**What it is:** An audio-driven video generation model that creates lifelike talking avatar videos.

**Key features:**
- Infinite-length video generation
- Accurate lip sync
- Consistent identity preservation
- Image-to-video AND video-to-video supported

**Modal deployment:** Already available on GitHub (`MeiGen-AI/InfiniteTalk`), deployed on Modal with:
- L40s GPUs
- FusioniX LoRA optimization
- Flash-attention + teacache for speed

**For n8n:** Can call via Modal's API endpoint → HTTP Request node in n8n.

---

## 2. Kie.AI (Recommended for Flow-Style)

**What it is:** An API hub that gives access to multiple video generation models through a single API key.

**Available models:**
- Google Veo 3.1 / Veo 3.1 Fast
- Runway Aleph
- Kling v2.6 / Kling 3.0 Motion Control
- Sora 2 (API wrapper)

**n8n integration:** Already widely used with n8n. Typical flow:
1. Send generation request → get task ID
2. Poll status or use callback URL
3. Retrieve final video

**Use cases found:** People use Kie.AI + n8n + Blotato to auto-create and publish AI motion videos to TikTok and other platforms.

---

## 3. Fal.ai

**What it is:** A unified API platform for AI models (text, image, video).

**Talking head models:**
- **SadTalker** — realistic 3D motion from audio, lip sync, expression scaling
- **MultiTalk** — natural facial expressions + lip sync

**Flow:**
1. Provide image + audio/text
2. API call → model processes
3. Video returned as media URL

**n8n template found:** Template #4987 — "3D Product Video Generator from 2D Image" uses Fal.ai + Google Drive + Gmail for automated video creation pipeline.

---

## 4. VO3

**Clarification:** VO3 AI is NOT a model — it's a platform/blog that compares and reviews video generation models (Veo 3, Sora 2, etc.). When Niko says "official VO3 ones," likely referring to Veo 3/3.1.

**Google Veo 3.1** (Jan 2026):
- 4K resolution, vertical video
- Character consistency
- Integrated audio (dialogue + sound effects)
- Available via Gemini app, Flow, Vertex AI, Google AI Studio

---

## 5. Decision Matrix

| Platform | Best For | Pricing | n8n Ready? |
|----------|----------|---------|------------|
| **Infinite Talk** (Modal) | Talking heads, lip sync | Modal free tier + GPU costs | Yes (HTTP API) |
| **Kie.AI** | Multi-model access, flow videos | Per-generation, affordable | Yes (proven) |
| **Fal.ai** | Quick talking heads, pay-per-use | Pay-per-use | Yes (template exists) |
| **Veo 3.1** | Cinematic quality, 4K | Google pricing | Via Vertex AI API |

---

## Next Steps
1. Start with Kie.AI + n8n for flow-style (most proven integration)
2. Set up Infinite Talk on Modal for talking heads
3. Fal.ai as a backup / complement for quick tests
4. Investigate community pre-built automations for swap-in workflows
