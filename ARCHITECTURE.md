# ARCHITECTURE.md

## 1. Overview

The Intelligence Briefing System is a Python-based automated research pipeline that fetches articles from RSS feeds and web pages, summarizes them using OpenAI's GPT-4o model, cross-verifies factual claims against independent sources, and produces a plain-text intelligence briefing report. It solves the problem of manual research aggregation by automating the entire workflow from source collection to final report delivery via email. The system is not agentic in the tool-calling sense — workers execute in a fixed, predetermined order.

## 2. How It Works (End-to-End Flow)

When you run `python orchestrator.py "AI regulation"`, the system executes this sequence:

```
python orchestrator.py "topic"
         │
         ├──> check_environment()           # Validates OPENAI_API_KEY present
         ├──> store.initialize_db()         # Creates SQLite tables if missing
         ├──> create_plan(topic)            # Returns TaskPlan with focus_areas and steps
         │         └──> OpenAI API call     # GPT-4o generates research angles
         │
         ├──> store.create_run(topic)       # Inserts row into runs table, returns run_id
         │
         ├──> web_collector.collect_all()   # For each URL in sources.txt:
         │         ├──> fetch_from_source() #   - Try direct RSS parse (feedparser)
         │         ├──> _find_feed_link()   #   - Discover RSS link in HTML <head>
         │         └──> scrape HTML body    #   - Fallback to raw text extraction
         │         └──> store.save_article()# Persist to articles table
         │
         ├──> evaluate_evidence()           # Check if articles cover plan.focus_areas
         │         └──> OpenAI API call     # GPT-4o evaluates coverage gaps
         │
         ├──> summarizer.summarize_all()    # For each article:
         │         └──> summarize_article() #   - OpenAI API call with focus_areas injected
         │         └──> store.save_summary()#   - Persist to summaries table
         │
         ├──> verifier.extract_and_verify_claims()
         │         ├──> extract_claims()    # OpenAI identifies 3-5 key claims
         │         └──> verify_claim()      # For each claim:
         │               └──> OpenAI API    #   - Verify using summaries EXCEPT source
         │               └──> store.save_verification()
         │
         ├──> writer.write_briefing()       # OpenAI generates final report
         │         └──> store.save_report() # Persist to reports table
         │
         └──> emailer.send_report()         # SMTP delivery (optional, if EMAIL_TO set)
```

**Key functions (in execution order):**
1. `orchestrator.check_environment()` → validates env vars
2. `planner.create_plan()` → returns `TaskPlan` object
3. `orchestrator._gate_collection()` → halts if < 2 articles
4. `planner.evaluate_evidence()` → warns on coverage gaps
5. `summarizer.summarize_all()` → batch summarization
6. `verifier.extract_and_verify_claims()` → cross-source fact-checking
7. `writer.write_briefing()` → final report assembly
8. `emailer.send_report()` → SMTP transmission

## 3. Architecture: Planner–Orchestrator–Worker Pattern

**Division of Responsibility:**

- **Planner (`planner.py`):** Decides *what* to research. Produces a `TaskPlan` containing `focus_areas` (3-4 research angles) and `steps` (execution order). After collection, evaluates whether articles sufficiently cover planned angles via `evaluate_evidence()`. Does not execute tasks — only plans and audits.

- **Orchestrator (`orchestrator.py`):** The dispatcher. Calls workers in fixed order: plan → collect → evaluate → summarize → verify → write → email. Implements quality gates (`_gate_collection`, `_gate_evidence`, `_gate_verification`) that halt or warn when thresholds fail. Manages `run_id` lifecycle and status updates.

- **Workers (`workers/`):** Execute single-purpose tasks. Each worker is stateless — receives inputs, calls OpenAI or HTTP endpoints, returns results. Workers do not communicate directly with each other. Results flow back to the orchestrator, which passes them to the next worker.

- **Storage (`store/sqlite_store.py`):** Persistence layer. All workers write to SQLite via `store.*` functions. No worker reads from the database — data flows forward through the orchestrator's return values.

**This is a pipeline, not an agent:**
The execution order is hardcoded. Workers cannot call other workers. There is no dynamic task generation or tool invocation. The planner's `steps` list is informational, not executable.

## 4. File-by-File Reference

### Entry Points

#### `orchestrator.py`
**Purpose:** Main entry point that controls the full pipeline workflow.

**Key functions:**
- `run(topic, email_to, verbose)` — executes 6-step pipeline from plan to email
- `check_environment()` — validates `REQUIRED_VARS` (just `OPENAI_API_KEY`)
- `_gate_collection(articles, run_id)` — halts if < 2 articles collected
- `_gate_evidence(topic, focus_areas, articles)` — warns on coverage gaps
- `_gate_verification(verifications)` — warns if all claims unverifiable

