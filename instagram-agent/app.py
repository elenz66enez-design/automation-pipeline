"""
Rabbi Goldsteyn Instagram DM Agent + Dashboard
- Webhook: listens for "link" / "preis" keywords → sends Claude DMs
- Dashboard: /dashboard — live activity tracker
- Storage: Modal Volume (persistent logs)
"""

import modal
import os
import json
import hmac
import hashlib
import time
import random
import httpx
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse

RABBI_SYSTEM_PROMPT = """Du bist Rabbi Goldsteyn — ein Charakter der deutschen Wohlstands-Nische.

CHARAKTER:
- Konservativer, weiser Berater der "verborgenes Wissen" teilt
- Spricht über legale Steuer-Strukturen die Reiche nutzen (VV GmbH, Familien-Genossenschaft)
- Versteht die Wut der Mittelklasse gegen das Steuersystem
- KEIN Abzocker-Coach, KEIN Hype — sachlich, valide, unterstrichen durch Fakten

ZIELGRUPPE:
- Männer 25-45, verdienen €2-5k/Monat, sparen 20-30% in ETFs
- Fühlen sich trotz Sparens pleite
- Wurden von €8-30k Coaches (Baulig etc.) verbrannt — maximaler Skeptizismus
- Core-Pain: "Ich spare 30% und fühle mich trotzdem arm"

HAWKINS MAP OF CONSCIOUSNESS — PFLICHT:
- Triff sie IMMER zuerst bei ihrer aktuellen Energie: Wut (150) / Verlangen (125) / Stolz (175)
- Führe sie HOCH zu: Mut (200) → Vernunft (400)
- NIEMALS mit Force arbeiten (Angst, Manipulation, Druck)
- IMMER mit Power arbeiten (Inspiration, Validierung, Fakten)

REGELN FÜR DMs:
1. KURZ — max 3-4 Sätze. Instagram-DMs müssen natürlich wirken.
2. Starte mit Validierung der Wut / des Problems (nie mit dem Produkt)
3. Hint auf verborgenes System-Wissen (Neugier wecken)
4. CTA am Ende (Link oder Preis Info)
5. Jede Antwort ANDERS formulieren — variiere Satzstruktur, Einstieg, Formulierungen
6. Kein Emojis-Spam — max 1-2 passende Emojis
7. Kein Hochdeutsch-Steiff — natürlich, direkt, wie ein Insider der spricht
8. NIEMALS "Kaufe jetzt" oder typische Verkaufs-Sprache

VERBOTEN:
- Hype-Sprache ("Werde reich in 30 Tagen")
- Druck ("Nur noch 2 Plätze")
- Mansplaining oder bevormunden
- Englische Wörter (außer etablierte Begriffe wie ETF, GmbH)
"""

LINK_PROMPT_DM = """Ein Nutzer hat Rabbi Goldsteyn per Instagram-DM das Wort "{keyword}" geschrieben.

Produkt: "Der Wohlstands Cheat Code" — eBook über legale deutsche Wohlstands-Strukturen (VV GmbH, Familien-Genossenschaft) die Reiche nutzen aber die Mittelklasse nie lernt.

Schreibe eine natürliche DM-Antwort die:
1. Kurz die Wut/das Problem validiert (System hält Mittelklasse absichtlich arm)
2. Neugier weckt auf das verborgene Wissen
3. Den Link direkt teilt: {product_link}

Max 4 Sätze. Variiere den Ansatz jedes Mal. Link ans Ende.
Username: {username}
"""

LINK_PROMPT_COMMENT = """Ein Nutzer hat unter einem Rabbi Goldsteyn Post/Reel das Wort "{keyword}" kommentiert.

Wir antworten per PRIVATER DM (nicht als öffentlicher Kommentar) — Links funktionieren hier.

Produkt: "Der Wohlstands Cheat Code" — eBook über legale deutsche Wohlstands-Strukturen.

Schreibe eine natürliche DM-Antwort die:
1. Kurz die Wut/das Problem validiert
2. Erklärt dass du ihm den Link per DM geschickt hast
3. Den Link teilt: {product_link}

WICHTIG: Schreibe so als wärst du proaktiv — z.B. "hab dir den Link direkt geschickt" — nicht so als würde er ihn angefordert haben.
Max 3-4 Sätze. Variiere jedes Mal.
Username: {username}
"""

PREIS_PROMPT = """Ein Nutzer fragt Rabbi Goldsteyn nach dem Preis von "Der Wohlstands Cheat Code".

Schreibe eine natürliche DM-Antwort die:
1. Den Preis NICHT sofort nennt — erst kurze Wert-Rahmung (was verlieren sie jährlich durch falsche Strukturen?)
2. Kurz erklärt was drin ist (Wissen das Steuerberater €300/Std. verlangen)
3. Dann den Preis nennt und Link teilt: {product_link}

Max 4-5 Sätze. Kein Verkaufs-Druck. Kein Hype.
Username: {username}
"""

TEASER_PROMPT = """Ein Nutzer hat unter einem Rabbi Goldsteyn Post das Wort "{keyword}" kommentiert.

Schreibe eine kurze, neugierig machende DM die:
1. Die Wut/das Problem kurz validiert (System hält Mittelklasse arm)
2. Andeutet dass Rabbi verborgenes Wissen hat
3. Mit einer Frage endet — z.B. "Soll ich dir zeigen wie das geht?"
KEIN Link, KEIN Produkt nennen. Nur Neugier wecken.
Max 2-3 Sätze. Natürlich, kein Verkaufs-Druck.
Username: {username}
"""

# Backward compat alias
LINK_PROMPT = LINK_PROMPT_DM

# ---------------------------------------------------------------------------
# Modal setup
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("fastapi>=0.110.0", "httpx>=0.27.0", "anthropic>=0.28.0")
)

app = modal.App("rabbi-goldsteyn-dm-agent")
secrets = modal.Secret.from_name("rabbi-goldsteyn-secrets")
volume = modal.Volume.from_name("rabbi-goldsteyn-logs", create_if_missing=True)

LOG_FILE = "/logs/activity.json"
TEASER_STATE_FILE = "/logs/teaser_state.json"
RABBI_PAGE_ID = "1007718295758585"

