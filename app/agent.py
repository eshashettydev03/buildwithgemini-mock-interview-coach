"""Mock Interview Coach Agent definition using Google ADK."""

import os
import json
from pathlib import Path
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
try:
    from a2ui.schema.manager import A2uiSchemaManager
    from a2ui.basic_catalog.provider import BasicCatalog
except ImportError:
    A2uiSchemaManager = None
    BasicCatalog = None
from app.a2ui_utils import a2ui_callback

from app.tools import (
    get_question,
    get_question_image,
    save_scorecard,
    get_past_sessions,
    search_official_docs,
    export_scorecard_to_markdown,
    search_reference_repos,
)

# Vertex AI Model Configuration
MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = """You are PrepPal, an expert, realistic technical mock interview coach for software engineering candidates.

## Core Persona & Interview Conduct
- You conduct realistic, rigorous, and professional technical interviews.
- You ask ONE question at a time.
- After the candidate answers, do NOT reveal the answer, solution, or provide hints unless they explicitly give up.
- Probe deeper! Ask 1–2 focused follow-up questions targeting omitted trade-offs, architecture decisions, scalability limits, or edge cases.
- Acknowledge candidate responses neutrally and concisely ("Understood", "Got it") before asking the next probing question.

## Tools
- `get_question(type, difficulty, user_id)`: Fetches an unseen question from the question bank. Call this at the start of an interview.
- `get_question_image(question_id)`: Call this IMMEDIATELY after fetching an Android / Kotlin technical question to display the screen mockup wireframe to the user.
- `save_scorecard(...)`: Persists the session evaluation to Firestore when the candidate says "done" or finishes the interview.
- `get_past_sessions(user_id)`: Checks past session history.

## Memory Bank & Personalization
- At the start of a session, check if you remember any previous weak areas, gaps, or feedback for this user.
- If past weak areas exist in memory, welcome the candidate back, briefly acknowledge what they previously struggled with (e.g. "Last time we noticed some gaps in process death handling and caching; let's pay special attention to those today"), and tailor your follow-ups accordingly.

## Completion & Scorecard Evaluation
When the candidate indicates they are finished (e.g., saying "done", "finish", "wrap up", "I am done"):
1. Calculate a rigorous evaluation with 1–5 numerical scores for each specific rubric category based on the interview type:
   - System Design:
     * architecture: (1-5)
     * scalability: (1-5)
     * trade_offs: (1-5)
     * communication: (1-5)
   - Android Technical:
     * platform_knowledge: (1-5)
     * code_quality: (1-5)
     * edge_cases: (1-5)
     * communication: (1-5)
   - Behavioral:
     * situation_clarity: (1-5)
     * ownership: (1-5)
     * impact: (1-5)
     * reflection: (1-5)
2. Determine the overall hiring recommendation lean:
   - "Strong Hire", "Lean Hire", "Lean No-Hire", or "Strong No-Hire"
3. Identify 2-4 concrete Strengths and 2-4 concrete Gaps / areas for improvement.
4. Call `save_scorecard` with all the structured results.
5. Present the final scorecard clearly in your response formatted with markdown tables and bullet points.
"""

# Build A2UI prompt with version 0.8 and Basic Catalog
_prompt_cache = Path(__file__).resolve().parent / "a2ui_prompt.txt"
if A2uiSchemaManager and BasicCatalog:
    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config("0.8")],
    )
    a2ui_system_prompt = schema_manager.generate_system_prompt(
        role_description="PrepPal, an expert technical mock interview coach for software engineering candidates",
        workflow_description="Conduct the interview session conversationally, and output rich structured A2UI UI cards/tables when presenting scorecards, questions with screen mockups, or past session histories.",
        ui_description=(
            "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
            "Never nest a Card inside a Card. "
            "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
            "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
            "nothing in adk web). "
            "You may include one Image component, but only when you have a public https "
            "URL for the image (for example the URL an image tool returns after uploading "
            "to a public bucket). Set the Image url to that exact https link, for example "
            "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
            "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
            "not have a public URL, add a short Text line noting the image instead. "
            "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
            "headings and emphasis. "
            "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
            "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
        ),
        include_schema=True,
        include_examples=True,
    )
elif _prompt_cache.exists():
    a2ui_system_prompt = _prompt_cache.read_text(encoding="utf-8")
else:
    a2ui_system_prompt = ""

FINAL_INSTRUCTION = f"{SYSTEM_INSTRUCTION}\n\n## A2UI Specification & Instructions\n{a2ui_system_prompt}"

async def interview_turn_callback(callback_context: CallbackContext):
    """Generates memory bank entries when session finishes or when durable facts are observed."""
    # When a turn indicates completion, persist session facts to Memory Bank
    user_content = callback_context.user_content
    text_content = ""
    if user_content and getattr(user_content, "parts", None):
        text_content = " ".join([p.text for p in user_content.parts if getattr(p, "text", None)]).lower()

    if "done" in text_content or "finish" in text_content or "scorecard" in text_content:
        await callback_context.add_session_to_memory()
    return None

# Load Agent Engine resource ID from deployment_metadata.json
def _get_agent_engine_id() -> str | None:
    meta_path = Path(__file__).resolve().parent.parent / "deployment_metadata.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                data = json.load(f)
                return data.get("remote_agent_runtime_id")
        except Exception:
            pass
    return None

agent_engine_id = _get_agent_engine_id()
agent_engine_numeric_id = agent_engine_id.split("/")[-1] if agent_engine_id else None

code_executor = (
    AgentEngineSandboxCodeExecutor(agent_engine_resource_name=agent_engine_id)
    if agent_engine_id
    else None
)

memory_service = (
    VertexAiMemoryBankService(
        project="qwiklabs-gcp-04-f2a70fd871e0",
        location="us-central1",
        agent_engine_id=agent_engine_numeric_id,
    )
    if agent_engine_numeric_id
    else None
)

root_agent = Agent(
    model=MODEL,
    name="mock_interview_coach",
    instruction=FINAL_INSTRUCTION,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        get_question,
        get_question_image,
        save_scorecard,
        get_past_sessions,
        search_official_docs,
        export_scorecard_to_markdown,
        search_reference_repos,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=interview_turn_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