**External dependencies:** OpenAI (via workers), SQLite, SMTP (optional)

#### `planner.py`
**Purpose:** Generates research plan and evaluates evidence coverage.

**Key classes:**
- `TaskPlan` — data container with `topic`, `focus_areas` (list), `steps` (list)

**Key functions:**
- `create_plan(topic)` — OpenAI API call to generate focus areas and steps
- `evaluate_evidence(topic, focus_areas, articles)` — returns `(sufficient: bool, reason: str, missing_areas: list)`

**External dependencies:** OpenAI (GPT-4o via `utils.retry.call_with_retry`)

### Workers

#### `workers/web_collector.py`
**Purpose:** Fetches article content from URLs in `sources.txt`.

**Key functions:**
- `collect_all(run_id, store, verbose)` — batch fetch all sources, save to DB
- `fetch_from_source(url)` — tries (1) direct RSS, (2) HTML feed discovery, (3) HTML scrape
- `_parse_feed(feed_url)` — uses `feedparser` to extract up to 5 articles per feed
- `_find_feed_link(page_url, soup)` — searches `<link>` tags for RSS/Atom URLs
- `load_sources()` — reads `sources.txt`, filters `#` comments

**External dependencies:** HTTP (requests), feedparser, BeautifulSoup

**Constants:**
- `MAX_RSS_ARTICLES = 5` — articles per feed
- `MAX_CONTENT_CHARS = 12000` — content truncation limit

#### `workers/summarizer.py`
**Purpose:** Creates plain-text summaries of articles using OpenAI.

**Key functions:**
- `summarize_all(articles, topic, focus_areas, run_id, store, verbose)` — batch process
- `summarize_article(title, content, topic, focus_areas)` — single summary (3-5 sentences)

**External dependencies:** OpenAI (GPT-4o, max_tokens=400, temperature=0.3)

**Improvement note:** `focus_areas` from planner are injected into every prompt.

#### `workers/verifier.py`
**Purpose:** Extracts key claims and cross-verifies against independent sources.

**Key functions:**
- `extract_and_verify_claims(summaries, topic, run_id, store, verbose)` — orchestration
- `extract_claims(summaries, topic)` — OpenAI call, returns `[(claim, source_idx)]`
- `verify_claim(claim, source_idx, summaries)` — verifies using summaries *excluding* source_idx

**External dependencies:** OpenAI (GPT-4o, temperature=0.1-0.2)

**Improvement note:** Claims are tagged with their source index. Verification excludes that source to prevent self-confirmation. Falls back gracefully if only one summary exists.

#### `workers/writer.py`
**Purpose:** Composes final intelligence briefing report.

**Key functions:**
- `write_briefing(topic, summaries, verifications, focus_areas, run_id, store, verbose)` — assembles report
- `_confidence_note(verifications)` — injects CAUTION message when verification is weak

**External dependencies:** OpenAI (GPT-4o, max_tokens=2000, temperature=0.4)

**Report structure (hardcoded in prompt):**
- EXECUTIVE SUMMARY
- KEY FINDINGS
- DETAILED ANALYSIS (addresses `focus_areas`)
- VERIFIED CLAIMS (with verdicts)
- SOURCES

### Storage

#### `store/sqlite_store.py`
**Purpose:** All database read/write operations.

**Key functions:**
- `initialize_db()` — creates tables via `executescript` if not exist
- `create_run(topic)` — inserts into `runs`, returns `run_id`
- `update_run_status(run_id, status)` — sets `status` to 'running', 'complete', or 'failed'
- `save_article(run_id, url, title, content)` — returns `article_id`
- `save_summary(article_id, run_id, summary)` — no return value
- `save_verification(run_id, claim, verdict, evidence)` — evidence = reasoning string
- `save_report(run_id, content)` — no return value

**External dependencies:** SQLite3 (stdlib), datetime (stdlib)

**Database location:** `briefing.db` in project root (path computed as `os.path.dirname(os.path.dirname(__file__))`)

### Config

#### `emailer.py`
**Purpose:** Sends report via SMTP.

**Key functions:**
- `send_report(to_address, subject, body)` — returns `(success: bool, message: str)`

**External dependencies:** SMTP (smtplib, stdlib), environment variables

**Environment variables (read at import):**
- `SMTP_HOST` (default: smtp.gmail.com)
- `SMTP_PORT` (default: 587)
- `SMTP_USER` (required for email)
- `SMTP_APP_PASSWORD` (required for email)
- `EMAIL_TO` (optional — orchestrator passes override)

**Error handling:** Catches `SMTPAuthenticationError` separately, suggests App Password.

#### `.env.example`
**Purpose:** Template for user credentials. Not loaded by code.

**Required:**
- `OPENAI_API_KEY` — validated in `orchestrator.check_environment()`

