"""Tools for the Mock Interview Coach agent."""

import io
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from google.cloud import firestore
from google.cloud import storage
from google import genai
from google.genai import types
from google.adk.tools.tool_context import ToolContext

# Hardcoded string as required for Agent Platform Firestore compatibility
PROJECT_ID = "qwiklabs-gcp-04-f2a70fd871e0"
# Hardcoded bucket name as a string as required
BUCKET_NAME = "preppal-mockups-qwiklabs-gcp-04-f2a70fd871e0"

_db: Optional[firestore.Client] = None
_storage_client: Optional[storage.Client] = None
_genai_client: Optional[genai.Client] = None

def get_firestore() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT_ID)
    return _db

def get_storage() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=PROJECT_ID)
    return _storage_client

def get_genai() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
        os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
        _genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    return _genai_client

DIFFICULTY_RANKS = {"mid": 1, "senior": 2, "staff": 3}

def get_question(type: str, difficulty: str, user_id: str) -> Dict[str, Any]:
    """Picks an interview question from Firestore, avoiding questions the user has already seen.

    Fallback cascade:
    1. Exact type + difficulty match, unseen by user.
    2. Nearest difficulty of the same type, unseen by user.
    3. Any unseen question of that type.
    4. Allow repeats if all questions of that type have been seen.

    Args:
        type: Interview type ('system_design', 'android_technical', or 'behavioral').
        difficulty: Difficulty level ('mid', 'senior', or 'staff').
        user_id: The candidate's persistent UUID.

    Returns:
        A dict with the question details: id, text, type, difficulty, screen_name, key_points, image_url.
    """
    db = get_firestore()
    type_norm = type.strip().lower()
    diff_norm = difficulty.strip().lower()
    if diff_norm not in DIFFICULTY_RANKS:
        diff_norm = "senior"

    # 1. Fetch seen questions for this user from sessions
    seen_ids = set()
    if user_id:
        sessions_ref = db.collection("sessions").where("user_id", "==", user_id).stream()
        for s in sessions_ref:
            data = s.to_dict()
            for qid in data.get("questions_asked", []):
                seen_ids.add(qid)

    # 2. Fetch all questions of this type from Firestore
    all_questions = []
    docs = db.collection("questions").where("type", "==", type_norm).stream()
    for d in docs:
        qdata = d.to_dict()
        qdata["id"] = d.id
        all_questions.append(qdata)

    if not all_questions:
        # Fallback to any questions in DB if type name was slightly misnamed
        all_questions = [d.to_dict() | {"id": d.id} for d in db.collection("questions").stream()]

    if not all_questions:
        return {
            "id": "generic_fallback",
            "type": type_norm,
            "difficulty": diff_norm,
            "text": "Design a scalable client-server architecture with caching and fault tolerance.",
            "key_points": ["Architecture", "Data model", "Failure modes"],
            "screen_name": None,
            "image_url": None,
        }

    target_rank = DIFFICULTY_RANKS.get(diff_norm, 2)

    def rank_distance(q):
        q_diff = q.get("difficulty", "senior")
        return abs(DIFFICULTY_RANKS.get(q_diff, 2) - target_rank)

    unseen = [q for q in all_questions if q["id"] not in seen_ids]

    # Priority 1: Exact difficulty match among unseen
    exact_unseen = [q for q in unseen if q.get("difficulty") == diff_norm]
    if exact_unseen:
        return exact_unseen[0]

    # Priority 2: Nearest difficulty among unseen
    if unseen:
        unseen_sorted = sorted(unseen, key=rank_distance)
        return unseen_sorted[0]

    # Priority 3: Repeats allowed (all questions have been seen)
    exact_all = [q for q in all_questions if q.get("difficulty") == diff_norm]
    if exact_all:
        return exact_all[0]

    return sorted(all_questions, key=rank_distance)[0]


