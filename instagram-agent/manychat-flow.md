# ManyChat Flow — Rabbi Goldsteyn Instagram Comment → AI DM

## Architektur

```
Instagram Comment (Keyword)
        ↓ ManyChat Comment Trigger (real-time)
Flow 1: Teaser DM
        ↓ External Request → Modal /generate (step=teaser)
        ↓ DM senden (AI Text)
        ↓ Custom Field: teaser_sent = true
              ↓
        User antwortet per DM
              ↓ ManyChat DM Trigger
Flow 2: Full DM
        ↓ Condition: teaser_sent = true
        ↓ External Request → Modal /generate (step=full)
        ↓ Full DM senden (AI Text + Link)
        ↓ Custom Field: full_sent = true
```

---

## Schritt 1 — Custom User Fields anlegen

In ManyChat → **Settings → Custom User Fields → + New Field**

| Field Name | Type | Default |
|------------|------|---------|
| `teaser_sent` | Boolean | false |
| `full_sent` | Boolean | false |
| `teaser_text` | Text | (leer) |
| `full_text` | Text | (leer) |

---

## Schritt 2 — Flow 1: Comment → Teaser DM

### In ManyChat → Flows → + New Flow
Name: **"Rabbi — Comment Teaser DM"**

---

### Trigger: Instagram Post/Reel Comment

1. **+ Add Trigger** → "Instagram Post and Reel Comments"
2. **Post:** "Specific Post" → neusten Reel auswählen
   - In ManyChat auf "Select Post" klicken
   - Es zeigt deine letzten Posts/Reels an → den neusten wählen
   - Post ID wird automatisch gespeichert
3. **Keyword filter:** Contains ANY of:
   ```
   link, links, info, wohlstand, cheat, gmbh, steuern, schick, senden, reich
   ```
4. **Reply type:** Private Reply (DM) ✓
5. **Also send public reply:** Optional — z.B. "📩 Hab dir was geschickt!"

---

### Action 1: External Request → Modal /generate

1. **+ Add Action** → "External Request"
2. Einstellungen:

**URL:**
```
https://elenz66enez--rabbi-goldsteyn-dm-agent-webhook.modal.run/generate
```

**Method:** POST

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "username": "{{instagram.username}}",
  "message": "{{trigger.comment_text}}",
  "source": "comment",
  "step": "teaser"
}
```

**Response Mapping:**
- Variable Name: `teaser_text`
- Map from: `content.messages[0].text`
- Oder: Response Body → `$.content.messages[0].text`

**Timeout:** 10s (ManyChat max)

> ⚠️ Falls Timeout: Modal hat `min_containers=1` — normalerweise <2s.
> Wenn Test-Timeout: Modal erst manuell aufwärmen via curl.

---

### Action 2: Set Custom Field

1. **+ Add Action** → "Set Custom Field"
2. Field: `teaser_sent` → Value: **true**

---

### Action 3: Send DM

1. **+ Add Action** → "Send Message"
2. Type: Text
3. Text:
```
{{teaser_text}}
```

> Das ist der KI-generierte Teaser — z.B.:
> "Ich versteh die Frustration. Du sparst 30% und trotzdem bleibt am Ende nichts übrig.
> Soll ich dir zeigen warum das System so gebaut ist — und wie die oberen 1% das umgehen?"

---

## Schritt 3 — Flow 2: DM Reply → Full DM mit Link

### In ManyChat → Flows → + New Flow
Name: **"Rabbi — DM Reply Full"**

---

### Trigger: Instagram DM Keyword

1. **+ Add Trigger** → "Instagram Direct Message"
2. **Keyword:** "Default" (fängt alle Antworten) ODER spezifisch: "ja", "ja bitte", "zeig mir"
3. **Fallback:** Default Reply aktivieren

---

### Condition: Teaser bereits gesendet?

1. **+ Add Condition**
2. Filter: `teaser_sent` **is** `true`
3. AND: `full_sent` **is not** `true`

**(Nur User die Teaser bekamen, aber noch kein Full-DM)**

---

### Action 1: External Request → Modal /generate (Full)

**URL:**
```
https://elenz66enez--rabbi-goldsteyn-dm-agent-webhook.modal.run/generate
```

**Method:** POST

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "username": "{{instagram.username}}",
  "message": "link",
  "source": "comment",
  "step": "full"
}
```

