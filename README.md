# AR Co-Pilot Backend

AI-powered Accounts Receivable validation platform — Step B backend.

## Architecture

```
Step A (done)   →  Frontend (React + Vite + Tailwind + shadcn/ui)
Step B (this)   →  Backend (FastAPI + SQLite + mocked AI)
Step C (next)   →  Replace ai_service.py with real Google ADK + Gemini
```

The mocked AI layer (`app/services/ai_service.py`) is the single swap point for Step C. Every other layer (engine, rules, API, SSE streaming) stays identical.

## Quick Start

```bash
# 1. Copy env config
cp .env.example .env

# 2. Install dependencies (Python 3.11+ required)
pip install -e ".[dev]"

# 3. Run migrations
alembic upgrade head

# 4. Seed database with mock data
python seed_data.py

# 5. Start server
uvicorn app.main:app --reload --port 8000
```

Or use the run script:
```bash
bash run.sh
```

Server: http://localhost:8000  
API docs: http://localhost:8000/docs  
Health: http://localhost:8000/health

## Folder Structure

```
app/
  main.py                  FastAPI entrypoint, CORS, router mounting
  config.py                Settings (pydantic-settings, .env)
  database.py              Async SQLAlchemy engine + session + Base
  models/                  SQLAlchemy ORM models (7 tables)
  schemas/                 Pydantic v2 request/response schemas
  api/                     FastAPI route handlers
  services/
    ai_service.py          MOCKED AI — swap this in Step C
    validation_engine.py   Async generator orchestrator
    audit_service.py       Wraps every state-changing action
    document_service.py    File storage (local ./uploads/)
  rules/                   One module per rule (26 total, 4 sections)
    base.py                BaseRule abstract class
    document_content/      8 rules
    hubspot_match/         6 rules
    field_completeness/    6 rules
    policy/                6 rules
```

## API Reference

All endpoints at `/api/v1`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/deals` | List deals (filters: status, submitted_by, search) |
| GET | `/deals/stats` | Dashboard stat cards |
| GET | `/deals/{id}` | Deal detail with documents + latest validation |
| POST | `/deals` | Create deal |
| PATCH | `/deals/{id}` | Update deal (status, etc.) |
| POST | `/deals/{id}/documents` | Upload document (multipart) |
| GET | `/documents/{id}` | Download document |
| DELETE | `/documents/{id}` | Delete document |
| POST | `/deals/{id}/validate` | Trigger validation run (async) |
| GET | `/validation-runs/{id}` | Get run status + all rule results |
| GET | `/validation-runs/{id}/stream` | **SSE stream** — yields results live |
| POST | `/rule-results/{id}/action` | Apply reviewer action |
| GET | `/rules` | List all rules grouped by section |
| GET | `/rules/{id}` | Single rule |
| PATCH | `/rules/{id}` | Update rule config (audited) |
| POST | `/rules/{id}/test` | Test rule against a deal |
| GET | `/checklists` | List checklists |
| POST | `/checklists` | Create checklist |
| PATCH | `/checklists/{id}` | Update checklist |
| POST | `/checklists/{id}/publish` | Publish draft |
| GET | `/audit-log` | Paginated audit log |
| GET | `/audit-log/stats` | Compliance score + weekly trend |

## SSE Streaming

```javascript
const es = new EventSource('/api/v1/validation-runs/{run_id}/stream');
es.onmessage = (e) => {
  const result = JSON.parse(e.data);
  if (result.event === 'complete') {
    // { passed, warnings, failed, status }
  } else {
    // RuleResult: { rule_id, rule_name, section, status, confidence, evidence, ... }
  }
};
```

## Mocked AI (Step B → Step C swap)

`app/services/ai_service.py` exposes:

```python
class AIService:
    async def evaluate_rule(rule, deal_context, documents) -> RuleEvaluation:
        # Step B: returns hardcoded responses with artificial 200-1500ms delay
        # Step C: calls Gemini via Google ADK, same return type
```

Demo deal **DL-12345** (Scholastic Solutions Pvt Ltd) returns exactly:
- 18 pass, 5 warning, 3 fail
- Failures: Pricing Annexure missing, ZCEO approval not attached, SLA deviation
- Warnings: Effective date mismatch, contact email domain, territory conflict, onboarding timeline

## Database

SQLite (dev) — designed for Postgres parity:
- No SQLite-specific types used
- Async SQLAlchemy 2.0 throughout
- Alembic for migrations
- To swap: change `DATABASE_URL` in `.env` to a Postgres URL

## Tests

```bash
pytest tests/ -v
```

15 tests covering deals CRUD, validation triggering, rules API, checklists, and audit log.

## Step C Migration Checklist

To replace mocked AI with real Gemini calls:

1. Set `AI_PROVIDER=gemini` and `GEMINI_API_KEY=...` in `.env`
2. Rewrite `app/services/ai_service.py` — only the `evaluate_rule()` method body changes
3. The `RuleEvaluation` dataclass return type is unchanged
4. All rule modules, the validation engine, SSE streaming, and audit logging stay identical