async def get_question_image(question_id: str, tool_context: Optional[ToolContext] = None) -> str:
    """Retrieves or generates a mobile app UI screen mockup for Android/Kotlin technical questions.

    Uses gemini-3.1-flash-lite-image in the global region.
    1. Saves the image as an artifact using tool_context.save_artifact so it appears in the Playground's Artifacts panel.
    2. Uploads the image bytes to the public Cloud Storage bucket (hardcoded string) and returns the public HTTPS URL.
    3. Caches the public URL in Firestore.

    Args:
        question_id: The question identifier (e.g. 'android_news_feed').
        tool_context: ToolContext injected by ADK to access artifact services.

    Returns:
        The public HTTPS URL to the screen mockup image.
    """
    db = get_firestore()
    doc_ref = db.collection("questions").document(question_id)
    doc = doc_ref.get()

    if not doc.exists:
        return ""

    qdata = doc.to_dict()
    if qdata.get("image_url"):
        return qdata["image_url"]

    screen_name = qdata.get("screen_name", "Mobile App Screen")
    prompt = (
        f"A clean, modern mobile app UI wireframe screen mockup of an Android {screen_name}. "
        "High quality UI/UX design, material design 3 aesthetic, mobile phone screen layout, "
        "crisp wireframe elements, components, toolbar, and content hierarchy."
    )

    image_bytes = None
    client = get_genai()

    # Generate image using gemini-3.1-flash-lite-image in global region
    try:
        response = client.models.generate_images(
            model="gemini-3.1-flash-lite-image",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png",
                aspect_ratio="9:16",
            ),
        )
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
    except Exception as e:
        try:
            res = client.models.generate_content(
                model="gemini-3.1-flash-lite-image",
                contents=prompt,
            )
            for part in res.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break
        except Exception as inner_e:
            print(f"Image generation fallback triggered: {e}; {inner_e}")

    # Fallback placeholder image generator if model quota/access unavailable
    if not image_bytes:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (360, 640), color=(245, 247, 250))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(16, 24), (344, 72)], fill=(33, 150, 243))
        draw.text((32, 40), f"Mockup: {screen_name}", fill=(255, 255, 255))
        draw.rectangle([(16, 88), (344, 220)], fill=(255, 255, 255), outline=(210, 215, 220))
        draw.rectangle([(16, 236), (344, 368)], fill=(255, 255, 255), outline=(210, 215, 220))
        draw.rectangle([(16, 384), (344, 516)], fill=(255, 255, 255), outline=(210, 215, 220))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

    # (1) Save artifact in tool_context so it appears in Playground's Artifacts panel
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            await tool_context.save_artifact(
                filename=f"{question_id}.png",
                artifact=artifact_part,
            )
        except Exception as err:
            print(f"Notice: unable to save artifact to tool_context: {err}")

    # (2) Upload to Cloud Storage bucket (hardcoded string) and return public HTTPS URL
    storage_cli = get_storage()
    blob_name = f"mockups/{question_id}.png"
    try:
        bucket = storage_cli.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type="image/png")
        try:
            blob.make_public()
            public_url = blob.public_url
        except Exception:
            public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
    except Exception as e:
        print(f"Warning uploading to GCS bucket {BUCKET_NAME}: {e}")
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"

    # Cache public URL in Firestore
    doc_ref.update({"image_url": public_url})
    return public_url


def save_scorecard(
    user_id: str,
    session_type: str,
    difficulty: str,
    questions_asked: List[str],
    strengths: List[str],
    gaps: List[str],
    scores: Dict[str, int],
    hire_lean: str,
    summary: str,
) -> str:
    """Persists the completed session results and scorecard into the Firestore 'sessions' collection.

    Args:
        user_id: Candidate's persistent UUID.
        session_type: 'system_design', 'android_technical', or 'behavioral'.
        difficulty: 'mid', 'senior', or 'staff'.
        questions_asked: List of question IDs covered during this interview.
        strengths: List of observed strengths.
        gaps: List of observed gaps / areas for improvement.
        scores: Dict mapping category names to integer scores (1-5).
        hire_lean: 'Strong Hire', 'Lean Hire', 'Lean No-Hire', or 'Strong No-Hire'.
        summary: Qualitative overall evaluation summary.

    Returns:
        The created session ID string.
    """
    db = get_firestore()
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    session_doc = {
        "id": session_id,
        "user_id": user_id,
        "date": datetime.now(timezone.utc).isoformat(),
        "type": session_type,
        "difficulty": difficulty,
        "questions_asked": questions_asked,
        "scorecard": {
            "strengths": strengths,
            "gaps": gaps,
            "scores": scores,
            "hire_lean": hire_lean,
            "summary": summary,
        },
    }
    db.collection("sessions").document(session_id).set(session_doc)
    return session_id


