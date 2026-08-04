# Ascendra — Comprehensive System & End-to-End Testing Guide

This document is the authoritative testing and verification manual for **Ascendra**, an AI-powered adaptive exam preparation mentor and study planner. It covers system startup, execution of the 72 automated unit tests, and comprehensive manual walkthroughs to test every feature across all four core modules in a live environment.

---

## 1. Getting Started & System Startup

### Prerequisites
- **Python:** 3.10 or newer
- **Node.js & npm:** v18.0 or newer
- **Database:** A cloud MongoDB Atlas instance (or a local MongoDB instance running on port 27017)
- **AI Credentials:** A Groq API key (`gsk_...`) obtained free from [console.groq.com](https://console.groq.com/)

### Step 1: Configure Backend Environment
1. Open your terminal and navigate to the backend directory:
   ```bash
   cd /home/harshita-patidar/Projects/Ascendra/backend
   ```
2. Copy the example environment configuration file:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` in a text editor and configure your credentials:
   ```env
   MONGODB_URI="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"
   DATABASE_NAME="ascendra_production"
   GROQ_API_KEY="gsk_your_groq_api_key_here"
   JWT_SECRET_KEY="replace-this-with-a-secure-secret-key-of-at-least-32-characters"
   ```

### Step 2: Start the Backend Server (FastAPI)
From inside `/home/harshita-patidar/Projects/Ascendra/backend`:
```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8000
```
- The API server will launch at **http://localhost:8000**.
- Interactive Swagger OpenAPi documentation is automatically generated and accessible at **http://localhost:8000/docs**.
- During startup, the app connects to MongoDB, initializes Beanie ODM models, and activates background cron schedulers for daily/weekly/monthly analytics tasks.

### Step 3: Start the Frontend Application (React + Vite)
Open a **new terminal window** and navigate to the frontend folder:
```bash
cd /home/harshita-patidar/Projects/Ascendra/frontend
npm install
npm run dev
```
- The Vite development server will launch at **http://localhost:5173**. Open this URL in any modern web browser to access the application.

---

## 2. Automated Test Suite (Pytest)

Ascendra includes a fast, isolated unit test suite covering schema enforcement, JWT authentication, AI prompt validation loops, topic tree algorithms, study planning heuristics, mathematical analytics projections, and spaced repetition scheduling.

### How to Run Automated Tests
Open a terminal in `/home/harshita-patidar/Projects/Ascendra/backend` and execute:
```bash
python3 -m pytest -v
```
To run a specific test suite or test case:
```bash
python3 -m pytest tests/test_readiness_score.py -v
```

### Breakdown of Test Files & What They Verify
All 72 automated unit tests execute in under 1 second without requiring an active database or network calls to Groq:

| Test File | Module | What It Tests & Verifies |
| :--- | :---: | :--- |
| `test_auth.py` | **1** | Bcrypt password hashing, JWT creation/verification, expiration handling, and login validation schemas. |
| `test_exams.py` | **1** | Pydantic constraint validation (e.g., ensuring daily study hours fall strictly within 0 to 24), partial updates. |
| `test_syllabus_parsing.py` | **1** | O($N$) dictionary tree builder (`_build_nested`), strict schema compliance when parsing unstructured syllabus strings. |
| `test_resource_parser.py` | **2** | Extraction and structure formatting for video lectures, playlists, textbook reading chapters, and practice question banks. |
| `test_planner.py` | **2** | AI Agent 4 schedule constraints, hour capacity fitting, and multi-day study itinerary structures. |
| `test_daily_plan_generation.py`| **3** | Pipeline A daily task allocation, carry-over merging from skipped/partial previous days. |
| `test_replanning_algorithm.py` | **3** | Pure deterministic topological sorting, day-capacity refitting, and redistributing unfinished study items without AI hallucinations. |
| `test_validation.py` | **AI** | Two-layer resilience: verifies self-correcting prompt retries when LLM output violates Pydantic schema schemas. |
| `test_readiness_score.py` | **4** | Pure mathematical evaluation of the 0–100 Readiness Score formula (40% completion + 25% consistency + 20% pace + 15% confidence), zero inputs, and exam proximity urgency scaling. |
| `test_prediction_service.py` | **4** | Table-driven tests verifying completion date projections, on-track status, required daily study hours, and handling of zero rolling study days. |
| `test_revision_scheduling.py` | **4** | Spaced repetition interval consistency (Days 1, 3, 7, 15, 30), low-confidence check-in triggers (`revision_number=0`), and UI interactive re-revision prompt flags. |

---

## 3. End-to-End Feature Testing Workflow (Live Web Application)

Follow this structured workflow in your browser (**http://localhost:5173**) to test and verify every functional capability across all four modules.

---

### Module 1: Exam Setup & Syllabus Engine

#### Test 1.1: Account Registration & Authentication
1. Navigate to http://localhost:5173. You will be automatically redirected to `/login`.
2. Click **"Don't have an account? Sign up"**.
3. Create an account with an email and password (e.g., `student@ascendra.ai` / `password123`).
4. **Expected Result:** JWT token is stored in localStorage, and you are routed to your main Exam List page.

#### Test 1.2: Exam Creation & Goal Setting
1. Click **"+ Create New Exam"**.
2. Fill out the preparation attributes:
   - **Exam Name:** e.g., `GATE Computer Science 2027`
   - **Target Exam Date:** Choose a date 60–90 days in the future.
   - **Daily Available Study Hours:** Enter `4`.
   - **Experience Level:** Select `Intermediate`.
   - **Target Goal Score:** e.g., `All India Rank < 500`.
3. Click **"Save Exam & Proceed to Syllabus"**.
4. **Expected Result:** Exam is created and you are navigated directly to the Syllabus Setup interface.

#### Test 1.3: Unstructured Syllabus Ingest (AI Agent 1)
1. In the text area, paste an unstructured, messy exam syllabus snippet:
   ```text
   Unit 1: Operating Systems - Process Management, CPU Scheduling (FCFS, Round Robin), Deadlocks, Memory Management (Paging, Virtual Memory).
   Unit 2: Algorithms - Asymptotic Notations, Divide and Conquer (Merge Sort, Quick Sort), Dynamic Programming (Matrix Chain Multiplication, Longest Common Subsequence).
   ```
2. Click **"🤖 Parse with AI Mentor"**.
3. **Expected Result:** Agent 1 (Syllabus Parser) structures the text into a clean hierarchical tree (Roots -> Units -> Sub-topics -> Leaf topics).

#### Test 1.4: Interactive Syllabus Review & Tree Manipulation
1. In the displayed interactive topic tree, test manual overrides before committing:
   - **Edit Title:** Click the edit pencil next to "FCFS" and rename to `FCFS & SJF Scheduling`.
   - **Delete Topic:** Delete any unwanted topic or redundant node.
   - **Add Topic:** Add a missing topic directly under a parent node.
2. Click **"Save Syllabus Structure"**.
3. **Expected Result:** The structured topic tree is committed to MongoDB using the hybrid parent-reference + ancestor array schema.

#### Test 1.5: Topic Enrichment & Difficulty Estimation (AI Agent 2)
1. On your Exam Dashboard, click **"✨ Enrich Topics"**.
2. **Expected Result:** Agent 2 chunks root topics and evaluates each leaf topic, automatically appending:
   - **Difficulty Rating:** Easy, Medium, or Hard.
   - **Estimated Study Hours:** Realistic hour requirements per topic.
   - **Weightage:** Importance score relative to typical exam distributions.
   - **Prerequisites:** Automatic mapping (e.g., establishing that *Process Management* is a prerequisite for *CPU Scheduling*).

#### Test 1.6: Study Resource Repository
1. On the exam view, locate the study resources section or add resources when setting up a module.
2. Add reference materials:
   - **Video Playlist:** Title `Gate Smashers OS Lectures`, Units: `45 videos`.
   - **Textbook:** Title `Galvin Operating Systems (9th Ed)`, Units: `300 pages`.
3. **Expected Result:** Resources are permanently cataloged and linked for subsequent AI planning tasks.

---

### Module 2: Adaptive Study Planning & Roadmaps

#### Test 2.1: Initializing an Adaptive Module
1. From the exam navigation bar, click **"📋 Modules"** -> **"+ Start New Module"**.
2. Select a target root topic from your syllabus (e.g., `Operating Systems`).
3. Set your module boundaries:
   - **Start Date:** Today's date.
   - **Target Completion Date:** 10 days from today.
   - **Daily Available Hours:** `3.5`.
   - **Custom Study Preferences (Optional):** Enter `Focus heavily on Deadlock numericals and PYQs`.
4. Select relevant study resources from your repository and click **"Generate Study Plan"**.

#### Test 2.2: Reviewing the AI Study Plan (Agent 4)
1. Allow Agent 4 up to 10 seconds to compile your tailored roadmap.
2. **Expected Result:** You are presented with a day-by-day itinerary (Day 1 through Day 10). Each day lists:
   - Specific leaf topics to study or practice.
   - Concrete action tasks (e.g., *"Watch videos 1–4 of Gate Smashers OS"*, *"Solve 15 practice problems on CPU Scheduling"*).
   - Time allocations corresponding to your daily available capacity.

#### Test 2.3: Manual Roadmap Customization
1. Click **"Edit Day"** on Day 2 or Day 3.
2. Modify a task description or alter the estimated hours from `2.0` to `1.5`.
3. Save the edits.
4. Click **"Accept Plan & Activate"**.
5. **Expected Result:** The module transitions to an `active` status, and daily schedule tracking begins.

---

### Module 3: Daily Execution, Mentorship & Replanning

#### Test 3.1: Accessing Today's Study Schedule
1. From your active module card or exam navigation, open **"Today's Plan"** (`/today`).
2. **Expected Result:** Displays today's specific study itinerary, clearly separating tasks by category tags:
   - 📖 **Study** (learning concepts)
   - ✏️ **Practice** (problem solving)
   - 🔄 **Revision** (reviewing prior concepts)
   - ↩️ **Carry-over** (unfinished items brought over from earlier days)

#### Test 3.2: Submitting a Daily Check-In & Reflection
1. Click **"✏️ Submit Check-in"**.
2. In the check-in modal/form:
   - Toggle checkboxes for completed tasks.
   - Enter your **Actual Hours Studied** (e.g., input `3.0` hours against a planned `3.5`).
   - In the reflection box, enter a qualitative summary:
     ```text
     Understood process states and FCFS scheduling well, but struggled a bit with calculating wait times in Round Robin due to quantum slicing.
     ```
3. Click **"Complete Check-in & Get Feedback"**.

#### Test 3.3: AI Diagnostic Feedback & Tone Adaptation (Agent 6)
1. Upon submission, view your immediate check-in feedback card.
2. **Expected Result:** Agent 6 analyzes your performance and delivers structured advice:
   - **Tone Tag:** Adapts dynamically (e.g., `🌟 Encouraging` if on track, `⚠ Urgent` or `⚖ Balanced` if lagging).
   - **Diagnostic Insights:** Acknowledges your Round Robin calculation struggle and suggests concrete practice tactics.
   - **Actionable Advice:** Gives 2–3 precise micro-goals for your next study session.
3. Verify that completed topics have their status bubbled up to parent root topics, dynamically advancing your overall exam completion progress bar.

#### Test 3.4: Day Skipping & Deterministic Replanning
1. Navigate back to a module's **Today's Plan** on a new simulated day (or click **"Skip Today"**).
2. **Expected Result:** The day is marked as skipped. Unfinished study tasks are retained in the database.
3. When accessing tomorrow's plan or checking module status, the system applies **deterministic topological sorting** to safely shift unfinished tasks forward into future days with available hour capacity without exceeding your maximum daily workload limit.

---

### Module 4: Analytics Dashboard, Spaced Repetition & AI Coach

#### Test 4.1: Exam Dashboard & Readiness Score Verification
1. Click on an exam from your homepage to access its default landing page: **"📊 Dashboard"** (`/dashboard`).
2. Verify the **Readiness Gauge**:
   - Displays a colorful 0–100 SVG half-arc gauge indicating exam preparedness (*Needs Attention*, *Moderate*, *On Track*, or *Exam Ready*).
   - **Score Breakdown Panel:** Verify that directly below the gauge, the exact calculation weighting is clearly visible to the student:
     - **Syllabus Done:** 40% weight
     - **Consistency:** 25% weight
     - **Pace:** 20% weight
     - **Confidence:** 15% weight
3. Verify the **KPI Stat Cards**: Check that real-time values accurately report Overall Progress (%), Study Streak (days with longest streak), 30-Day Consistency (%), 14-Day Rolling Avg Daily Hours, Total All-Time Studied Hours, and Required Daily Hours to meet the exam deadline.

#### Test 4.2: Interactive Charting Engine (Recharts & Custom SVG)
1. **Hours Studied vs. Planned Timeline:**
   - Test the interactive range buttons: Click **"This Week"** (7 days), **"This Month"** (30 days), and **"All Time"**.
   - Hover over data points to verify the custom tooltip displays Planned Hours, Actual Hours, and the precise Delta vs. plan (`+0.5h` or `-1.0h`).
2. **Topic-wise Progress Bar Chart:**
   - Verify horizontal bars representing root topics colored by status (`Completed` in emerald, `In Progress` in amber, `Not Started` in slate).
3. **Study Calendar Heatmap (GitHub-style):**
   - Verify the custom 16-week × 7-day grid. Hover over colored squares to ensure native tooltips report exact dates and hours studied per day.

#### Test 4.3: Spaced Repetition Queue & Emoji Confidence Rating
1. Locate the **"🔄 Revisions Due"** card on the dashboard or navigate to **"Revisions"** (`/revision-queue`).
2. Notice items organized by **⚡ Urgent** (low confidence / overdue) and **Due Today**, generated automatically by the fixed spaced intervals (**Day 1, 3, 7, 15, and 30** after initial topic completion).
3. Click **"Done ✓"** on any listed revision item.
4. An inline rating selector expands: **"How confident do you feel?"**.
5. Test selecting a confidence rating from 1 to 5 using the emoji indicators:
   - `😕 1 - Confused`
   - `😐 2 - Shaky`
   - `🙂 3 - Okay`
   - `😊 4 - Good`
   - `🎯 5 - Nailed it!`
6. Click **"Mark Complete"**. If rated $\ge 3$, the task is cleanly finalized, and the next scheduled interval is queued in the future.

#### Test 4.4: Interactive Low-Confidence Re-Revision Prompt
1. Click **"Done ✓"** on another due revision item.
2. Intentionally select a low rating of **1 (Confused)** or **2 (Shaky)** and click **"Mark Complete"**.
3. **Expected Result:** Instead of silently auto-scheduling, an explicit warning prompt pops up:
   - *"Still a bit shaky? 🤔 You rated your confidence low. Would you like to schedule another revision for tomorrow?"*
4. Click **"Yes, schedule one more"**.
5. Verify that an urgent extra revision (`revision_number=0`, triggered by `low_confidence`) is scheduled for tomorrow and highlighted with an urgent electrical badge in your queue.

#### Test 4.5: AI Weekly Reviews & Mid-Week Risk Alerting (Agent 8)
1. From the dashboard header, click **"📋 Weekly Review"** (`/weekly-reviews`).
2. Click **"✨ Generate Now"** to test Agent 8 (AI Analytics Coach) on demand (normally scheduled via cron every Sunday at 23:00).
3. **Expected Result:** A comprehensive review card generated by Agent 8 appears containing:
   - **Tonal Assessment:** e.g., `Encouraging` or `Urgent`.
   - **Performance Stats Grid:** Planned vs. Actual hours, Topics completed, Active study days.
   - **Strong vs. Weak Topics:** Visual chips categorizing topics where you excelled vs. areas requiring remedial attention.
   - **AI Narrative:** Qualitative analysis without raw mathematical computation (since metrics are precomputed in Python).
   - **Key Recommendation:** A prominent callout box defining your single most critical objective for the coming week.
4. *Note on Mid-Week Risk Alerts:* The background scheduler runs daily at 06:30 AM. If a student misses 3+ consecutive scheduled study days mid-week, an urgent risk review tagged with a red `Risk Alert` badge is automatically generated to intervene and reorient the student.

#### Test 4.6: AI Monthly Reviews & Projections
1. Navigate to **"Monthly Reviews"** (`/monthly-reviews`).
2. Click **"✨ Generate This Month"** to simulate the monthly cron job (which runs on the 1st of each month at 01:00).
3. Verify that the monthly review clearly details:
   - **Projected Finish Date:** Calculated from your 14-day rolling average study pace.
   - **Pace Guidance:** An info bar explicitly informing you if your projected finish date lands safely before your scheduled exam date, or if you need to boost your daily hours to finish on time.

---

## 4. Advanced Debugging & Database Verification

If you need to inspect raw application data during testing, you can examine your MongoDB collections directly via MongoDB Compass, Atlas Explorer, or `mongosh`:

- `users`: User profiles and hashed bcrypt password payloads.
- `exams`: Active study targets, total study capacities, and archived soft-deleted entries.
- `topics`: Hierarchical syllabus structures containing `parent_id`, `ancestor_ids`, and completion percentages.
- `module_starts`: Active study roadmaps with generated itineraries (`module_plan_days`).
- `daily_reports` & `study_logs`: Submitted user check-ins, recorded hours, and completed units.
- `revision_schedules`: Spaced repetition tracking documents (`revision_number` 0 to 5) and `days_overdue` states.
- `confidence_logs`: Historical logs of topic user ratings (1–5) and contextual tags (`checkin` vs. `revision_done`).
- `weekly_reviews` & `monthly_reviews`: Persisted AI summaries, strong/weak topic mappings, and suggested actions.
- `ai_interactions`: Permanent system audit log containing every LLM call made across all agents, including raw system/user prompt payloads, model latencies, token usages, and Groq JSON responses.