LINK_KEYWORDS = {"link", "links", "url", "schick", "senden", "schicken", "info", "wohlstand", "wealth", "cheat", "gmbh", "steuern", "freiheit", "vermögen", "reich", "kaufen", "bestellen"}
PREIS_KEYWORDS = {"preis", "kosten", "wieviel", "wie viel", "price", "euro", "€"}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def load_logs() -> list:
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_log(entry: dict) -> None:
    os.makedirs("/logs", exist_ok=True)
    logs = load_logs()
    logs.append(entry)
    if len(logs) > 2000:
        logs = logs[-2000:]
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f)
    volume.commit()


def save_system_event(event_type: str, detail: str, level: str = "info") -> None:
    """Log system-level events (token refresh, webhook ping, errors)."""
    os.makedirs("/logs", exist_ok=True)
    try:
        with open("/logs/system.json", "r") as f:
            events = json.load(f)
    except Exception:
        events = []
    events.append({
        "ts": datetime.utcnow().isoformat(),
        "type": event_type,
        "detail": detail,
        "level": level,
    })
    events = events[-500:]
    with open("/logs/system.json", "w") as f:
        json.dump(events, f)
    volume.commit()


def load_system_events() -> list:
    try:
        with open("/logs/system.json", "r") as f:
            return json.load(f)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Teaser state — tracks users who got teaser DM, waiting for opt-in reply