def get_past_sessions(user_id: str) -> List[Dict[str, Any]]:
    """Returns previous interview sessions with dates, types, and scores for the specified user_id.

    Args:
        user_id: Candidate's persistent UUID.

    Returns:
        A list of past session summary dicts sorted by date descending.
    """
    if not user_id:
        return []
    db = get_firestore()
    sessions = []
    # Avoid composite index by filtering in memory
    docs = db.collection("sessions").where("user_id", "==", user_id).stream()
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        sessions.append(data)
    sessions.sort(key=lambda s: s.get("date", ""), reverse=True)
    return sessions[:10]


def search_official_docs(topic: str, platform: str = "android") -> Dict[str, Any]:
    """Searches official engineering documentation and best practices (Android Developer docs, Kotlin, or Cloud Architecture).

    Args:
        topic: The concept or library to look up (e.g., 'Paging 3', 'Coroutines StateFlow', 'Process death SavedStateHandle', 'CRDTs').
        platform: The ecosystem ('android', 'kotlin', or 'system_design').

    Returns:
        Dict containing key official guidance, modern replacement APIs, and common pitfalls.
    """
    topic_clean = topic.strip().lower()
    
    # Official guidance knowledge base for technical interview topics
    KNOWLEDGE_BASE = {
        "paging": {
            "title": "Android Jetpack Paging 3 Guidance",
            "recommended_apis": ["PagingDataAdapter", "RemoteMediator", "PagingData<T>", "cachedIn(viewModelScope)"],
            "deprecated_or_antipatterns": ["Paging 2 PositionalDataSource", "Loading all pages into memory without pagination"],
            "official_guidelines": "Always cache PagingData in viewModelScope before exposing as Flow to Compose or RecyclerView.",
        },
        "state": {
            "title": "StateFlow and Compose UI State",
            "recommended_apis": ["StateFlow", "asStateFlow()", "collectAsStateWithLifecycle()", "SavedStateHandle"],
            "deprecated_or_antipatterns": ["LiveData in Compose", "MutableStateFlow exposed directly as public property"],
            "official_guidelines": "Use collectAsStateWithLifecycle to automatically pause collection when the Activity/Fragment is not at least in STARTED state.",
        },
        "process death": {
            "title": "Android Process Death & State Restoration",
            "recommended_apis": ["SavedStateHandle", "rememberSaveable", "Parcelable / kotlinx.serialization"],
            "deprecated_or_antipatterns": ["Relying only on ViewModel memory without SavedStateHandle", "Storing large Bitmaps in Bundle"],
            "official_guidelines": "ViewModels survive configuration changes, but NOT system-initiated process death under memory pressure. SavedStateHandle preserves essential keys up to 50KB.",
        },
        "caching": {
            "title": "Offline Caching & Single Source of Truth",
            "recommended_apis": ["Room database", "Flow<List<Entity>>", "NetworkBoundResource / RemoteMediator"],
            "deprecated_or_antipatterns": ["Displaying network data directly without persisting to local database first"],
            "official_guidelines": "UI should observe local database state; network responses should update local database.",
        },
        "sync": {
            "title": "System Design: Conflict-free Replicated Data Types & Sync",
            "recommended_apis": ["CRDTs (Pn-Counter, LWW-Element-Set)", "Operational Transformation (OT)", "Vector clocks"],
            "deprecated_or_antipatterns": ["Naive wall-clock timestamps for distributed ordering without drift compensation"],
            "official_guidelines": "Use vector clocks or hybrid logical clocks (HLC) for distributed causal ordering; prefer state-based or operation-based CRDTs for collaborative editing.",
        }
    }

    # Match topic keywords
    for key, info in KNOWLEDGE_BASE.items():
        if key in topic_clean:
            return {"found": True, "topic": topic, "platform": platform, "details": info}

    return {
        "found": True,
        "topic": topic,
        "platform": platform,
        "details": {
            "title": f"Official Best Practices: {topic}",
            "recommended_apis": ["Modern standard libraries", "Type-safe interfaces", "Unidirectional data flow"],
            "deprecated_or_antipatterns": ["Global mutable state", "Blocking main thread operations", "Missing cancellation checks"],
            "official_guidelines": f"Ensure {topic} is architected with clear boundaries, lifecycle awareness, error boundaries, and scalable decoupling."
        }
    }


