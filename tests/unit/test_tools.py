"""Unit tests for PrepPal tools."""

import pytest
from app.tools import DIFFICULTY_RANKS, get_question

def test_difficulty_ranks():
    assert DIFFICULTY_RANKS["mid"] == 1
    assert DIFFICULTY_RANKS["senior"] == 2
    assert DIFFICULTY_RANKS["staff"] == 3

def test_get_question_returns_valid_structure():
    q = get_question("android_technical", "mid", "test_mock_user")
    assert "id" in q
    assert "text" in q
    assert "type" in q
    assert "difficulty" in q
    assert "key_points" in q
    assert isinstance(q["key_points"], list)

def test_get_question_fallback_nearest():
    # If mid is requested for system_design
    q = get_question("system_design", "mid", "test_mock_user")
    assert q["type"] == "system_design"
    assert q["difficulty"] == "mid"

def test_search_official_docs():
    from app.tools import search_official_docs
    res = search_official_docs("process death", "android")
    assert res["found"] is True
    assert "SavedStateHandle" in str(res["details"])

def test_export_scorecard_to_markdown():
    from app.tools import export_scorecard_to_markdown, save_scorecard
    sid = save_scorecard(
        user_id="test_export_user",
        session_type="android_technical",
        difficulty="senior",
        questions_asked=["android_chat_screen"],
        strengths=["Good architecture"],
        gaps=["Missed retry backoff"],
        scores={"platform_knowledge": 4, "code_quality": 4, "edge_cases": 3, "communication": 5},
        hire_lean="Strong Hire",
        summary="Very strong technical candidate."
    )
    url = export_scorecard_to_markdown(sid, "test_export_user")
    assert "storage.googleapis.com" in url
    assert sid in url

def test_search_reference_repos():
    from app.tools import search_reference_repos
    res = search_reference_repos("paging3", "kotlin")
    assert res["success"] is True
    assert isinstance(res["repositories"], list)

@pytest.mark.asyncio
async def test_get_question_image_signature():
    from app.tools import get_question_image
    # Verify callable asynchronously without tool_context
    url = await get_question_image("android_news_feed")
    assert "https://" in url
    assert "mockups/android_news_feed.png" in url
