# Ascendra — AI-Powered Adaptive Exam Preparation & Mentorship Engine

**Ascendra** is an agentic AI educational platform designed to act as a personalized study mentor, adaptive schedule architect, and data-driven coach for high-stakes exam preparation (GATE, JEE, UPSC, GRE, etc.). It replaces rigid study timetables and unstructured syllabus lists with dynamic, AI-curated study roadmaps that adapt daily to a student's pace, confidence levels, and conceptual mastery.

---

## 🎯 The Problem It Solves

Preparing for extensive competitive examinations presents severe systemic challenges for modern learners:
1. **Syllabus Overwhelm & Lack of Structure:** Official syllabi are typically multi-page unstructured text documents. Students struggle to break them down into actionable milestones, estimate time requirements, or map conceptual dependencies (prerequisites).
2. **The Fragility of Static Timetables:** Traditional study schedules fail immediately upon contact with reality. If a student gets sick, experiences burnout, or underestimates the difficulty of a chapter, a static calendar collapses—fostering guilt, procrastination, and eventual abandonment.
3. **Absence of Personalized Mentorship:** Self-studying students lack daily diagnostic feedback. When they stumble on complex topics, there is no mentor to diagnose their misunderstandings, adjust tone based on stress, or recommend targeted remedial tactics.
4. **The Forgetting Curve & Unstructured Revision:** Reading a chapter once does not guarantee long-term recall. Without systematic spaced repetition and confidence tracking, critical knowledge decays rapidly before exam day.

---

## 🔄 The Ascendra Solution & Full Mentorship Loop

Ascendra solves these problems by executing a **continuous, four-stage mentorship loop** that accompanies the learner from day zero through exam day:

```
        ┌─────────────────────────────────────────────────────────┐
        │ 1. INGEST & ENRICH (Module 1)                           │
        │ Unstructured Syllabus → AI Tree & Prerequisite Mapping │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │ 2. ADAPTIVE ROADMAPPING (Module 2)                      │
        │ Select Module + Capacity → AI Generates Daily Schedule  │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │ 3. EXECUTION, MENTORSHIP & REPLANNING (Module 3)        │
        │ Daily Check-in & Reflection → AI Diagnostics & Feedback │
        │ Behind Pace or Skipped Days? → Deterministic Replanning │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │ 4. REFLECTION & RETENTION (Module 4)                    │
        │ Spaced Repetition (1/3/7/15/30d) + Confidence Triggers  │
        │ 14-Day Rolling Projections & AI Weekly/Monthly Coach     │
        └─────────────────────────────────────────────────────────┘
```

---

## 🏗️ System Architecture & Technology Stack

Ascendra is engineered with a scalable cloud-first architecture, uniting asynchronous Python APIs, MongoDB document modeling, high-speed open-source Large Language Models, and a responsive frontend design system.

### Core Stack
- **Backend Framework:** **FastAPI** (Python 3.10+) utilizing fully asynchronous concurrency (`async/await`) and Uvicorn ASGI servers.
- **Database & ODM:** **MongoDB Atlas (Cloud)** paired with **Beanie ODM** (asynchronous ODM built over Motor and Pydantic).
- **AI Infrastructure & Inference:** **Groq Cloud API** running open-source instruction-tuned models:
  - `llama-3.3-70b-versatile`: Utilized for deep pedagogical reasoning, diagnostic feedback, and strategic study planning.
  - `llama-3.1-8b-instant`: Utilized for rapid JSON schema formatting and low-latency syllabus structuring.
- **Frontend Web Application:** **React 19** powered by **Vite**, structured with **Tailwind CSS v4** (custom dark mode theme, glassmorphism, and micro-animations), and state-managed via **TanStack React Query v5** with automated Axios JWT interception.
- **Data Visualization & Charting:** **Recharts** for interactive timeline graphs and topic completion bars, supplemented by custom native SVG components (Readiness Gauge & GitHub-style Heatmap).
- **Background Scheduling:** **APScheduler** running asynchronous background daemon cron jobs for automated reviews and risk intervention checks.

---

## 📐 Key Architectural & System Design Decisions

