# Architecture overview

This document explains the main moving parts of the project so you (or a reviewer)
can quickly understand how everything fits together.

## Stack

- **Backend:** FastAPI (Python)
- **Frontend:** Vanilla HTML, CSS, and JavaScript
- **Speech-to-text / TTS:** Sarvam AI Python SDK (`sarvamai`)
- **LLM:** Anthropic Claude (via `anthropic` Python SDK)
- **Optional “agent” mode:** LangChain + DuckDuckGo + Wikipedia

## Request flow

### 1. User interaction (browser)

The UI is defined in `templates/index.html` and styled via `static/css/style.css`.

Key elements:

- A microphone button to start recording.
- A stop button to end recording.
- A scrollable chat area that renders each message bubble.
- An `<audio>` element to play voice replies.

When the user taps **Start**:

1. `MediaRecorder` is created with `audio/webm`.
2. On **Stop**, the recorded audio chunks are combined into a Blob.
3. A `FormData` payload is built:
   - `file`: the audio blob
   - `history`: JSON-encoded list of `{role, content}` messages
4. This payload is sent via `fetch("/talk", { method: "POST", body: form })`.

### 2. FastAPI endpoint `/talk`

The core logic lives in `app.py`:

1. The audio file is saved to a temporary `.webm` file.
2. Sarvam STT is called:

   ```python
   stt_resp = client.speech_to_text.transcribe(
       file=f,
       model="saaras:v3",
       mode="transcribe",
   )
   ```

3. The transcript is extracted with `pick_first(...)`. If no transcript is
   present, a friendly error is returned instead of a noisy debug object.
4. Session history is rebuilt from the `history` form field.
5. The backend decides whether to:
   - Use the **research agent** (`run_research_query`) for search/YouTube style
     prompts, or
   - Call standard **Claude chat** (Haiku) for normal conversation.
6. The resulting reply text is passed to Sarvam TTS:

   ```python
   tts_resp = client.text_to_speech.convert(
       text=reply,
       model="bulbul:v3",
       target_language_code="en-IN",
       speaker="shubh",
   )
   ```

7. The first base64 WAV from `tts_resp.audios[0]` (or compatible fields) is
   returned to the browser along with the updated history.

### 3. Claude + “agent” mode

The file `agent_research.py` mirrors your standalone AI agent project and
implements:

- A `ResearchResponse` Pydantic schema.
- Tools: DuckDuckGo search, Wikipedia, and a “save to file” helper.
- An Anthropic Claude Sonnet (`claude-3-5-sonnet-20241022`) LangChain agent.

The app uses this **only** when the transcript includes search-like keywords
(`"youtube"`, `"search"`, `"google"`, `"wikipedia"`, `"wiki"`). Otherwise, it
just uses a lightweight Claude Haiku chat completion.

### 4. Session memory

The browser keeps a `history` array of messages and sends it to `/talk` with
each request. The backend:

- Validates and trims this history to the last ~10 turns.
- Uses it as context for Claude so the assistant can remember the recent
  conversation.
- Returns the updated history, which the frontend re-renders as bubbles.

## Deployment notes

- The app entry point is `app:app`.
- For production:
  - Run `uvicorn app:app --host 0.0.0.0 --port 8000`.
  - Front it with Nginx or a managed reverse proxy.
  - Configure `SARVAM_API_KEY` and `ANTHROPIC_API_KEY` as environment variables.
- The UI is static and requires no build step; any ASGI host that can serve
  FastAPI + static files is sufficient.

## Future improvements

- Add OAuth-based email / calendar integrations to let the agent manage
  scheduling and mail safely.
- Persist long-term conversation history in a database.
- Turn the LangChain agent into a richer tool-using system for local desktop
  automation (via a separate, local helper service).