**Response Mapping:**
- Variable: `full_text`
- Path: `$.content.messages[0].text`

---

### Action 2: Send Full DM

1. **+ Add Action** → "Send Message"
2. Type: Text
3. Text:
```
{{full_text}}
```

> Das Full-DM enthält den Link und ist länger, z.B.:
> "Das System wurde bewusst so gebaut dass Mittelklasse-Familien niemals die gleichen
> Strukturen nutzen wie Vermögende. VV GmbH, Familien-Genossenschaft — legal, erprobt,
> und kaum jemand kennt sie. Hier ist alles erklärt: [link]"

---

### Action 3: Set Custom Field

1. Field: `full_sent` → Value: **true**

---

## Schritt 4 — Test

### Curl Test (Modal Endpoint direkt):
```bash
# Teaser testen
curl -X POST \
  https://elenz66enez--rabbi-goldsteyn-dm-agent-webhook.modal.run/generate \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "message": "link",
    "source": "comment",
    "step": "teaser"
  }'

# Erwartete Antwort:
# {
#   "version": "v2",
#   "content": {
#     "messages": [{ "type": "text", "text": "KI-generierter Teaser..." }]
#   }
# }
```

### ✅ Endpoint bereits live getestet (2026-03-25):

**Teaser Response:**
```
"Ich sehe dass du mehr über die Mechanismen hinter dem Rücken der Mittelklasse
wissen möchtest. Das System hält viele in einer Situation wo sie sich arm fühlen
obwohl sie sparen. Hast du jemals daran gedacht dass es ein anderes System geben
könnte das dich aus dieser Lage befreit?"
```

**Full DM Response:**
```
"Hab dir den Link direkt geschickt, damit du mehr über 'Der Wohlstands Cheat Code'
erfährst: [product link]. Schau mal rein, vielleicht findest du da die Lösung."
```
→ Response Zeit: **<3 Sekunden** (weit unter ManyChat's 10s Timeout) ✅
→ ManyChat v2 Format: ✅

### ManyChat Testplan (erst testen, dann live):

**Phase 1 — ManyChat Test-Modus (kein echtes Posting):**
1. Flow in ManyChat öffnen → "Test Flow" Button (oben rechts)
2. ManyChat öffnet einen Test-Chat in deinem Instagram DM
3. Kommentiere mit deinem Test-Account "link" unter den Reel
4. Prüfen: Teaser DM angekommen? Text sinnvoll?
5. Auf Teaser antworten (beliebiger Text)
6. Prüfen: Full DM mit Link angekommen?
7. Custom Fields prüfen: `teaser_sent = true`, `full_sent = true`?

**Phase 2 — Live schalten:**
- Flow von "Draft" → **"Active"** schalten (Toggle oben rechts)
- Fertig. Läuft ab sofort auf dem neusten Reel.

**Phase 3 — Nach erstem echten Trigger prüfen:**
- ManyChat → Analytics → Flow Activity ansehen
- Modal Dashboard: https://elenz66enez--rabbi-goldsteyn-dm-agent-webhook.modal.run/dashboard

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| External Request timeout (10s) | Modal mit `modal deploy` neu deployen, `min_containers=1` prüfen |
| `teaser_text` leer | Response Mapping Pfad prüfen: `content.messages[0].text` |
| Flow triggert nicht | Keyword in Trigger-Liste prüfen, Post ID verifizieren |
| Doppelte DMs | Custom Field `full_sent = true` prüfen |
| "Response is null" | Modal endpoint curl-testen, ANTHROPIC_API_KEY in Modal Secrets prüfen |

---

## Warum kein n8n mehr nötig

| Was | Vorher (n8n Plan) | Jetzt (ManyChat) |
|-----|-------------------|-----------------|
| Comment Trigger | n8n Polling alle 15 min | **Real-time** via ManyChat |
| DM senden | upload-post.com API (kein DM API!) | **ManyChat nativ** |
| Dedup | Google Sheets | **ManyChat Custom Fields** |
| App Review | Eigener App Review nötig | **ManyChat ist Meta Partner** |
| Setup-Zeit | ~1h | **~15 min** |

n8n ist optional — nur noch nützlich für erweiterte Analytics/Logging.
