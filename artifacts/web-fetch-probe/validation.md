# Live-Probe `openrouter:web_fetch` (2026-10-10)

Skript: `scripts/probe_web_fetch.py --live` (echter OpenRouter-Aufruf, Agent-Payload
mit `provider.zdr: true`). Rohdaten (ohne Schlüssel) liegen als JSON daneben
(gitignored). Modelle: Claude Sonnet 5.5, GPT-6 Luna, Gemini 3.5 Flash-Lite;
Dokumente: HTML (peps.python.org/pep-0020) und PDF (arxiv.org/pdf/1706.03762).
54 Aufrufe, zusammen rund 0,13 $.

## Ergebnis: Gate nicht bestanden (für unseren Transport)

1. **Kommt der Seitentext beim Client an?**
   - **Chat Completions (unser Agent-Transport, gestreamt und nicht gestreamt): nein.**
     Weder im Stream noch in der fertigen Antwort steht der Text, keine
     `annotations`, kein Toolergebnis. Sichtbar ist nur ein Zähler in
     `usage.server_tool_use_details` (`tool_calls_requested`, `tool_calls_executed`).
   - **Responses API (`/api/v1/responses`): ja.** Ein Output-Item
     `{"type": "openrouter:web_fetch", "status", "url", "title", "content", "httpStatus", "error"}`
     trägt den gelesenen Text. Bei Fehlern `status: "incomplete"` plus `error`.
2. **Usage/Kosten:** Kein `web_fetch_requests`. `server_tool_use_details` zählt
   alle Server-Tool-Aufrufe, auch gescheiterte (3 requested / 3 executed bei 1
   erfolgreichem Fetch), und würde sich mit der Websuche mischen. In `usage.cost`
   taucht keine Fetch-Gebühr auf (cost = upstream inference); laut Doku Exa
   0,001 $/Fetch, Engine `openrouter` gratis. Gelesener Text kostet als
   Input-Tokens des Modells.
3. **`engine: auto` unter ZDR:** läuft bei allen drei Modellen, kein 403. `auto`
   liefert denselben Text wie `exa` (PEP 20: 1 632 Zeichen); `native` liefert
   bei allen drei denselben Text wie `openrouter` (keines hat eigenen Fetch, Fallback).
4. **Grenzen werden eingehalten:** `allowed_domains` → „URL domain is not allowed
   by domain filtering rules.“; `max_uses: 1` → weitere Fetches „Fetch limit
   reached“; `max_content_tokens: 500` → Text nach rund 2 000 Zeichen abgeschnitten.
5. **PDF:** bei allen drei Modellen lesbar (wörtliches Abstract-Zitat).
   **Latenz:** ganzer Aufruf mit einem Fetch 1,5–3,9 s, mit drei Versuchen bis 8,7 s.

## Abdeckung im Vergleich zum eigenen Abruf

`--case coverage`, 21 typische Quellseiten: eigener Abruf
(`source_documents.fetch_document`) gegen OpenRouter `auto` (GPT-6 Luna, Responses API).

| | eigener Abruf | OpenRouter `auto` |
|---|---|---|
| Text gelesen | 12 brauchbar, 2 fast leer (heise 264, TechRadar 36 Zeichen) | 21/21 |
| gescheitert | 6× `access_denied` (Reuters, NYT, OpenAI, Investopedia, Zeit), 1× PDF `unsupported_document` | 0 |
| Dauer | 0,1–2,8 s | 2,6–3,9 s (inkl. Modellaufruf) |
| Kosten je Seite | 0 | 0,007–0,066 ct (Luna-Tokens), ggf. + 0,1 ct Exa |

## Folgerung

Der Auftrag (Server-Tool direkt im Orchestrator-Schritt) ist mit unserem
Chat-Completions-Transport nicht prüfbar umsetzbar: Der Orchestrator könnte
lesen, aber Antwortschritt und Judges sähen den Text nie (das Problem von A17).
Umsetzbar sind:

- **Eigenes Client-Tool `read_source`, ausgeführt über OpenRouters Fetch**
  (Responses API, kleiner Helfer-Aufruf, Text aus dem `openrouter:web_fetch`-Item):
  Abdeckung wie oben 21/21, PDF inklusive, Text landet als Evidenz bei uns.
- **Eigenes Client-Tool über `fetch_document`** (Rückfall laut Auftrag):
  ohne Dritte und gratis, aber 8 von 21 typischen Quellen nicht oder kaum lesbar
  und ohne PDF.
