# My agent: Mock Interview Coach (PrepPal)

One-liner: A realistic conversational mock interview coach for software engineers that runs full interview sessions, recalls cross-session weak areas using Memory Bank, references mobile UI screen mockups, and grades performance with an A2UI scorecard.

## 1. User Identity & Session Continuity
- **Frontend Identity**: When the custom frontend is built, it passes a stable `user_id` (a UUID generated on first load and stored in `localStorage`) so that Memory Bank facts and past sessions persist across visits.
- **Playground Testing**: Explicit user identity is not needed during local Playground testing.

## 2. Conversation Flow & Interviewer Persona
- **Setup**: User selects or states their target role (e.g. Senior Android Engineer), interview type (System Design, Android/Kotlin Technical, or Behavioral), and difficulty (Mid, Senior, Staff).
- **Memory Recall at Session Start**:
  - Before asking the first question, the agent retrieves memories for the candidate from Memory Bank.
  - If previous weak areas or gaps exist, the agent acknowledges them and targets them during the interview.
- **Interviewer Behavior**:
  - Realistic senior technical interviewer persona.
  - Asks one question at a time.
  - Asks probing follow-up questions based on what the candidate said or left out.
  - Never gives away the answer or provides hints prematurely.
- **Completion & Scorecard**:
  - When the candidate indicates they are finished (says "done" or wraps up), the agent produces a comprehensive scorecard:
    - Strengths identified
    - Gaps / weak areas for improvement (stated clearly in conversation so Memory Bank extracts them)
    - 1–5 score per area (tailored by interview type)
    - Hire / No-hire lean (Strong Hire, Lean Hire, Lean No-Hire, Strong No-Hire)
  - Calls `save_scorecard` to persist the session in Firestore.
  - Renders the scorecard as an **A2UI card**.

## 3. Scorecard Areas by Interview Type
Scores are rated 1–5 for each specific category:
- **System Design**:
  - Architecture
  - Scalability
  - Trade-offs
  - Communication
- **Android / Kotlin Technical**:
  - Platform Knowledge
  - Code / Architecture Quality
  - Edge Cases
  - Communication
- **Behavioral**:
  - Situation Clarity
  - Ownership
  - Impact
  - Reflection

## 4. Memory (Cross-Session via Vertex AI Memory Bank)
- Uses Memory Bank's **automatic extraction** as set up by the `memory-bank-setup` skill (`PreloadMemoryTool` + `after_agent_callback` invoking `add_session_to_memory()`).
- Weak areas and candidate gaps from the scorecard must be stated clearly in the conversation so Memory Bank automatically extracts and attributes them to the user.
- At the start of subsequent sessions, the agent recalls these stored weak areas to tailor questions and follow-ups.

## 5. UI (A2UI & Plain Chat UI)
- The frontend stays the lab's **plain chat UI** (no custom sidebar or timer).
- **A2UI Components**:
  - **Scorecard**: Rendered as an **A2UI card** displaying scores (1–5), hire lean, strengths, gaps, and the mobile screen mockup image (if applicable).
  - **Past Sessions**: Rendered as an **A2UI table** showing dates, interview types, difficulty, and scores.

## 6. Database Schema (Firestore)
- **`questions` collection**:
  - `id`: Unique identifier
  - `text`: Question prompt / scenario
  - `type`: `system_design` | `android_technical` | `behavioral`
  - `difficulty`: `mid` | `senior` | `staff`
  - `key_points`: List of expectations/signals a strong answer must cover
  - `image_url`: Optional public Cloud Storage URL for UI screen mockup
  - `screen_name`: Associated app screen (for Android questions, e.g. "News Feed", "Checkout Flow")
- **`sessions` collection**:
  - `id`: Session UUID
  - `user_id`: Candidate identifier
  - `date`: Timestamp
  - `type`: Interview type
  - `difficulty`: Selected difficulty
  - `questions_asked`: List of question IDs
  - `scorecard`: { strengths, gaps, scores (1-5 per rubric area), hire_lean, summary }

## 7. Tools
- `get_question(type, difficulty, user_id)`:
  - Picks an interview question from the bank, avoiding questions the user has already seen.
  - Fallback cascade: If nothing matches the exact type + difficulty (or user has seen them all):
    1. Fall back to nearest difficulty in that type.
    2. Fall back to any unseen question of that type.
    3. Allow repeats if all questions of that type have been seen.
- `get_question_image(question_id)`:
  - For Android/Kotlin technical questions only.
  - Returns existing `image_url` if present.
  - Otherwise, generates a mobile app screen mockup using **`gemini-3.1-flash-lite-image` in the `global` region**, uploads it to Cloud Storage, saves the public URL to Firestore, and returns it. (Generated once per question and reused).
- `save_scorecard(...)`: Persists the structured scorecard to the Firestore `sessions` collection.
- `get_past_sessions(user_id)`: Returns historical sessions with dates, types, and scores for the specified `user_id`.

## 8. Seed Data (12 Starter Questions)
Every interview type includes at least one question at each difficulty (`mid`, `senior`, `staff`):

### Android / Kotlin Technical (4 questions with UI screen context)
1. **News Feed Screen** (`difficulty: mid`): Infinite scrolling list, pagination, image caching, configuration changes, RecyclerView / Jetpack Compose.
2. **Chat Screen** (`difficulty: senior`): Real-time messaging, WebSocket lifecycle, optimistic UI updates, SQLite/Room persistence, background sync.
3. **Checkout Flow** (`difficulty: senior`): Multi-step checkout, payment validation, coroutine exception handling, process death state restoration.
4. **Media Player / Audio Stream** (`difficulty: staff`): Background playback service, notification controls, lifecycle-aware coroutines, audio focus, low-latency streaming pipeline.

### System Design (4 questions)
1. **Offline-First Sync Engine** (`difficulty: mid`): Local persistence, delta sync with server, conflict resolution (last-write-wins vs client prompt).
2. **Real-Time Collaborative Document Editor** (`difficulty: senior`): Operational Transformation / CRDTs, concurrency control, connection drop recovery.
3. **High-Throughput Push Notification Service** (`difficulty: senior`): 1M notifications/minute, device registry, rate limiting, provider failover (FCM/APNs).
4. **Mobile Crash Reporting & Observability SDK** (`difficulty: staff`): In-process signal handling, stack trace symbolication, network/battery budgeting, sampled telemetry ingestion.

### Behavioral (4 questions)
1. **Technical Disagreement** (`difficulty: mid`): Handling a technical disagreement with a teammate or lead on framework/library choices.
2. **Production Incident Post-Mortem** (`difficulty: senior`): Diagnosing and mitigating a high-severity production issue under pressure, and driving blameless retrospectives.
3. **Mentorship & Leveling Up** (`difficulty: senior`): Mentoring and helping an underperforming or junior engineer navigate a complex technical hurdle.
4. **Cross-Functional Scope & Trade-offs** (`difficulty: staff`): Negotiating engineering trade-offs and technical debt remediation against aggressive product timelines with executives.

## 9. Tool & Feature Scope
- **Memory**: Vertex AI Memory Bank automatic extraction (`memory-bank-setup` pattern).
- **Tools**: `get_question`, `get_question_image`, `save_scorecard`, `get_past_sessions`.
- **Image gen**: `gemini-3.1-flash-lite-image` in `global` region only.
- **UI**: Plain chat UI with A2UI cards for Scorecards and A2UI tables for Past Sessions.
