"""Seed starter questions into Firestore questions collection."""

import os
from google.cloud import firestore

# Hardcoded string as required for Agent Platform Firestore compatibility
PROJECT_ID = "qwiklabs-gcp-04-f2a70fd871e0"

QUESTIONS = [
    # --- Android / Kotlin Technical (4 questions) ---
    {
        "id": "android_news_feed",
        "type": "android_technical",
        "difficulty": "mid",
        "screen_name": "News Feed Screen",
        "text": (
            "Design the client architecture for a social media News Feed screen on Android. "
            "The feed contains text, user avatars, and media cards with infinite scroll pagination. "
            "How do you structure the UI layer (Jetpack Compose or RecyclerView), manage state with ViewModel, "
            "handle image loading/caching, and survive configuration changes?"
        ),
        "key_points": [
            "Use Jetpack Compose (LazyColumn) or RecyclerView with DiffUtil/ListAdapter",
            "Use Paging 3 library with RemoteMediator for network + local Room cache",
            "State management via ViewModel with StateFlow / Compose State",
            "Image caching strategy using Coil or Glide with memory/disk caching",
            "Lifecycle handling and preserving scroll state across configuration changes"
        ],
        "image_url": None
    },
    {
        "id": "android_chat_screen",
        "type": "android_technical",
        "difficulty": "senior",
        "screen_name": "Real-Time Chat Screen",
        "text": (
            "You are building a 1:1 real-time messaging screen on Android with WebSocket connectivity. "
            "How do you implement optimistic UI updates for sent messages, manage WebSocket connection "
            "lifecycle across app background/foreground transitions, and ensure zero message loss using Room DB?"
        ),
        "key_points": [
            "Optimistic message insertion in Room with a PENDING status, updating to SENT on server ACK",
            "Process lifecycle observer (DefaultLifecycleObserver / ProcessLifecycleOwner) for WebSocket disconnect/reconnect with backoff",
            "Single source of truth pattern: UI observes Room Flow, network writes directly to Room",
            "Kotlin Coroutines / Flow with SupervisorJob and proper cancellation scopes",
            "Handling network flapping, message deduplication by client-generated message UUID"
        ],
        "image_url": None
    },
    {
        "id": "android_checkout_flow",
        "type": "android_technical",
        "difficulty": "senior",
        "screen_name": "Checkout Flow Screen",
        "text": (
            "Architect a multi-step Checkout screen on Android with shipping address, payment method selection, "
            "and a 'Place Order' action. How do you prevent double-submissions, manage complex validation state, "
            "handle payment gateway coroutine failures, and restore state after low-memory process death?"
        ),
        "key_points": [
            "SavedStateHandle in ViewModel to persist form drafts across process death",
            "Button debounce and idempotent order tokens sent with API requests to prevent double charges",
            "Robust Kotlin Coroutine ExceptionHandler, distinct domain errors (recoverable vs fatal)",
            "Unidirectional Data Flow (UDF) with immutable UI State sealed interface",
            "Secure handling of payment tokens in memory (never storing raw CVV/card info locally)"
        ],
        "image_url": None
    },
    {
        "id": "android_media_player",
        "type": "android_technical",
        "difficulty": "staff",
        "screen_name": "Media Player & Audio Stream Screen",
        "text": (
            "Architect a high-performance audio streaming screen and background playback engine on Android. "
            "How do you structure Media3 / MediaSessionService, handle audio focus changes (e.g. incoming phone call), "
            "manage lock screen and notification media controls, and minimize battery consumption during background streaming?"
        ),
        "key_points": [
            "Use MediaSessionService / MediaLibraryService with ExoPlayer from Jetpack Media3",
            "AudioAttributes and automatic AudioFocus management with transient ducking/pausing",
            "Foreground service notification with MediaStyle and playback actions (play, pause, seek)",
            "WakeLock / WifiLock minimization and audio buffer chunking for battery optimization",
            "Handling Bluetooth headset disconnects (BECOMING_NOISY intent) and hardware buttons"
        ],
        "image_url": None
    },

    # --- System Design (4 questions) ---
    {
        "id": "sys_offline_sync",
        "type": "system_design",
        "difficulty": "mid",
        "screen_name": None,
        "text": (
            "Design an offline-first synchronization engine for a mobile note-taking application. "
            "Users can edit notes offline on multiple devices. How do you synchronize changes back to the cloud, "
            "track mutations, and resolve conflicting edits to the same note?"
        ),
        "key_points": [
            "Local mutation queue / outbox pattern with sequence IDs and timestamps",
            "Sync protocols: delta-based syncing vs snapshot sync using change logs",
            "Conflict resolution strategies: Last-Write-Wins (LWW), version vectors, or candidate prompt",
            "Network batching, exponential backoff, and idempotent server APIs",
            "Security: client encryption and server authorization"
        ],
        "image_url": None
    },
    {
        "id": "sys_collab_doc",
        "type": "system_design",
        "difficulty": "senior",
        "screen_name": None,
        "text": (
            "Design a real-time collaborative document editor (like Google Docs) supporting dozens of simultaneous editors. "
            "Explain your approach to concurrency control, conflict resolution, document storage, and network transport."
        ),
        "key_points": [
            "Operational Transformation (OT) or Conflict-free Replicated Data Types (CRDTs)",
            "WebSocket / WebTransport duplex communication with a central coordination server",
            "Document partitioning, memory snapshots, and append-only edit logs in storage",
            "Presence service (cursor tracking, active user heartbeats via Redis)",
            "Graceful handling of high-latency clients and reconnection replay"
        ],
        "image_url": None
    },
    {
        "id": "sys_push_notifications",
        "type": "system_design",
        "difficulty": "senior",
        "screen_name": None,
        "text": (
            "Design a global push notification service capable of dispatching 1 million notifications per minute to iOS and Android devices. "
            "Cover the device token registry, message ingestion, queuing, third-party provider integration (APNs/FCM), and rate limiting."
        ),
        "key_points": [
            "Device registration service with distributed key-value storage (e.g. Cassandra / DynamoDB)",
            "Kafka / PubSub message broker with priority queues (transactional vs promotional)",
            "Worker pools connecting via HTTP/2 persistent connections to FCM and APNs",
            "Per-user notification frequency capping and quiet-hours rate limiting",
            "Telemetry for delivery status, retry policies with dead-letter queues (DLQ)"
        ],
        "image_url": None
    },
    {
        "id": "sys_crash_sdk",
        "type": "system_design",
        "difficulty": "staff",
        "screen_name": None,
        "text": (
            "Design a mobile crash reporting and telemetry SDK to be embedded in top-tier apps with hundreds of millions of daily active users. "
            "How do you safely capture in-process fatal crashes (including native NDK crashes and ANRs), guarantee crash delivery without losing data, "
            "and enforce strict client battery, memory, and network budgets?"
        ),
        "key_points": [
            "UncaughtExceptionHandler for JVM crashes and sigaction signal handler with alternate stack for NDK/C++ crashes",
            "ANR watchdog thread monitoring main thread Looper queue",
            "Writing crash report synchronously to disk before process death; uploading on next app launch",
            "Adaptive sampling, compression, and strict quota budgets for network and battery",
            "Server ingestion pipeline with symbolication service (ProGuard mapping files / debug symbols)"
        ],
        "image_url": None
    },

    # --- Behavioral (4 questions) ---
    {
        "id": "behav_tech_disagreement",
        "type": "behavioral",
        "difficulty": "mid",
        "screen_name": None,
        "text": (
            "Tell me about a time you strongly disagreed with a team member or tech lead regarding an architectural decision, "
            "framework choice, or implementation approach. How did you handle the situation, and what was the outcome?"
        ),
        "key_points": [
            "Clear articulation of the technical disagreement and differing perspectives",
            "Data-driven evaluation (prototyping, benchmarking, trade-off matrix) rather than emotional arguments",
            "Professional communication, active listening, and empathy",
            "Disagree and commit: backing the final decision wholeheartedly once made",
            "Lessons learned or post-implementation validation"
        ],
        "image_url": None
    },
    {
        "id": "behav_prod_incident",
        "type": "behavioral",
        "difficulty": "senior",
        "screen_name": None,
        "text": (
            "Describe a high-severity production outage or critical bug you were responsible for or had to resolve under intense pressure. "
            "Walk me through your thought process, immediate mitigation steps, communication with stakeholders, and the subsequent post-mortem."
        ),
        "key_points": [
            "Fast triage: prioritize immediate mitigation (rollback, feature flag disable) over debugging in production",
            "Clear, calm communication with incident commanders, customer support, and stakeholders",
            "Root-cause analysis (5 Whys) during the blameless post-mortem",
            "Action items created to prevent recurrence (guardrails, alerting, automated tests)",
            "Accountability and personal reflection"
        ],
        "image_url": None
    },
    {
        "id": "behav_mentorship",
        "type": "behavioral",
        "difficulty": "senior",
        "screen_name": None,
        "text": (
            "Give me an example of a time you mentored a junior or struggling engineer through a difficult technical problem or project. "
            "How did you tailor your mentorship to their learning style, and how did you measure their growth?"
        ),
        "key_points": [
            "Identifying underlying root causes (confidence, technical fundamentals, domain context)",
            "Guiding with Socratic questioning and pairing rather than dictating solutions",
            "Setting milestone goals and providing frequent, constructive feedback",
            "Fostering psychological safety and autonomy",
            "Measurable outcome: the engineer successfully delivering and growing independently"
        ],
        "image_url": None
    },
    {
        "id": "behav_scope_tradeoffs",
        "type": "behavioral",
        "difficulty": "staff",
        "screen_name": None,
        "text": (
            "Tell me about a situation where you had to negotiate scope, technical debt, and delivery timelines with product managers "
            "or executive leadership under tight business constraints. How did you balance speed with code quality and long-term sustainability?"
        ),
        "key_points": [
            "Translating technical risks and technical debt into business impact and velocity metrics",
            "Phased delivery approach: MVP with clearly documented non-fatal compromises, followed by hardening",
            "Influencing stakeholders through collaborative roadmapping and risk mitigation plans",
            "Maintaining high ethical standards for security, data privacy, and reliability",
            "Successful business delivery while safeguarding team sustainability and architecture"
        ],
        "image_url": None
    }
]

def seed():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    batch = db.batch()
    coll_ref = db.collection("questions")

    for q in QUESTIONS:
        doc_ref = coll_ref.document(q["id"])
        batch.set(doc_ref, q)

    batch.commit()
    print(f"Successfully seeded {len(QUESTIONS)} questions into Firestore 'questions' collection.")

if __name__ == "__main__":
    seed()