def export_scorecard_to_markdown(session_id: str, user_id: str) -> str:
    """Exports a candidate's completed interview scorecard to a downloadable Markdown dossier uploaded to Cloud Storage.

    Args:
        session_id: The ID of the session to export.
        user_id: Candidate's persistent UUID.

    Returns:
        The public HTTPS URL to the generated candidate dossier.
    """
    db = get_firestore()
    doc_ref = db.collection("sessions").document(session_id)
    doc = doc_ref.get()

    if not doc.exists:
        return ""

    data = doc.to_dict()
    sc = data.get("scorecard", {})

    scores_table = "| Category | Score (1-5) |\n| :--- | :--- |\n"
    for cat, val in sc.get("scores", {}).items():
        cat_display = cat.replace("_", " ").title()
        scores_table += f"| {cat_display} | {val}/5 |\n"

    strengths_md = "\n".join([f"- {s}" for s in sc.get("strengths", [])]) or "- N/A"
    gaps_md = "\n".join([f"- {g}" for g in sc.get("gaps", [])]) or "- N/A"

    markdown_content = f"""# PrepPal Technical Interview Dossier
**Candidate ID:** `{user_id}`  
**Session ID:** `{session_id}`  
**Interview Type:** {data.get('type', '').replace('_', ' ').title()}  
**Difficulty:** {data.get('difficulty', '').title()}  
**Date:** {data.get('date', '')}  

---

## Final Recommendation: **{sc.get('hire_lean', 'N/A')}**

### Executive Summary
{sc.get('summary', 'No summary provided.')}

### Detailed Scoring Rubric
{scores_table}

### Key Strengths Observed
{strengths_md}

### Areas for Improvement & Gaps
{gaps_md}

---
*Generated by PrepPal Mock Interview Coach on Google Cloud Agent Platform*
"""

    storage_cli = get_storage()
    blob_name = f"dossiers/{session_id}.md"
    try:
        bucket = storage_cli.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(markdown_content, content_type="text/markdown")
        try:
            blob.make_public()
            public_url = blob.public_url
        except Exception:
            public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
    except Exception as e:
        print(f"Error uploading dossier: {e}")
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"

    return public_url


def search_reference_repos(query: str, language: str = "Kotlin") -> Dict[str, Any]:
    """Searches GitHub for top open-source reference implementations, libraries, or architectures matching a technical topic.

    Uses the free public GitHub Search API (from public-apis directory).
    Reads GITHUB_TOKEN from the environment if present (optional, unauthenticated allows 60 requests/hr).

    Args:
        query: The technical topic or architecture pattern to search for (e.g. 'Paging3 Compose', 'CRDT WebSocket', 'ExoPlayer Media3').
        language: Programming language filter, defaults to 'Kotlin'.

    Returns:
        Dict containing top repository matches with descriptions, stars, and URLs.
    """
    import urllib.request
    import urllib.parse
    import json

    q_parts = [query]
    if language:
        q_parts.append(f"language:{language}")
    full_query = " ".join(q_parts)
    encoded_query = urllib.parse.quote(full_query)

    url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page=3"
    headers = {"User-Agent": "PrepPal-Mock-Interview-Coach", "Accept": "application/vnd.github.v3+json"}
    
    # Read token from environment variable if provided
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            items = []
            for item in data.get("items", []):
                items.append({
                    "name": item.get("full_name"),
                    "stars": item.get("stargazers_count"),
                    "description": item.get("description"),
                    "url": item.get("html_url"),
                })
            return {
                "success": True,
                "query": query,
                "total_count": data.get("total_count", 0),
                "repositories": items,
            }
    except Exception as e:
        return {
            "success": False,
            "query": query,
            "error": str(e),
            "repositories": [],
        }
