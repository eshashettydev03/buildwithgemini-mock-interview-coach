"""FastAPI web server for Mock Interview Coach PrepPal."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService

from app.agent import root_agent
from app.tools import get_firestore, get_past_sessions

app = FastAPI(title="PrepPal Mock Interview Coach")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent session & memory services in-process for local runner
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    memory_service=memory_service,
    app_name="preppal",
)

class UserRegisterRequest(BaseModel):
    user_id: str
    display_name: str

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None
    is_start: bool = False

@app.get("/")
async def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(index_path)

@app.post("/api/users")
async def register_user(req: UserRegisterRequest):
    """Registers or updates a user in Firestore."""
    db = get_firestore()
    doc_ref = db.collection("users").document(req.user_id)
    doc_ref.set({
        "user_id": req.user_id,
        "display_name": req.display_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, merge=True)
    return {"status": "ok", "user_id": req.user_id}

@app.get("/api/sessions/past")
async def fetch_past_sessions(user_id: str):
    """Fetches past sessions for user_id."""
    sessions = get_past_sessions(user_id)
    return {"sessions": sessions}

@app.post("/api/chat")
async def chat_turn(req: ChatRequest):
    """Executes an agent turn using the ADK Runner."""
    import uuid
    session_id = req.session_id or f"session_{uuid.uuid4().hex[:8]}"

    # Ensure session exists in the session service
    existing_session = await session_service.get_session(
        session_id=session_id,
        user_id=req.user_id,
        app_name="preppal",
    )
    if not existing_session:
        await session_service.create_session(
            session_id=session_id,
            user_id=req.user_id,
            app_name="preppal",
        )

    # Format user content
    from google.genai import types
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=req.message)],
    )

    reply_text = ""
    image_url = None

    try:
        async for event in runner.run_async(
            session_id=session_id,
            user_id=req.user_id,
            new_message=user_content,
        ):
            # Check for tool call results or function responses containing image URLs
            if hasattr(event, "content") and event.content:
                for part in getattr(event.content, "parts", []):
                    if getattr(part, "text", None):
                        reply_text += part.text
                    # Check if tool response had an image URL
                    fn_resp = getattr(part, "function_response", None)
                    if fn_resp and getattr(fn_resp, "response", None):
                        resp_dict = fn_resp.response
                        if isinstance(resp_dict, dict) and "output" in resp_dict:
                            out = resp_dict["output"]
                            if isinstance(out, str) and ("storage.googleapis.com" in out or "http" in out):
                                image_url = out
                            elif isinstance(out, dict) and out.get("image_url"):
                                image_url = out["image_url"]

    except Exception as e:
        print(f"Error during runner.run_async: {e}")
        reply_text = f"An error occurred: {str(e)}"

    # If image URL not detected in tool output directly, check Firestore for current question image
    if not image_url and ("http" in reply_text and "mockups" in reply_text):
        import re
        match = re.search(r'(https://storage\.googleapis\.com/[^\s\)\"]+)', reply_text)
        if match:
            image_url = match.group(1)

    return {
        "reply": reply_text,
        "image_url": image_url,
        "session_id": session_id,
    }

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

def get_fast_api_app():
    return app