### 1. Hybrid Topic Tree Schema in MongoDB
Syllabi naturally form deep hierarchies (Root Subjects $\rightarrow$ Modules/Units $\rightarrow$ Chapters $\rightarrow$ Leaf Topics). Storing trees in NoSQL without incurring expensive recursive joins is a classic challenge.
- **Our Design:** We implemented the **Hybrid (Parent Reference + Ancestor IDs Array)** pattern in [Topic](file:///home/harshita-patidar/Projects/Ascendra/backend/app/models/topic.py). Every node explicitly indexes both its immediate `parent_id` and an ordered array of all `ancestor_ids`.
- **Why It Matters:** Fetching an entire subject subtree requires just a single MongoDB indexed query (`{"ancestor_ids": root_id}`). When a student completes a leaf topic, completion percentages roll up instantly to the main exam progress bar in $O(1)$ database calls.

### 2. Specialized Multi-Agent Teamwork
Rather than relying on one monolithic general LLM prompt, Ascendra deploys five highly specialized AI agents working collectively under strict systemic constraints:
- **Agent 1 (Syllabus Parser):** Converts unstructured pasted text into strict nested JSON hierarchies.
- **Agent 2 (Difficulty & Prerequisite Estimator):** Evaluates leaf topics under an async concurrency semaphore (`Semaphore(3)`) to assign realistic study hour requirements, difficulty tiers (Easy/Medium/Hard), exam weightages, and conceptual prerequisite mappings.
- **Agent 4 (Study Planner):** Synthesizes a student's daily hour capacity, topic dependencies, and linked resources (video playlists, textbooks) into an actionable daily itinerary.
- **Agent 6 (Daily Diagnostic Mentor):** Evaluates daily check-ins and self-reflections, adapting tonal delivery (Encouraging, Urgent, Balanced) and prescribing targeted conceptual remediation.
- **Agent 8 (Strategic Analytics Coach):** Synthesizes weekly and monthly historical performance to deliver high-level executive study insights and priority focus areas.

### 3. Two-Layer AI Resilience & Self-Correction
Large Language Models occasionally generate malformed JSON or violate expected domain constraints. Ascendra guarantees operational reliability via a custom two-layer resilience pipeline in [validation.py](file:///home/harshita-patidar/Projects/Ascendra/backend/app/services/ai/validation.py):
- **Layer 1 (Network Resilience):** Utilizes `tenacity` exponential backoff to recover from transient network latencies or API rate limits.
- **Layer 2 (Schema Self-Correction):** All AI outputs are validated against strict Pydantic domain models. If the LLM violates a type constraint or omits a required field, the engine automatically catches the Pydantic `ValidationError`, injects the traceback directly into a corrective feedback prompt, and gives the LLM an opportunity to self-correct its JSON output before throwing an application error.
- **System Audit Logging:** Every LLM interaction is transparently wrapped by [logging_wrapper.py](file:///home/harshita-patidar/Projects/Ascendra/backend/app/services/ai/logging_wrapper.py), persisting prompts, model latencies, token usages, and raw completions directly to an `ai_interactions` MongoDB collection for debuggability and cost auditing.

### 4. Strict Separation of Deterministic Heuristics vs. AI Qualitative Narrative
A fundamental design tenet of Ascendra is that **LLMs should never perform complex arithmetic, scheduling math, or critical path sorting**.
- **Deterministic Replanning Engine:** When a student misses a day or skips tasks, rescheduling is performed by a pure algorithm in [replanning_service.py](file:///home/harshita-patidar/Projects/Ascendra/backend/app/services/replanning_service.py). It runs a deterministic **Topological Sort** (to honor prerequisite order) and uses capacity-fitting heuristics to redistribute unfinished work across future available days without violating daily hour limits. No AI hallucinations can ever displace a prerequisite or double-book a study day.
- **Isolated Predictive Analytics:** Readiness scores, 14-day rolling speed averages, projected completion dates, and categorizations of strong vs. weak topics are computed deterministically in Python ([prediction_service.py](file:///home/harshita-patidar/Projects/Ascendra/backend/app/services/prediction_service.py) & [analytics_service.py](file:///home/harshita-patidar/Projects/Ascendra/backend/app/services/analytics_service.py)). These verified numbers are then fed as read-only parameters into Agent 8, allowing the LLM to focus purely on qualitative mentoring narrative.

### 5. Reactive Spaced Repetition Engine
Ascendra implements a scientific spaced repetition memory model in [revision_service.py](file:///home/harshita-patidar/Projects/Ascendra/backend/app/services/revision_service.py) that seamlessly unifies static memory intervals with interactive confidence feedback:
- **Fixed Interval Schedules:** Upon initial topic completion, the engine automatically schedules five recurring review sessions at increasing intervals: **Day 1, Day 3, Day 7, Day 15, and Day 30**.
- **Low-Confidence Intervention:** When checking in or completing a revision, students rate their mastery on a 1–5 scale. If a student indicates conceptual fragility (rating $\le 2$ / "Confused" or "Shaky"), the system actively overrides the standard spacing and queues an urgent revision (`revision_number=0`) for the next day, presenting an inline interactive prompt to secure the user's explicit alignment.

---

## 🚀 Complete Feature Inventory

### Module 1: Exam Setup & Syllabus Engine
- **JWT Secure Auth:** User registration and login with bcrypt password hashing and token expiration handling.
- **Custom Exam Target Profiles:** Configure target exam dates, goal rank/score, experience level, and daily available hours.
- **AI Syllabus Parser (Agent 1):** Instantly converts messy pasted syllabus text into a clean hierarchical topic tree.
- **Interactive Syllabus Editor:** Rename topics, reorganize branches, and add or delete nodes before finalizing structure.
- **AI Topic Enrichment (Agent 2):** Automatically assigns estimated study hours, difficulty ratings, exam weightages, and conceptual prerequisite links.
- **Study Resource Library:** Catalog YouTube playlists, textbook chapter ranges, and question banks directly to your exam profile.

### Module 2: Adaptive Study Planning
- **Modular Roadmapping:** Select individual root topics (e.g., *Operating Systems*) and generate focused multi-day study itineraries.
- **AI Schedule Architect (Agent 4):** Crafts balanced daily study agendas marrying syllabus requirements with cataloged external resources.
- **Interactive Roadmap Customization:** Edit daily hour commitments and customize specific daily tasks before activating a module plan.

### Module 3: Daily Execution, Mentorship & Replanning
- **Today's Study Agenda:** Clean daily operational dashboard categorizing tasks by tag: 📖 **Study**, ✏️ **Practice**, 🔄 **Revision**, and ↩️ **Carry-over**.
- **Interactive Check-ins & Reflections:** Record actual hours spent, toggle task completions, and log textual reflections on daily stumbling blocks.
- **AI Diagnostic Feedback (Agent 6):** Receives instant diagnostic analysis on stumbling blocks, dynamic tonal adjustments (Encouraging/Urgent/Balanced), and action-oriented study tips.
- **Day Skipping & Deterministic Replanning:** Skip study days without fear; pure algorithms topologically reorder and redistribute unfinished items across future dates based on available capacity.

### Module 4: Predictive Analytics, Spaced Repetition & AI Coach
- **Default Analytics Dashboard:** Opening an exam instantly directs learners to their central analytics command center.
- **Visual Readiness Gauge:** SVG half-arc speedometer showing real-time readiness (0–100), paired with an explicit breakdown showing exactly how the score is weighted (40% Syllabus Done, 25% Consistency, 20% Pace, 15% Confidence).
- **Interactive Analytics Charts:**
  - *Hours Studied vs. Planned:* Area chart with **This Week / This Month / All Time** range switchers and planned vs. actual delta calculations.
  - *Topic Completion Breakdown:* Color-coded horizontal progress bars by root subject.
  - *Study Calendar Heatmap:* Custom 16-week × 7-day GitHub-style intensity grid showing daily study frequency.
- **Spaced Repetition Queue:** Dedicated queue grouping items by **⚡ Urgent** and **Due Today**, displaying days overdue and upcoming 7-day schedules.
- **Emoji Confidence Rating & Intervention:** Interactive 1–5 emoji rating system during revision check-offs, complete with intelligent inline popups offering extra scheduled review sessions for shaky concepts.
- **AI Weekly & Monthly Reviews (Agent 8):** Automated qualitative reports highlighting strong vs. weak performance areas, key priority callout actions, and realistic projected completion dates based on 14-day rolling study speeds.
- **Mid-Week Risk Alerting:** Background scheduler executes daily at 06:30 AM; missing 3 or more consecutive study days mid-week triggers an automatic high-priority intervention review.

---

## 🧪 Verification & Comprehensive Testing Guide

Ascendra is verified by a thorough automated test suite and exhaustive manual testing workflows:
- **Automated Test Suite:** Includes **72 unit tests across 10 test suites** running via `pytest`. Tests cover schema constraints, authentication encryption, AI validation retry loops, deterministic replanning heuristics, mathematical readiness formulas, and spaced repetition scheduling without needing database dependencies.
- **Manual End-to-End Testing:** Detailed step-by-step instructions for testing every feature in your web browser across all four modules.

For exhaustive setup instructions, environmental variable configurations, commands to run automated tests, and manual step-by-step browser testing guides, please consult **[TESTING.md](file:///home/harshita-patidar/Projects/Ascendra/TESTING.md)**.
