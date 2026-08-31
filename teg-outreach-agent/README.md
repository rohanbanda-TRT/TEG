# TEG Inquiry Outreach Agent

FastAPI service + chat widget that researches a TEG 2026 inquiry-page prospect
(knowledge base first, then free web tools) and runs a persona-tuned,
factually-guarded conversation to drive participation.

## Setup

```bash
cd teg-outreach-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # fill DATABASE_URL, ANTHROPIC_API_KEY, TAVILY_API_KEY
createdb teg_outreach
alembic upgrade head
```

## Run

```bash
uvicorn app.main:app --reload
```

- `POST /inquiries` `{person_name, company_name}` -> `{session_id, opening_message, persona}`
- `WS /chat/{session_id}` -> live conversation
- `GET /sessions/{session_id}` -> transcript + dossier + handoff (internal)

## Tests

```bash
createdb teg_outreach_test
python -m pytest -q
```

## Retention

```bash
python -m app.jobs.retention   # run from cron
```

## Design docs

- Spec: `../docs/superpowers/specs/2026-08-31-teg-outreach-agent-design.md`
- Plan: `../docs/superpowers/plans/2026-08-31-teg-outreach-agent.md`
