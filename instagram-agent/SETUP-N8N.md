# Setup: Instagram Comment → AI DM (n8n + upload-post.com)

Kein App Review nötig. Funktioniert mit echten Followern sofort.

---

## Übersicht

```
Comment mit Keyword ("link", "info", etc.)
        ↓ Polling alle 15 min
n8n Workflow
        ↓
Modal /generate (step=teaser)
        ↓
upload-post.com → Teaser DM an Commenter
        ↓ User antwortet
n8n (Polling alle 5 min)
        ↓
Modal /generate (step=full)
        ↓
upload-post.com → Full DM mit Link
```

---

## Schritt 1 — upload-post.com Account (5 min)

1. Gehe zu **https://upload-post.com**
2. Account erstellen (Gratis: 10 DMs/Monat für Tests)
3. **Instagram Account verbinden** via OAuth (unter Settings → Integrations)
4. **API Key kopieren** (unter Settings → API → Generate Key)
5. **Post ID ermitteln:**
   - Gehe zum Instagram-Post (z.B. der Rabbi Goldsteyn Post)
   - URL: `https://www.instagram.com/p/XXXXXXX/`
   - Post ID via upload-post.com Dashboard oder API: `GET /api/v1/posts`

---

## Schritt 2 — Google Sheet erstellen (3 min)

1. Neues Google Sheet erstellen: **"Rabbi Goldsteyn — IG DM Tracking"**
2. Sheet-Tab umbenennen: `ig_dm_sent`
3. Erste Zeile (Header) eintragen:

| A | B | C | D |
|---|---|---|---|
| `comment_id` | `username` | `ts` | `step` |

4. **Sheet ID kopieren** aus der URL:
   `https://docs.google.com/spreadsheets/d/**SHEET_ID_HIER**/edit`

---

## Schritt 3 — n8n Setup (5 min)

### Option A: n8n Cloud (empfohlen)
1. Account erstellen: https://n8n.io (Gratis Tier verfügbar)
2. Einloggen → **Workflows → Import**

### Option B: Self-hosted
```bash
npx n8n
# Öffnet auf http://localhost:5678
```

### Workflow importieren
1. n8n Dashboard → **Workflows → Import from File**
2. Datei wählen: `instagram-agent/n8n-workflow.json`
3. Workflow wird importiert ✓

---

## Schritt 4 — Credentials einrichten (5 min)

### upload-post.com API Key
1. n8n → **Credentials → New**
2. Typ: **HTTP Header Auth**
3. Name: `upload-post.com API Key`
4. Header Name: `Authorization`
5. Header Value: `Bearer DEIN_UPLOADPOST_API_KEY`

### Google Sheets OAuth2
1. n8n → **Credentials → New**
2. Typ: **Google Sheets OAuth2 API**
3. OAuth Flow durchführen (Google Account autorisieren)

---

## Schritt 5 — Variablen setzen (2 min)

In n8n → **Settings → Variables** folgende Werte eintragen:

| Variable | Wert |
|----------|------|
| `INSTAGRAM_POST_ID` | Post ID vom Rabbi-Post (aus upload-post.com) |
| `GOOGLE_SHEET_ID` | Sheet ID aus Google Sheets URL |

---

## Schritt 6 — Nodes anpassen (5 min)

### Keyword-Liste anpassen (optional)
Im Node **"Filter: New + Keyword Match"** → Code:
```js
const KEYWORDS = ['link', 'links', 'info', 'wohlstand', 'cheat', 'gmbh', 'steuern', 'schick', 'senden'];
```
Keywords nach Bedarf erweitern.

### upload-post.com API Endpoints verifizieren
Die Endpoints im Workflow sind Platzhalter basierend auf der upload-post.com API.
Verifiziere die genauen Endpoints in der upload-post.com Dokumentation:
- **Comments abrufen:** `GET /api/v1/comments?post_id=...`
- **DM senden:** `POST /api/v1/messages/dm`
- **Inbox abrufen:** `GET /api/v1/messages/inbox`

Falls die Endpoints abweichen: In den HTTP Request Nodes die URL anpassen.

---

## Schritt 7 — Test (5 min)

1. Workflow **aktivieren** (Toggle oben rechts)
2. Kommentiere "link" unter dem Rabbi-Post mit einem Test-Account
3. Max 15 Min warten
4. Prüfen:
   - [ ] Teaser DM angekommen
   - [ ] Google Sheet: Eintrag mit `step=teaser`
5. Auf Teaser DM antworten (beliebiger Text)
6. Max 5 Min warten
7. Prüfen:
   - [ ] Full DM mit Link angekommen
   - [ ] Google Sheet: Eintrag mit `step=full`

---

## Modal /generate Endpoint

Der Endpoint ist bereits live:
```
POST https://elenz66enez--rabbi-goldsteyn-dm-agent-webhook.modal.run/generate
```

**Teaser Request:**
```json
{
  "username": "testuser",
  "message": "link",
  "source": "comment",
  "step": "teaser"
}
```

**Full DM Request:**
```json
{
  "username": "testuser",
  "message": "link",
  "source": "comment",
  "step": "full"
}
```

**Response Format (ManyChat-kompatibel):**
```json
{
  "version": "v2",
  "content": {
    "messages": [{ "type": "text", "text": "DM Text hier..." }]
  }
}
```

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| "No new comments" obwohl Kommentar da | Keyword in Liste prüfen, Post ID verifizieren |
| DM wird nicht gesendet | upload-post.com API Endpoint + Auth prüfen |
| Google Sheets Fehler | OAuth2 Credentials neu autorisieren |
| Modal Timeout | Normal bei Cold Start (erste Anfrage ~10s) — Retry-Logic ist in Workflow |
| Teaser gesendet, aber kein Full DM | 5-min Polling abwarten, Reply muss in Inbox sein |

---

## Kosten

| Service | Gratis Tier | Production |
|---------|-------------|------------|
| upload-post.com | 10 DMs/Monat | ab $16/mo |
| n8n Cloud | 5 Workflows | ab $20/mo |
| Modal (AI) | $30 Credits | Pay-per-use |
| Google Sheets | Gratis | Gratis |
