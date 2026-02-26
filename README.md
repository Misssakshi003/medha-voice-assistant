# Sakshi Voice Agent · Sarvam + Claude

A voice-first personal AI assistant that runs in your browser, powered by:

- **Sarvam AI** for speech-to-text (STT) and text-to-speech (TTS)
- **Claude (Anthropic)** for reasoning, chat, and optional “agent” web research
- **FastAPI** backend + vanilla JS frontend

Speak to it in your browser and get:

- Live transcription
- Intelligent answers with short-term memory per session
- Natural voice replies

> This project is designed to be portfolio-ready: you can push the
> `plumbing_data_pipeline` folder as a standalone GitHub repo and link it
> from your résumé or LinkedIn.

---

## Features

- 🎙️ **Voice chat UI** with a dark, mobile-inspired theme
- 🧠 **Session memory** – remembers the last turns in the conversation
- 🔊 **High‑quality TTS** via Sarvam `bulbul:v3` (speaker `shubh`)
- 🤝 **Claude integration** for:
  - General Q&A and planning
  - Drafting emails and messages
  - Explaining concepts clearly
- 🌐 **Optional agent mode** (via `agent_research.py`):
  - DuckDuckGo + Wikipedia tools using LangChain
  - Good for search / YouTube / research-style prompts
- ⚙️ Production‑oriented structure:
  - `app.py` as a clean FastAPI entry point
  - `templates/` and `static/` for UI
  - `docs/` folder for further documentation

---

## Project structure

From inside `plumbing_data_pipeline/`:

```text
plumbing_data_pipeline/
├─ app.py                  # FastAPI app + routes
├─ agent_research.py       # Optional LangChain research agent (Claude Sonnet)
├─ templates/
│  └─ index.html           # Dark themed chat UI
├─ static/
│  └─ css/
│     └─ style.css         # UI styling
├─ docs/
│  └─ architecture.md      # High-level design notes
├─ README.md               # This file
└─ requirements.txt        # Python dependencies
```

Other files (like old notebooks/CSVs) are not required to run the chatbot.

---

## Setup

### 1. Create and activate a virtual environment

From the folder *above* `plumbing_data_pipeline`:

```bash
cd "assignments practise"          # your workspace root
python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
cd plumbing_data_pipeline
pip install -r requirements.txt
```

### 3. Configure API keys

Create a `.env` file or set environment variables in your shell:

```bash
export SARVAM_API_KEY="your_sarvam_key_here"
export ANTHROPIC_API_KEY="your_claude_key_here"
```

For Windows PowerShell:

```powershell
$env:SARVAM_API_KEY="your_sarvam_key_here"
$env:ANTHROPIC_API_KEY="your_claude_key_here"
```

### 4. Run the app

Development mode (auto‑reload):

```bash
uvicorn app:app --reload
```

Production-style (single worker):

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Then open in your browser:

- http://127.0.0.1:8000

---

## How it works (high-level)

1. **Browser** captures audio via `MediaRecorder` and sends `audio/webm`
   to `POST /talk` along with the current session history.
2. **FastAPI** saves audio to a temp file and calls:
   - `client.speech_to_text.transcribe(...)` (Sarvam `saaras:v3`)
   - builds a short conversation context from history
   - either calls:
     - `run_research_query(...)` (LangChain agent; optional), or
     - `claude_client.messages.create(...)` (Claude Haiku)
3. The **reply text** is sent to Sarvam TTS
   (`text_to_speech.convert(...)`, `bulbul:v3`, `speaker="shubh"`),
   and the first base64 WAV is returned to the browser.
4. The **frontend**:
   - Renders the updated chat history (user + assistant bubbles)
   - Decodes the base64 audio and plays it with an `<audio>` element.

---

## Extending the project

- Add more tools into `agent_research.py` (e.g. your own APIs).
- Replace the Claude model with a different one by changing the model IDs.
- Swap the Sarvam voices / languages by adjusting the TTS parameters.
- Deploy on Render / Railway / any ASGI‑compatible host using the
  `uvicorn app:app` entry point.

---

## License

You can choose any license when you publish this on GitHub (MIT is a good default). This file does not declare a license so you stay flexible for your public repo.

# medha-voice-assistant