**Optional:**
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `EMAIL_TO` — if missing, email is skipped

#### `sources.txt`
**Purpose:** Newline-separated list of URLs to fetch. Lines starting with `#` are comments.

**Format:** Plain text, UTF-8. Parsed by `web_collector.load_sources()`.

**Current defaults:** 10 RSS feeds (ArXiv cs.AI + cs.LG, MIT Tech Review, Wired, IEEE Spectrum, Ars Technica, Crunchbase, VentureBeat, TechCrunch, Google Research Blog)

### Infrastructure

#### `Dockerfile`
**Purpose:** Containerize the system.

**Base image:** `python:3.11-slim`

**Entry point:** `python orchestrator.py` (CMD defaults to `--help`)

**Layers:**
1. Copy `requirements.txt` → `pip install` (cached)
2. Copy all project files
3. No USER directive (runs as root)

**Example run:**
```bash
docker run --rm --env-file .env briefing-system "AI regulation"
```

#### `requirements.txt`
**Purpose:** Python package dependencies.

**Packages:**
- `openai>=1.30.0` — API client
- `requests>=2.31.0` — HTTP fetching
- `beautifulsoup4>=4.12.0` — HTML parsing
- `python-dotenv>=1.0.0` — .env file loader
- `feedparser>=6.0.0` — RSS/Atom parsing

#### `.github/workflows/daily-briefing.yml`
**Purpose:** GitHub Actions workflow for scheduled briefing runs.

**Trigger:**
- Cron: `0 7 * * 3,6` (Wednesdays and Saturdays at 07:00 UTC)
- Manual dispatch with optional topic input (default: "AI Agents in production")

**Steps:**
1. `actions/checkout@v5` — clone repo
2. `actions/setup-python@v6` — install Python 3.11
3. `pip install -r requirements.txt`
4. `python orchestrator.py "$TOPIC"` — runs briefing