# ---------------------------------------------------------------------------
def _load_teaser_state() -> dict:
    try:
        with open(TEASER_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_teaser_state(state: dict) -> None:
    os.makedirs("/logs", exist_ok=True)
    with open(TEASER_STATE_FILE, "w") as f:
        json.dump(state, f)
    volume.commit()


def mark_teaser_sent(sender_id: str) -> None:
    state = _load_teaser_state()
    state[sender_id] = datetime.utcnow().isoformat()
    _save_teaser_state(state)


def is_teaser_pending(sender_id: str) -> bool:
    """Returns True if user got a teaser DM in the last 24h."""
    state = _load_teaser_state()
    ts = state.get(sender_id)
    if not ts:
        return False
    age = (datetime.utcnow() - datetime.fromisoformat(ts)).total_seconds()
    return age < 86400  # 24h window


def clear_teaser_state(sender_id: str) -> None:
    state = _load_teaser_state()
    state.pop(sender_id, None)
    _save_teaser_state(state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def classify_keyword(text: str) -> str | None:
    t = text.lower()
    for kw in LINK_KEYWORDS:
        if kw in t:
            return "link"
    for kw in PREIS_KEYWORDS:
        if kw in t:
            return "preis"
    return None


def verify_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def generate_dm_response(trigger: str, username: str, product_link: str, source: str = "dm", keyword: str = "", step: str = "full") -> tuple[str, int, float]:
    """Returns (text, tokens, elapsed_seconds). source = 'dm' or 'comment'. step = 'teaser' or 'full'."""
    t0 = time.time()

    if step == "teaser":
        prompt = TEASER_PROMPT
    elif trigger == "preis":
        prompt = PREIS_PROMPT
    elif source == "comment":
        prompt = LINK_PROMPT_COMMENT
    else:
        prompt = LINK_PROMPT_DM

    user_msg = prompt.format(
        username=username or "du",
        product_link=product_link,
        keyword=keyword or trigger,
    )

    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "max_tokens": 300,
                "messages": [
                    {"role": "system", "content": RABBI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        tokens = data.get("usage", {}).get("total_tokens", 0)
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=300,
            system=RABBI_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        tokens = msg.usage.input_tokens + msg.usage.output_tokens
        text = msg.content[0].text.strip()

    elapsed = round(time.time() - t0, 2)
    return text, tokens, elapsed


def send_dm(recipient_id: str, text: str, token: str) -> str:
    url = f"https://graph.facebook.com/v25.0/{RABBI_PAGE_ID}/messages"
    resp = httpx.post(url, json={
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }, params={"access_token": token}, timeout=15)
    return resp.status_code


def send_private_reply(comment_id: str, text: str, token: str) -> str:
    url = f"https://graph.facebook.com/v25.0/{comment_id}/private_replies"
    resp = httpx.post(url, json={"message": text}, params={"access_token": token}, timeout=15)
    return resp.status_code


# ---------------------------------------------------------------------------
# Webhook processing
# ---------------------------------------------------------------------------
def process_entry(entry: dict, access_token: str, product_link: str) -> None:
    for change in entry.get("changes", []):
        field = change.get("field")

        # ── Facebook Page feed (comments on FB page posts) ──────────────────
        if field == "feed":
            value = change.get("value", {})
            if value.get("item") != "comment" or value.get("verb") != "add":
                continue
            comment_text = value.get("message", "")
            comment_id   = value.get("comment_id", "")
            sender_id    = str(value.get("sender_id", ""))
            username     = value.get("sender_name", "")
            post_id      = value.get("post_id", "")

            if sender_id == RABBI_PAGE_ID:
                continue
            trigger = classify_keyword(comment_text)
            if not trigger:
                continue

            print(f"[FB-FEED] trigger={trigger} @{username}: {comment_text!r}")
            delay = round(random.uniform(3, 8), 2)
            time.sleep(delay)
            t_send = time.time()
            dm_text, tokens, claude_ms = generate_dm_response(trigger, username, product_link, source="comment", keyword=comment_text[:30], step="teaser")

            status = "error"
            try:
                status_code = send_private_reply(comment_id, dm_text, access_token)
                status = "sent" if status_code == 200 else f"error_{status_code}"
            except Exception:
                if sender_id:
                    try:
                        send_dm(sender_id, dm_text, access_token)
                        status = "sent_fallback"
                    except Exception:
                        status = "failed"

            if status in ("sent", "sent_fallback"):
                mark_teaser_sent(sender_id)

            total_ms = round((time.time() - t_send) * 1000)
            save_log({
                "ts": datetime.utcnow().isoformat(),
                "type": "fb_comment",
                "trigger": trigger,
                "username": username,
                "sender_id": sender_id,
                "comment_id": comment_id,
                "input": comment_text[:300],
                "response": dm_text,
                "status": status,
                "delay_s": delay,
                "claude_s": claude_ms,
                "tokens": tokens,
                "total_ms": total_ms,
                "hour": datetime.utcnow().hour,
                "weekday": datetime.utcnow().weekday(),
                "media_id": post_id,
                "media_type": "FB_POST",
                "step": "teaser",
            })
            continue

        # ── Instagram comments ───────────────────────────────────────────────
        if field != "comments":
            continue
        value = change.get("value", {})
        comment_text = value.get("text", "")
        comment_id = value.get("id", "")
        from_user = value.get("from", {})
        sender_id = from_user.get("id", "")
        username = from_user.get("name", "")
        media = value.get("media", {})
        media_id = media.get("id", "")
        media_type = media.get("media_product_type", "POST")

        if sender_id == RABBI_PAGE_ID:
            continue
        trigger = classify_keyword(comment_text)
        if not trigger:
            continue

        print(f"[COMMENT] trigger={trigger} @{username}: {comment_text!r}")
        delay = round(random.uniform(3, 8), 2)
        time.sleep(delay)
        t_send = time.time()
        # Step 1: always send teaser DM on comment trigger
        dm_text, tokens, claude_ms = generate_dm_response(trigger, username, product_link, source="comment", keyword=comment_text[:30], step="teaser")

        status = "error"
        try:
            status_code = send_private_reply(comment_id, dm_text, access_token)
            status = "sent" if status_code == 200 else f"error_{status_code}"
        except Exception as e:
            if sender_id:
                try:
                    send_dm(sender_id, dm_text, access_token)
                    status = "sent_fallback"
                except Exception:
                    status = "failed"

        if status in ("sent", "sent_fallback"):
            mark_teaser_sent(sender_id)

        total_ms = round((time.time() - t_send) * 1000)
        save_log({
            "ts": datetime.utcnow().isoformat(),
            "type": "comment",
            "trigger": trigger,
            "username": username,
            "sender_id": sender_id,
            "comment_id": comment_id,
            "input": comment_text[:300],
            "response": dm_text,
            "status": status,
            "delay_s": delay,
            "claude_s": claude_ms,
            "tokens": tokens,
            "total_ms": total_ms,
            "hour": datetime.utcnow().hour,
            "weekday": datetime.utcnow().weekday(),
            "media_id": media_id,
            "media_type": media_type,
            "step": "teaser",
        })

    for messaging in entry.get("messaging", []):
        msg_text = messaging.get("message", {}).get("text", "")
        sender_id = messaging.get("sender", {}).get("id", "")

        if sender_id == RABBI_PAGE_ID:
            continue

        # Step 2: if user replied to teaser → send full DM with link
        if is_teaser_pending(sender_id):
            print(f"[DM-OPT-IN] step=full from {sender_id}: {msg_text!r}")
            delay = round(random.uniform(2, 5), 2)
            time.sleep(delay)
            t_send = time.time()
            dm_text, tokens, claude_ms = generate_dm_response("link", sender_id, product_link, source="comment", step="full")
            status = "error"
            try:
                status_code = send_dm(sender_id, dm_text, access_token)
                status = "sent" if status_code == 200 else f"error_{status_code}"
            except Exception:
                status = "failed"
            if status == "sent":
                clear_teaser_state(sender_id)
            total_ms = round((time.time() - t_send) * 1000)
            save_log({
                "ts": datetime.utcnow().isoformat(),
                "type": "dm_optin",
                "trigger": "opt-in",
                "username": sender_id,
                "sender_id": sender_id,
                "input": msg_text[:300],
                "response": dm_text,
                "status": status,
                "delay_s": delay,
                "claude_s": claude_ms,
                "tokens": tokens,
                "total_ms": total_ms,
                "hour": datetime.utcnow().hour,
                "weekday": datetime.utcnow().weekday(),
                "step": "full",
            })
            continue

        # Normal DM trigger (no teaser pending)
        trigger = classify_keyword(msg_text)
        if not trigger:
            continue

        print(f"[DM] trigger={trigger} from {sender_id}: {msg_text!r}")
        delay = round(random.uniform(3, 8), 2)
        time.sleep(delay)
        t_send = time.time()
        dm_text, tokens, claude_ms = generate_dm_response(trigger, sender_id, product_link)

        status = "error"
        try:
            status_code = send_dm(sender_id, dm_text, access_token)
            status = "sent" if status_code == 200 else f"error_{status_code}"
        except Exception:
            status = "failed"

        total_ms = round((time.time() - t_send) * 1000)
        save_log({
            "ts": datetime.utcnow().isoformat(),
            "type": "dm",
            "trigger": trigger,
            "username": sender_id,
            "sender_id": sender_id,
            "input": msg_text[:300],
            "response": dm_text,
            "status": status,
            "delay_s": delay,
            "claude_s": claude_ms,
            "tokens": tokens,
            "total_ms": total_ms,
            "hour": datetime.utcnow().hour,
            "weekday": datetime.utcnow().weekday(),
        })


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """<!DOCTYPE html>
<!-- Rabbi Goldsteyn DM Agent Dashboard v2 -->
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rabbi Goldsteyn — DM Agent</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#080808;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif;min-height:100vh}
/* Header */
.header{background:#0f0f0f;border-bottom:1px solid #1a1a1a;padding:16px 28px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}
.avatar{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#c9a84c,#7a5a10);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.header-info h1{font-size:16px;font-weight:600;letter-spacing:-0.3px}
.header-info p{font-size:11px;color:#555;margin-top:1px}
.header-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.live-badge{display:flex;align-items:center;gap:5px;background:#0d1f0d;border:1px solid #1a3a1a;border-radius:20px;padding:4px 10px;font-size:11px;color:#22c55e}
.live-dot{width:6px;height:6px;border-radius:50%;background:#22c55e;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,0.4)}50%{opacity:0.8;box-shadow:0 0 0 4px rgba(34,197,94,0)}}
.btn{background:#1a1a1a;border:1px solid #2a2a2a;color:#888;padding:5px 12px;border-radius:6px;cursor:pointer;font-size:11px;transition:all 0.15s}
.btn:hover{background:#222;color:#ccc;border-color:#333}
.btn.active{background:#1e2a1e;border-color:#22c55e;color:#22c55e}
/* Stats grid */
.stats{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;padding:20px 28px}
.stat{background:#0f0f0f;border:1px solid #1a1a1a;border-radius:10px;padding:16px;transition:border-color 0.2s}
.stat:hover{border-color:#2a2a2a}
.stat .label{font-size:10px;color:#444;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px}
.stat .value{font-size:26px;font-weight:700;line-height:1}
.stat .sub{font-size:10px;color:#3a3a3a;margin-top:5px}
.stat.gold .value{color:#c9a84c}
.stat.blue .value{color:#3b82f6}
.stat.green .value{color:#22c55e}
.stat.red .value{color:#ef4444}
.stat.purple .value{color:#a855f7}
.stat.white .value{color:#e0e0e0}
/* Health bar */
.health-bar{margin:0 28px 20px;background:#0f0f0f;border:1px solid #1a1a1a;border-radius:10px;padding:14px 20px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.health-item{display:flex;align-items:center;gap:8px;font-size:12px}
.health-dot{width:8px;height:8px;border-radius:50%}
.h-ok{background:#22c55e;box-shadow:0 0 6px #22c55e}
.h-warn{background:#f59e0b;box-shadow:0 0 6px #f59e0b}
.h-err{background:#ef4444;box-shadow:0 0 6px #ef4444}
/* Toolbar */
.toolbar{padding:0 28px 14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.toolbar-label{font-size:11px;color:#444;margin-right:4px}
.filter-btn{background:#111;border:1px solid #1e1e1e;color:#555;padding:4px 10px;border-radius:5px;cursor:pointer;font-size:11px;transition:all 0.15s}
.filter-btn:hover{border-color:#333;color:#888}
.filter-btn.on{border-color:#c9a84c;color:#c9a84c;background:#1a1400}
.filter-btn.on.blue{border-color:#3b82f6;color:#3b82f6;background:#0a1628}
.filter-btn.on.green{border-color:#22c55e;color:#22c55e;background:#0a1f0a}
.filter-btn.on.red{border-color:#ef4444;color:#ef4444;background:#1f0a0a}
.search{background:#111;border:1px solid #1e1e1e;color:#ccc;padding:4px 10px;border-radius:5px;font-size:11px;width:200px;outline:none}
.search:focus{border-color:#333}
.search::placeholder{color:#333}
.spacer{flex:1}
.auto-label{font-size:10px;color:#333}
/* Log list */
.section{padding:0 28px 32px}
.log-list{display:flex;flex-direction:column;gap:6px}
.log-item{background:#0f0f0f;border:1px solid #1a1a1a;border-radius:9px;overflow:hidden;transition:border-color 0.15s;cursor:pointer}
.log-item:hover{border-color:#2a2a2a}
.log-item.link-t{border-left:2px solid #c9a84c}
.log-item.preis-t{border-left:2px solid #3b82f6}
.log-item.error-item{border-left:2px solid #ef4444;background:#110a0a}
.log-header{padding:12px 14px;display:grid;grid-template-columns:auto auto 1fr auto auto;gap:10px;align-items:center}
.log-body{padding:0 14px 12px;display:none;border-top:1px solid #161616;margin-top:0;padding-top:10px}
.log-item.expanded .log-body{display:block}
.log-item.expanded{border-color:#2a2a2a}
.badge{padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.3px}
.b-link{background:#1a1200;color:#c9a84c;border:1px solid #3a2800}
.b-preis{background:#0a1020;color:#3b82f6;border:1px solid #1a2a4a}
.b-comment{background:#0a180a;color:#22c55e;border:1px solid #1a3a1a}
.b-dm{background:#150f20;color:#a855f7;border:1px solid #2a1a40}
.b-sent{background:#0a180a;color:#22c55e;border:1px solid #1a3a1a}
.b-error{background:#1f0a0a;color:#ef4444;border:1px solid #3a1a1a}
.b-warn{background:#1f1400;color:#f59e0b;border:1px solid #3a2800}
.log-user{font-size:12px;font-weight:600;color:#ccc}
.log-input{font-size:11px;color:#444;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px}
.log-time{font-size:10px;color:#333;white-space:nowrap}
.log-expand{font-size:10px;color:#333;padding:2px 6px}
.body-row{margin-bottom:8px}
.body-label{font-size:10px;color:#444;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:3px}
.body-text{font-size:12px;color:#888;line-height:1.6;background:#0a0a0a;border:1px solid #181818;border-radius:6px;padding:8px 10px;white-space:pre-wrap;word-break:break-word}
.body-text.response-text{color:#bbb}
/* Error section */
.error-banner{margin:0 28px 16px;background:#150808;border:1px solid #3a1212;border-radius:10px;padding:14px 18px}
.error-banner h3{font-size:12px;color:#ef4444;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px}
.error-entry{font-size:11px;color:#888;padding:6px 0;border-bottom:1px solid #1a0a0a;display:flex;gap:12px}
.error-entry:last-child{border-bottom:none}
.error-ts{color:#444;flex-shrink:0}
.error-msg{color:#cc4444}
/* Empty */
.empty{text-align:center;padding:60px;color:#222;font-size:13px}
/* Scrollbar */
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:#0a0a0a}
::-webkit-scrollbar-thumb{background:#222;border-radius:2px}
@media(max-width:900px){.stats{grid-template-columns:repeat(3,1fr)}}
@media(max-width:600px){.stats{grid-template-columns:repeat(2,1fr)}.log-input{display:none}}
</style>
</head>
<body>

<div class="header">
  <div class="avatar">🎩</div>
  <div class="header-info">
    <h1>Rabbi Goldsteyn — DM Agent</h1>
    <p>Der Wohlstands Cheat Code · Page ID 1007718295758585</p>
  </div>
  <div class="header-right">
    <div class="live-badge"><div class="live-dot"></div>Live</div>
    <button class="btn" onclick="loadData()">↻ Refresh</button>
    <button class="btn" id="autoBtn" onclick="toggleAuto()">Auto OFF</button>
  </div>
</div>

<div class="stats" id="stats">
  <div class="stat white"><div class="label">Gesamt</div><div class="value" id="s-total">—</div><div class="sub">alle Zeit</div></div>
  <div class="stat gold"><div class="label">Heute</div><div class="value" id="s-today">—</div><div class="sub" id="s-date">—</div></div>
  <div class="stat gold"><div class="label">Link</div><div class="value" id="s-link">—</div><div class="sub" id="s-link-pct">—</div></div>
  <div class="stat blue"><div class="label">Preis</div><div class="value" id="s-preis">—</div><div class="sub" id="s-preis-pct">—</div></div>
  <div class="stat green"><div class="label">Gesendet</div><div class="value" id="s-sent">—</div><div class="sub">Erfolgsrate</div></div>
  <div class="stat red"><div class="label">Fehler</div><div class="value" id="s-err">—</div><div class="sub">Fehlerrate</div></div>
</div>

<div class="health-bar" id="healthBar">
  <span style="font-size:11px;color:#444;text-transform:uppercase;letter-spacing:0.5px">System Status</span>
  <div class="health-item"><div class="health-dot h-ok" id="h-agent"></div><span id="h-agent-label">Agent lädt...</span></div>
  <div class="health-item"><div class="health-dot h-warn" id="h-webhook"></div><span id="h-webhook-label">Webhook: nicht verbunden</span></div>
  <div class="health-item"><div class="health-dot h-ok" id="h-claude"></div><span id="h-llm-label">LLM: lädt...</span></div>
  <div class="health-item"><div class="health-dot h-ok" id="h-product"></div><span id="h-product-label">Produkt-Link: lädt...</span></div>
  <div style="margin-left:auto;font-size:10px;color:#333" id="lastUpdate">—</div>
</div>

<div id="errorBanner" style="display:none"></div>

<div class="toolbar">
  <span class="toolbar-label">Filter:</span>
  <button class="filter-btn on" id="f-all" onclick="setFilter('all',this)">Alle</button>
  <button class="filter-btn" id="f-link" onclick="setFilter('link',this)">🔗 Link</button>
  <button class="filter-btn blue" id="f-preis" onclick="setFilter('preis',this)">💶 Preis</button>
  <button class="filter-btn green" id="f-comment" onclick="setFilter('comment',this)">💬 Comment</button>
  <button class="filter-btn green" id="f-dm" onclick="setFilter('dm',this)">✉️ DM</button>
  <button class="filter-btn red" id="f-error" onclick="setFilter('error',this)">⚠️ Fehler</button>
  <button class="filter-btn" id="f-posts" onclick="showPostsView(this)" style="margin-left:8px;border-color:#8b5cf6;color:#8b5cf6">🎬 Posts</button>
  <input class="search" id="searchBox" placeholder="🔍 Suchen..." oninput="renderLogs()">
  <div class="spacer"></div>
  <span class="auto-label" id="autoLabel"></span>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 28px 20px">
  <div style="background:#0f0f0f;border:1px solid #1a1a1a;border-radius:10px;padding:16px">
    <div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px">📅 Trigger pro Tag (letzte 7 Tage)</div>
    <canvas id="dailyChart" height="120"></canvas>
  </div>
  <div style="background:#0f0f0f;border:1px solid #1a1a1a;border-radius:10px;padding:16px">
    <div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px">🕐 Aktivste Stunden (UTC)</div>
    <canvas id="hourlyChart" height="120"></canvas>
  </div>
</div>

<div style="padding:0 28px 12px;display:flex;align-items:center;gap:12px">
  <div style="font-size:10px;color:#444;text-transform:uppercase;letter-spacing:0.8px">System Events</div>
  <div id="sysEvents" style="display:flex;gap:8px;flex-wrap:wrap"></div>
</div>

<div class="section">
  <div class="log-list" id="logList"><div class="empty">Lade Daten...</div></div>
</div>

<script>
let allLogs = [];
let activeFilter = 'all';
let autoInterval = null;
let autoOn = false;
let dailyChart = null;
let hourlyChart = null;

async function loadData() {
  try {
    const [logsRes, statsRes, sysRes] = await Promise.all([
      fetch('/api/logs?limit=500'),
      fetch('/api/stats'),
      fetch('/api/system'),
    ]);
    allLogs = await logsRes.json();
    const stats = await statsRes.json();
    const sysEvents = await sysRes.json();
    updateStats();
    renderLogs();
    updateHealth(stats);
    renderCharts(stats);
    renderSysEvents(sysEvents);
    document.getElementById('lastUpdate').textContent = 'Zuletzt: ' + new Date().toLocaleTimeString('de-DE');
  } catch(e) {
    console.error(e);
  }
}

function renderCharts(stats) {
  const chartOpts = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#444', font: { size: 9 } }, grid: { color: '#151515' } },
      y: { ticks: { color: '#444', font: { size: 9 } }, grid: { color: '#151515' }, beginAtZero: true },
    },
  };

  // Daily chart
  const daily = stats.daily || {};
  const days = Object.keys(daily).sort();
  const dCtx = document.getElementById('dailyChart').getContext('2d');
  if (dailyChart) dailyChart.destroy();
  dailyChart = new Chart(dCtx, {
    type: 'bar',
    data: {
      labels: days.map(d => d.slice(5)),
      datasets: [{ data: days.map(d => daily[d]), backgroundColor: '#c9a84c44', borderColor: '#c9a84c', borderWidth: 1, borderRadius: 3 }],
    },
    options: chartOpts,
  });

  // Hourly heatmap as bar chart
  const hourly = stats.hourly || {};
  const hours = Array.from({length: 24}, (_, i) => i);
  const hCtx = document.getElementById('hourlyChart').getContext('2d');
  if (hourlyChart) hourlyChart.destroy();
  hourlyChart = new Chart(hCtx, {
    type: 'bar',
    data: {
      labels: hours.map(h => h + 'h'),
      datasets: [{ data: hours.map(h => hourly[String(h)] || 0), backgroundColor: '#3b82f644', borderColor: '#3b82f6', borderWidth: 1, borderRadius: 2 }],
    },
    options: chartOpts,
  });
}

function renderSysEvents(events) {
  const container = document.getElementById('sysEvents');
  const last5 = events.slice(-5).reverse();
  container.innerHTML = last5.map(e => {
    const color = e.level === 'error' ? '#ef4444' : e.level === 'warn' ? '#f59e0b' : '#444';
    return '<span style="font-size:10px;color:'+color+';background:#111;border:1px solid #1e1e1e;border-radius:4px;padding:2px 7px">' +
      (e.ts||'').slice(11,16) + ' · ' + e.type + '</span>';
  }).join('');
}

function updateStats() {
  const total = allLogs.length;
  const today = new Date().toISOString().slice(0,10);
  const todayCount = allLogs.filter(l => l.ts && l.ts.startsWith(today)).length;
  const linkCount = allLogs.filter(l => l.trigger === 'link').length;
  const preisCount = allLogs.filter(l => l.trigger === 'preis').length;
  const sentCount = allLogs.filter(l => l.status && l.status.includes('sent')).length;
  const errCount = allLogs.filter(l => l.status && (l.status.includes('error') || l.status === 'failed')).length;

  document.getElementById('s-total').textContent = total;
  document.getElementById('s-today').textContent = todayCount;
  document.getElementById('s-date').textContent = today;
  document.getElementById('s-link').textContent = linkCount;
  document.getElementById('s-link-pct').textContent = total ? Math.round(linkCount/total*100)+'% der Trigger' : '—';
  document.getElementById('s-preis').textContent = preisCount;
  document.getElementById('s-preis-pct').textContent = total ? Math.round(preisCount/total*100)+'% der Trigger' : '—';
  document.getElementById('s-sent').textContent = sentCount;
  document.getElementById('s-err').textContent = errCount;

  // Error banner
  const errors = allLogs.filter(l => l.status && (l.status.includes('error') || l.status === 'failed')).slice(-10).reverse();
  const banner = document.getElementById('errorBanner');
  if(errors.length > 0) {
    banner.style.display = 'block';
    banner.innerHTML = '<div class="error-banner"><h3>⚠️ Letzte Fehler ('+errors.length+')</h3>' +
      errors.map(e => '<div class="error-entry"><span class="error-ts">' + (e.ts||'').slice(0,16).replace('T',' ') + '</span>' +
        '<span class="error-msg">Status: ' + e.status + ' · @' + (e.username||'?') + ' · Trigger: ' + (e.trigger||'?') + '</span></div>').join('') +
      '</div>';
  } else {
    banner.style.display = 'none';
  }
}

function updateHealth(stats) {
  document.getElementById('h-agent').className = 'health-dot h-ok';
  document.getElementById('h-agent-label').textContent = 'Agent: Online · ' + (stats.total||0) + ' Logs · Ø ' + (stats.avg_claude_s||0) + 's Claude';

  const hasWebhookEvents = (stats.total||0) > 0;
  document.getElementById('h-webhook').className = 'health-dot ' + (hasWebhookEvents ? 'h-ok' : 'h-warn');
  document.getElementById('h-webhook-label').textContent = hasWebhookEvents ? 'Webhook: Verbunden ✓' : 'Webhook: Warte auf Meta-Verbindung';

  document.getElementById('h-product-label').textContent = 'Produkt-Link: aktiv · ' + (stats.total_tokens||0).toLocaleString() + ' Tokens total';
  const llmLabel = stats.llm_provider === 'groq' ? '⚡ Groq: llama-3.3-70b-versatile' : '🤖 Anthropic: claude-opus-4-6';
  document.getElementById('h-llm-label').textContent = llmLabel;

  // Update extra stats from API
  document.getElementById('s-sent').textContent = (stats.by_status || {})['sent'] || 0;
  document.getElementById('s-err').textContent = ((stats.by_status || {})['failed'] || 0) + ((stats.by_status || {})['error'] || 0);
}

function setFilter(f, btn) {
  activeFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  renderLogs();
}

function renderLogs() {
  const search = document.getElementById('searchBox').value.toLowerCase();
  let logs = [...allLogs].reverse();

  if(activeFilter === 'link') logs = logs.filter(l => l.trigger === 'link');
  else if(activeFilter === 'preis') logs = logs.filter(l => l.trigger === 'preis');
  else if(activeFilter === 'comment') logs = logs.filter(l => l.type === 'comment');
  else if(activeFilter === 'dm') logs = logs.filter(l => l.type === 'dm');
  else if(activeFilter === 'error') logs = logs.filter(l => l.status && (l.status.includes('error') || l.status === 'failed'));

  if(search) logs = logs.filter(l =>
    (l.username||'').toLowerCase().includes(search) ||
    (l.input||'').toLowerCase().includes(search) ||
    (l.response||'').toLowerCase().includes(search) ||
    (l.trigger||'').toLowerCase().includes(search)
  );

  const container = document.getElementById('logList');
  if(logs.length === 0) {
    container.innerHTML = '<div class="empty">Keine Einträge für diesen Filter</div>';
    return;
  }

  container.innerHTML = logs.slice(0, 100).map((l, i) => {
    const ts = (l.ts||'').slice(0,16).replace('T',' ');
    const isError = l.status && (l.status.includes('error') || l.status === 'failed');
    const statusBadge = l.status
      ? (l.status.includes('sent') ? '<span class="badge b-sent">✓ sent</span>' :
         l.status === 'failed' ? '<span class="badge b-error">✗ failed</span>' :
         '<span class="badge b-warn">⚠ '+l.status+'</span>')
      : '';
    return '<div class="log-item '+(l.trigger||'')+'-t'+(isError?' error-item':'')+'" onclick="toggle(this)">' +
      '<div class="log-header">' +
        '<span class="badge b-'+(l.trigger||'link')+'">'+(l.trigger||'?')+'</span>' +
        '<span class="badge b-'+(l.type||'dm')+'">'+(l.type||'dm')+'</span>' +
        '<div style="display:flex;flex-direction:column;gap:2px">' +
          '<span class="log-user">@'+(l.username||'?')+'</span>' +
          '<span class="log-input">"'+(l.input||'').slice(0,80)+'"</span>' +
        '</div>' +
        statusBadge +
        '<span class="log-time">'+ts+'</span>' +
      '</div>' +
      '<div class="log-body">' +
        '<div class="body-row"><div class="body-label">Nachricht des Nutzers</div><div class="body-text">'+(l.input||'—')+'</div></div>' +
        '<div class="body-row"><div class="body-label">Claude Antwort</div><div class="body-text response-text">'+(l.response||'—')+'</div></div>' +
        '<div style="display:flex;gap:8px;font-size:10px;color:#333;margin-top:6px">' +
          '<span>Status: '+(l.status||'—')+'</span>' +
          '<span>·</span><span>'+ts+' UTC</span>' +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

function toggle(el) {
  el.classList.toggle('expanded');
}

function toggleAuto() {
  autoOn = !autoOn;
  const btn = document.getElementById('autoBtn');
  const label = document.getElementById('autoLabel');
  if(autoOn) {
    autoInterval = setInterval(loadData, 30000);
    btn.textContent = 'Auto ON';
    btn.classList.add('active');
    label.textContent = 'Refresh alle 30s';
  } else {
    clearInterval(autoInterval);
    btn.textContent = 'Auto OFF';
    btn.classList.remove('active');
    label.textContent = '';
  }
}

async function showPostsView(btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  const container = document.getElementById('logList');
  container.innerHTML = '<div class="empty">Lade Posts...</div>';

  try {
    const res = await fetch('/api/posts');
    const posts = await res.json();

    if (posts.length === 0) {
      container.innerHTML = '<div class="empty">Noch keine Post-Daten — kommt sobald erste Kommentar-Trigger eintreffen 🎬</div>';
      return;
    }

    container.innerHTML = posts.map(p => {
      const igUrl = 'https://www.instagram.com/p/' + p.media_id + '/';
      const comments = (p.comments || []).slice(-3).reverse();
      return '<div class="log-item" style="border-left:2px solid #8b5cf6">' +
        '<div class="log-header" style="grid-template-columns:auto 1fr auto">' +
          '<span class="badge" style="background:#1a0f30;color:#8b5cf6;border:1px solid #3a1f60">' + (p.media_type||'POST') + '</span>' +
          '<div>' +
            '<div class="log-user" style="display:flex;align-items:center;gap:8px">' +
              'Post ID: ' + p.media_id +
              '<a href="'+igUrl+'" target="_blank" style="font-size:10px;color:#8b5cf6;text-decoration:none">↗ öffnen</a>' +
            '</div>' +
            '<div style="display:flex;gap:10px;margin-top:4px">' +
              '<span style="font-size:11px;color:#c9a84c">🔗 '+p.link+' Link</span>' +
              '<span style="font-size:11px;color:#3b82f6">💶 '+p.preis+' Preis</span>' +
              '<span style="font-size:11px;color:#888">Gesamt: '+p.count+'</span>' +
            '</div>' +
          '</div>' +
          '<span class="log-time">' + (p.last_ts||'').slice(0,16).replace('T',' ') + '</span>' +
        '</div>' +
        (comments.length > 0 ?
          '<div class="log-body" style="display:block">' +
          comments.map(c =>
            '<div style="padding:6px 0;border-bottom:1px solid #151515;display:grid;grid-template-columns:1fr 1fr;gap:12px">' +
              '<div><div class="body-label">@'+c.user+' schrieb</div><div class="body-text">'+(c.text||'—')+'</div></div>' +
              '<div><div class="body-label">Claude antwortete</div><div class="body-text response-text">'+(c.response||'—').slice(0,120)+'...</div></div>' +
            '</div>'
          ).join('') +
          '</div>' : '') +
      '</div>';
    }).join('');
  } catch(e) {
    container.innerHTML = '<div class="empty">Fehler beim Laden der Posts</div>';
  }
}

loadData();
</script>
</body>
</html>"""


def build_dashboard(logs: list) -> str:
    total = len(logs)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today = sum(1 for l in logs if l.get("ts", "").startswith(today_str))
    link_count = sum(1 for l in logs if l.get("trigger") == "link")
    preis_count = sum(1 for l in logs if l.get("trigger") == "preis")
    link_pct = round(link_count / total * 100) if total else 0
    preis_pct = round(preis_count / total * 100) if total else 0

    items = ""
    for entry in reversed(logs[-50:]):
        trigger = entry.get("trigger", "")
        etype = entry.get("type", "dm")
        username = entry.get("username", "unknown")
        inp = entry.get("input", "")
        resp = entry.get("response", "")
        ts = entry.get("ts", "")[:16].replace("T", " ")
        status = entry.get("status", "")
        status_cls = "status-sent" if "sent" in status else "status-error"

        items += f"""
        <div class="activity-item {trigger}-trigger">
          <div style="display:flex;flex-direction:column;gap:4px;padding-top:2px">
            <span class="badge {trigger}">{trigger}</span>
            <span class="badge {etype}">{etype}</span>
          </div>
          <div class="activity-content">
            <div class="username">@{username}</div>
            <div class="input">💬 "{inp}"</div>
            <div class="response">🤖 {resp[:160]}{'...' if len(resp) > 160 else ''}</div>
          </div>
          <div class="activity-meta">
            <div class="time">{ts}</div>
            <div class="{status_cls}">{status}</div>
          </div>
        </div>"""

    return DASHBOARD_HTML


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
web_app = FastAPI()


@web_app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    logs = load_logs()
    return build_dashboard(logs)


@web_app.post("/generate")
async def generate_for_manychat(request: Request):
    """
    ManyChat External Request endpoint.
    POST JSON: {"username": "...", "message": "...", "source": "dm|comment"}
    Returns: {"text": "..."}
    """
    try:
        data = await request.json()
    except Exception:
        data = {}

    username = data.get("username", "du")
    message  = data.get("message", "")
    source   = data.get("source", "dm")
    step     = data.get("step", "full")  # "teaser" or "full"
    product_link = os.environ.get("RABBI_PRODUCT_LINK", "")

    trigger = classify_keyword(message) or "link"
    try:
        text, tokens, elapsed = generate_dm_response(
            trigger, username, product_link, source=source, keyword=message[:30], step=step
        )
    except Exception as e:
        import traceback
        return {"error": str(e), "detail": traceback.format_exc()}

    save_log({
        "ts": datetime.utcnow().isoformat(),
        "type": f"manychat_{source}",
        "trigger": trigger,
        "username": username,
        "sender_id": username,
        "input": message[:300],
        "response": text,
        "status": "sent",
        "delay_s": 0,
        "claude_s": elapsed,
        "tokens": tokens,
        "total_ms": int(elapsed * 1000),
        "hour": datetime.utcnow().hour,
        "weekday": datetime.utcnow().weekday(),
    })

    # ManyChat Dynamic Content format
    return {
        "version": "v2",
        "content": {
            "messages": [{"type": "text", "text": text}]
        }
    }


@web_app.get("/setup-page-subscription")
async def setup_page_subscription():
    """One-time: subscribes FB page + Instagram Business Account to webhook fields."""
    token = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]
    results = {}

    # 1. Subscribe Facebook Page to feed+messages
    r1 = httpx.post(
        f"https://graph.facebook.com/v25.0/{RABBI_PAGE_ID}/subscribed_apps",
        params={"subscribed_fields": "feed,messages,mention", "access_token": token},
        timeout=15,
    )
    results["fb_page"] = {"status": r1.status_code, "body": r1.text}

    # 2. Get Instagram Business Account ID from the Page
    r2 = httpx.get(
        f"https://graph.facebook.com/v25.0/{RABBI_PAGE_ID}",
        params={"fields": "instagram_business_account", "access_token": token},
        timeout=15,
    )
    results["ig_lookup"] = {"status": r2.status_code, "body": r2.text}

    ig_id = r2.json().get("instagram_business_account", {}).get("id")
    if ig_id:
        # 3. Subscribe Instagram Business Account to messages
        r3 = httpx.post(
            f"https://graph.facebook.com/v25.0/{ig_id}/subscribed_apps",
            params={"subscribed_fields": "messages,comments,mentions", "access_token": token},
            timeout=15,
        )
        results["ig_account"] = {"status": r3.status_code, "body": r3.text, "ig_id": ig_id}
    else:
        results["ig_account"] = "Could not find Instagram Business Account ID"

    return results


@web_app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == os.environ.get("META_VERIFY_TOKEN", ""):
        return PlainTextResponse(params.get("hub.challenge"))
    raise HTTPException(status_code=403)


@web_app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    app_secret = os.environ.get("META_APP_SECRET", "")
    sig = request.headers.get("x-hub-signature-256", "")
    if app_secret and not verify_signature(body, sig, app_secret):
        raise HTTPException(status_code=403)

    payload = json.loads(body)
    save_system_event("webhook_received", f"entries={len(payload.get('entry',[]))}", "info")

    access_token = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]
    product_link = os.environ.get("RABBI_PRODUCT_LINK", "")

    for entry in payload.get("entry", []):
        try:
            process_entry(entry, access_token, product_link)
        except Exception as e:
            print(f"[ERROR] {e}")
            save_system_event("processing_error", str(e)[:200], "error")

    return Response(content="EVENT_RECEIVED", media_type="text/plain")


@web_app.get("/api/logs")
async def get_logs(limit: int = 200):
    logs = load_logs()
    return logs[-limit:]


@web_app.get("/api/stats")
async def get_stats():
    from collections import Counter, defaultdict
    logs = load_logs()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    total = len(logs)
    errors = [l for l in logs if "error" in str(l.get("status","")) or l.get("status") == "failed"]

    # Hourly distribution (for heatmap)
    hourly = defaultdict(int)
    for l in logs:
        h = l.get("hour")
        if h is not None:
            hourly[str(h)] += 1

    # Daily trend (last 7 days)
    daily = defaultdict(int)
    for l in logs:
        day = (l.get("ts") or "")[:10]
        if day:
            daily[day] += 1

    # Avg Claude response time
    times = [l.get("claude_s") for l in logs if l.get("claude_s")]
    avg_claude = round(sum(times)/len(times), 2) if times else 0

    # Total tokens used
    total_tokens = sum(l.get("tokens", 0) for l in logs)

    return {
        "total": total,
        "today": sum(1 for l in logs if l.get("ts","").startswith(today)),
        "by_trigger": dict(Counter(l.get("trigger") for l in logs)),
        "by_type": dict(Counter(l.get("type") for l in logs)),
        "by_status": dict(Counter(l.get("status") for l in logs)),
        "error_rate": round(len(errors) / max(total, 1) * 100, 1),
        "success_rate": round((total - len(errors)) / max(total, 1) * 100, 1),
        "avg_claude_s": avg_claude,
        "total_tokens": total_tokens,
        "hourly": dict(hourly),
        "daily": dict(sorted(daily.items())[-7:]),
        "last_errors": [{"ts": e.get("ts","")[:16], "status": e.get("status"), "user": e.get("username","?")} for e in errors[-5:]],
        "llm_provider": "groq" if os.environ.get("GROQ_API_KEY") else "anthropic",
    }


@web_app.get("/api/system")
async def get_system_events():
    return load_system_events()[-100:]


@web_app.get("/api/posts")
async def get_posts_stats():
    """Which posts/reels triggered the most DMs."""
    from collections import defaultdict
    logs = load_logs()
    posts = defaultdict(lambda: {"count": 0, "link": 0, "preis": 0, "comments": [], "last_ts": ""})
    for l in logs:
        mid = l.get("media_id")
        if not mid:
            continue
        posts[mid]["count"] += 1
        posts[mid]["media_type"] = l.get("media_type", "POST")
        if l.get("trigger") == "link":
            posts[mid]["link"] += 1
        elif l.get("trigger") == "preis":
            posts[mid]["preis"] += 1
        posts[mid]["comments"].append({
            "user": l.get("username", "?"),
            "text": l.get("input", ""),
            "response": l.get("response", ""),
            "ts": l.get("ts", ""),
            "status": l.get("status", ""),
        })
        if l.get("ts", "") > posts[mid]["last_ts"]:
            posts[mid]["last_ts"] = l.get("ts", "")
    # Sort by count
    result = [{"media_id": k, **v} for k, v in posts.items()]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Modal deployment
# ---------------------------------------------------------------------------
@app.function(
    image=image,
    secrets=[secrets],
    volumes={"/logs": volume},
    timeout=60,
    min_containers=1,
)
@modal.concurrent(max_inputs=20, target_inputs=5)
@modal.asgi_app()
def webhook():
    return web_app


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
@app.local_entrypoint()
def test_responses():
    product_link = os.environ.get("RABBI_PRODUCT_LINK", "https://dein-link.com")
    for trigger in ["link", "preis"]:
        print(f"\n{'='*60}\nTrigger: {trigger.upper()}\n{'='*60}")
        for i in range(3):
            resp = generate_dm_response(trigger, "max_mustermann", product_link)
            print(f"\n[Variante {i+1}]\n{resp}")
