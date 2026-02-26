# app.py
import os
import json
import tempfile
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sarvamai import SarvamAI
from anthropic import Anthropic

try:
    # Optional web-research / YouTube-style agent (LangChain-based).
    from agent_research import run_research_query  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - optional dependency path
    run_research_query = None  # type: ignore[assignment]

app = FastAPI(title="Sakshi Voice Agent")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ---------- Config ----------
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY")
if not SARVAM_API_KEY:
    raise RuntimeError("Set SARVAM_API_KEY in your environment.")

client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("Set ANTHROPIC_API_KEY in your environment.")

claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)


# ---------- Helpers ----------
def to_dict(obj: Any) -> Dict[str, Any]:
    """Convert sarvamai/pydantic responses to plain dict safely."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):  # pydantic v2
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "dict"):  # pydantic v1
        try:
            return obj.dict()
        except Exception:
            pass
    try:
        return dict(obj)
    except Exception:
        return {"_raw": str(obj)}

def pick_first(d: Dict[str, Any], paths: list[str]) -> str:
    """Get first non-empty value from a list of dotted paths."""
    for p in paths:
        cur: Any = d
        ok = True
        for part in p.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, "", [], {}):
            return str(cur)
    return ""

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/talk")
async def talk(
    file: UploadFile = File(...),
    history: str | None = Form(None),
):
    tmp_path = None
    try:
        # Save upload to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # 1) STT
        # Use default language detection and codec handling (this worked best
        # for your earlier tests).
        with open(tmp_path, "rb") as f:
            stt_resp = client.speech_to_text.transcribe(
                file=f,
                model="saaras:v3",
                mode="transcribe",
            )

        stt = to_dict(stt_resp)
        transcript = pick_first(
            stt,
            ["transcript", "text", "output", "results.transcript", "data.transcript"],
        )

        # If STT could not understand anything, avoid dumping the raw
        # object into the chat. Return a clear message instead.
        if not transcript or not transcript.strip():
            friendly_msg = (
                "I couldn't clearly understand that audio. "
                "Please try again, speaking a bit closer to the mic."
            )
            return JSONResponse(
                {
                    "transcript": "",
                    "reply": friendly_msg,
                    "audio_b64": "",
                    "history": memory,
                }
            )

        # Rebuild conversation history from client (per-session memory).
        # This `memory` only stores natural chat turns, not large data blobs.
        memory: list[dict[str, str]] = []
        if history:
            try:
                raw_history = json.loads(history)
                if isinstance(raw_history, list):
                    for msg in raw_history:
                        if not isinstance(msg, dict):
                            continue
                        role = msg.get("role")
                        content = msg.get("content")
                        if role in ("user", "assistant") and isinstance(content, str):
                            memory.append({"role": role, "content": content})
            except Exception:
                memory = []

        # Decide whether to use the web-research agent (for YouTube / web queries)
        # or standard Claude chat for this turn.
        lower_transcript = transcript.lower()
        use_research_agent = (
            run_research_query is not None
            and any(kw in lower_transcript for kw in ["youtube", "search", "google", "wikipedia", "wiki"])
        )

        if use_research_agent:
            # Use LangChain agent with web tools (YouTube/search-style queries).
            reply = run_research_query(transcript)  # type: ignore[misc]
        else:
            # Build messages for Claude from memory only.
            claude_messages: list[dict[str, str]] = list(memory)
            claude_messages.append({"role": "user", "content": transcript})
            claude_messages = claude_messages[-10:]

            # 2) CHAT via Claude (no external tools)
            claude_resp = claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=512,
                system=(
                    "You are a helpful personal assistant. Provide clear, detailed answers when "
                    "the user asks for explanations, including structured bullet points where "
                    "helpful.\n\n"
                    "You do NOT have direct control over email, YouTube, or the user's computer, "
                    "but you MUST still be helpful:\n"
                    "- If the user asks you to send an email, DRAFT the exact email (subject and body) "
                    "they can copy‑paste instead of saying you cannot send it.\n"
                    "- If the user asks for a YouTube video or link, provide one or more plausible "
                    "YouTube search URLs or video links they can click.\n"
                    "- If the user asks for desktop actions (brightness, volume, settings), explain "
                    "step‑by‑step how they can do it themselves.\n"
                    "Avoid generic disclaimers like 'I do not have the capability'; always return "
                    "the most useful draft, link, or instructions you can."
                ),
                messages=claude_messages,
            )

            # Extract reply from Claude response
            reply = ""
            try:
                for block in getattr(claude_resp, "content", []) or []:
                    if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                        reply = block.text
                        break
                if not reply:
                    reply = str(claude_resp)
            except Exception:
                reply = str(claude_resp)

        # 3) TTS
        tts_resp = client.text_to_speech.convert(
            text=reply,
            model="bulbul:v3",
            target_language_code="en-IN",
            # Speaker names must be lowercase as per SDK:
            # e.g. "anushka", "abhilash", "shubh", ...
            speaker="shubh",
        )

        # Newer SDK returns a TextToSpeechResponse with `audios: list[str]`
        # (each is a base64-encoded WAV). Prefer that, then fall back.
        audio_b64 = ""
        try:
            audios = getattr(tts_resp, "audios", None)
            if isinstance(audios, list) and audios:
                audio_b64 = audios[0]
        except Exception:
            audio_b64 = ""

        if not audio_b64:
            tts = to_dict(tts_resp)
            if isinstance(tts.get("audios"), list) and tts["audios"]:
                audio_b64 = tts["audios"][0]
            else:
                audio_b64 = pick_first(tts, ["audio", "audio_base64", "data.audio"])

        # Updated conversation including this assistant reply (chat text only)
        updated_history = (
            memory + [{"role": "user", "content": transcript}, {"role": "assistant", "content": reply}]
        )[-10:]

        return JSONResponse(
            {
                "transcript": transcript,
                "reply": reply,
                "audio_b64": audio_b64,
                "history": updated_history,
            }
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