**Secrets (required in repo settings):**
- `OPENAI_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `EMAIL_TO`

#### `utils/retry.py`
**Purpose:** Exponential backoff for OpenAI API calls.

**Key functions:**
- `call_with_retry(fn, *args, **kwargs)` — retries on `RETRYABLE` errors

**Retryable errors:**
- `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError`

**Parameters:**
- `MAX_ATTEMPTS = 3`
- `BASE_DELAY = 2.0` seconds, doubles after each failure

**Usage:** All OpenAI calls in planner, summarizer, verifier, writer are wrapped:
```python
response = call_with_retry(
    _get_client().chat.completions.create,
    model=MODEL,
    messages=[...],
)
```

## 5. Data Model

SQLite schema from `store/sqlite_store.py`:

```sql
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,  -- ISO 8601 timestamp (UTC)
    status      TEXT    DEFAULT 'running'  -- 'running' | 'complete' | 'failed'
);

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    url         TEXT    NOT NULL,  -- source URL (may appear multiple times for RSS)
    title       TEXT,
    content     TEXT,              -- truncated to 12,000 chars by web_collector
    fetched_at  TEXT    NOT NULL,  -- ISO 8601 timestamp (UTC)
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER NOT NULL,
    run_id      INTEGER NOT NULL,
    summary     TEXT    NOT NULL,  -- plain-text, 3-5 sentences
    created_at  TEXT    NOT NULL,  -- ISO 8601 timestamp (UTC)
    FOREIGN KEY (article_id) REFERENCES articles(id),
    FOREIGN KEY (run_id)     REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS verifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    claim       TEXT    NOT NULL,  -- factual claim as one sentence
    verdict     TEXT    NOT NULL,  -- 'Supported' | 'Partially Supported' | 'Not Supported' | 'Unverifiable'
    evidence    TEXT,              -- reasoning string from OpenAI (not actual evidence text)
    created_at  TEXT    NOT NULL,  -- ISO 8601 timestamp (UTC)
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL,
    content     TEXT    NOT NULL,  -- final plain-text briefing report
    created_at  TEXT    NOT NULL,  -- ISO 8601 timestamp (UTC)
    FOREIGN KEY (run_id) REFERENCES runs(id)
);
```

**Row semantics:**
- `runs`: One row per invocation of `orchestrator.run()`.
- `articles`: One row per article fetched. RSS feeds yield multiple articles per URL.
- `summaries`: One row per article summary. `article_id` is unique per summary.
- `verifications`: One row per claim extracted and verified. No link to source article (claim origin is stored as string in report).
- `reports`: One row per final report. Multiple runs can exist, but each has one report.

## 6. External Dependencies

### OpenAI API
**Models used:** `gpt-4o` (hardcoded in `planner.py`, `summarizer.py`, `verifier.py`, `writer.py`)

**Configuration:** Environment variable `OPENAI_API_KEY` (required). Loaded by `openai` package via default behavior (no explicit client config).

**Call sites:**
- `planner.create_plan()` — max_tokens=400, temperature=0.3
- `planner.evaluate_evidence()` — max_tokens=200, temperature=0.1
- `summarizer.summarize_article()` — max_tokens=400, temperature=0.3
- `verifier.extract_claims()` — max_tokens=500, temperature=0.2
- `verifier.verify_claim()` — max_tokens=200, temperature=0.1
- `writer.write_briefing()` — max_tokens=2000, temperature=0.4

**Total API calls per run:** 1 (plan) + 1 (evaluate) + N (summaries) + 1 (extract claims) + M (verify claims) + 1 (write) = 4 + N + M, where N = article count, M = claim count (typically 3-5).

### SMTP (Gmail App Password flow)
**Protocol:** STARTTLS on port 587

**Configuration:**
- `SMTP_HOST` (default: smtp.gmail.com)
- `SMTP_PORT` (default: 587)
- `SMTP_USER` — sender address (required)
- `SMTP_APP_PASSWORD` — 16-char app password (required, NOT regular Gmail password)

**Failure modes:**
- `SMTPAuthenticationError` → suggests app password URL
- `SMTPException` → generic SMTP error
- `OSError` → connection error

### Python Packages
**From `requirements.txt`:**
- `openai>=1.30.0` — official OpenAI SDK
- `requests>=2.31.0` — HTTP client (used in `web_collector`)
- `beautifulsoup4>=4.12.0` — HTML/XML parser (used in `web_collector`)
- `python-dotenv>=1.0.0` — loads `.env` file (optional import in `orchestrator.py`)
- `feedparser>=6.0.0` — RSS/Atom parser (used in `web_collector`)

**Stdlib dependencies:** `sqlite3`, `smtplib`, `argparse`, `datetime`, `os`, `sys`, `time`, `warnings`

### Docker
**Base image:** `python:3.11-slim` (Debian-based, minimal Python runtime)

**No additional system packages installed.** All dependencies are Python packages from `requirements.txt`.

## 7. Configuration

### Environment Variables (from `.env.example`)

| Variable | Required | Default | Purpose | What breaks if missing |
|----------|----------|---------|---------|----------------------|
| `OPENAI_API_KEY` | **YES** | (none) | API key for GPT-4o calls | `orchestrator.check_environment()` exits with error message |
| `SMTP_HOST` | NO | `smtp.gmail.com` | SMTP server hostname | Email skipped (no error) |
| `SMTP_PORT` | NO | `587` | SMTP server port | Email skipped (no error) |
| `SMTP_USER` | NO* | (none) | Sender email address | `emailer.send_report()` returns `(False, "credentials not configured")` |
| `SMTP_APP_PASSWORD` | NO* | (none) | Gmail app password (16 chars) | Same as SMTP_USER |
| `EMAIL_TO` | NO | (none) | Default recipient address | Orchestrator prints tip message, email skipped |

**\*NO* = not enforced by `check_environment()`, but email will fail if missing.

### File-Based Configuration

**`sources.txt`:**
- **Required:** YES (throws `FileNotFoundError` if missing)
- **Format:** One URL per line, lines starting with `#` ignored
- **Location:** Project root (discovered via `os.path.join(os.path.dirname(os.path.dirname(__file__)))`)
- **What breaks:** `web_collector.load_sources()` raises `FileNotFoundError`, orchestrator catches and sets `run.status = 'failed'`

## 8. Extending the System

**Adding a new worker:** Create a module in `workers/` with a function that takes `(articles, topic, run_id, store, verbose)` and returns a list of dicts. Import it in `orchestrator.py` and insert a call in the `run()` function at the desired pipeline position. Update `planner.create_plan()` to add a step description if the worker should appear in the plan output. No changes to other workers are needed — the orchestrator mediates all data flow.

**Changing the LLM provider:** Replace `openai` imports in `planner.py`, `summarizer.py`, `verifier.py`, `writer.py` with a different SDK (e.g., Anthropic, Azure OpenAI). Update `utils/retry.py` to handle the new provider's retryable exceptions. Change the `MODEL` constant in each worker file. The prompt engineering may need adjustment depending on the new model's instruction-following behavior. The `call_with_retry` wrapper signature is provider-agnostic.

**Swapping SQLite for another store:** Replace `store/sqlite_store.py` with a new module that implements the same function signatures (`initialize_db`, `create_run`, `save_article`, etc.). Update the import in `orchestrator.py` and all workers from `from store import sqlite_store as store` to the new module. The store interface is purely function-based (no classes), so a new backend only needs to match the function signatures. Consider async implementations (PostgreSQL with asyncpg, MongoDB) if scaling beyond single-process execution.
