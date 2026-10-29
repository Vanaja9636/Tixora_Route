# Tixora Route

**Intelligent Tixorachannel Ticket Routing and SLA Management Platform**

Tixora Route is a reproducible synthetic-data and routing platform for support tickets. It provides explainable assignment decisions, channel-aware SLAs, immutable lifecycle history, validation, anomaly detection, CSV/JSON/SQL exports, and a FastAPI service.

## Requirements

- Python 3.11 or newer
- Windows PowerShell, macOS, or Linux
- Dependencies listed in `requirements.txt`

## Setup on Windows

From the project directory:

```powershell
cd C:\Users\vanaj\Downloads\Tixora_Route
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

If PowerShell prevents environment activation, run commands with the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

The default SQLite database is `data/cli_demo.db`; previously present database files are preserved as legacy inputs and are not overwritten. All persisted timestamps are naive UTC values; the business calendar uses Monday–Friday, 09:00–17:00 UTC. `calendar` and `24x7` calendars count continuous wall-clock time.

## Quick demo

The demo initializes the schema, generates 100 tickets/100 agents/300 messages with seed `20261022`, routes new tickets, validates data, computes metrics, and exports outputs:

```powershell
python -m tixora_route.cli demo
```

Equivalent full-workflow invocation:

```powershell
python -m tixora_route.cli all --tickets 100 --agents 100 --messages 300 --seed 20261022 --event-days 90
```

Run the focused project tests:

```powershell
python -m pytest -q tests
```

## CLI commands

```powershell
python -m tixora_route.cli init
python -m tixora_route.cli generate --tickets 100 --agents 100 --messages 300 --seed 20261022
python -m tixora_route.cli simulate
python -m tixora_route.cli validate
python -m tixora_route.cli anomalies
python -m tixora_route.cli metrics
python -m tixora_route.cli export --out exports
python -m tixora_route.cli repro --tickets 100 --messages 300 --agents 20
```

Use a fresh database (`--database sqlite:///data/another_run.db`) to generate a different dataset; generation is idempotent for a matching ticket count and refuses to append a different-sized run to a populated database.

## Full-scale generation

The configurable challenge target is 30,000 tickets, 100 agents, 100,000 messages, and 90 simulated days:

```powershell
python -m tixora_route.cli all --tickets 30000 --agents 100 --messages 100000 --seed 20261022 --event-days 90 --out exports
```

For separate phases:

```powershell
python -m tixora_route.cli generate --tickets 30000 --agents 100 --messages 100000 --seed 20261022 --event-days 90
python -m tixora_route.cli simulate
python -m tixora_route.cli validate
python -m tixora_route.cli metrics
python -m tixora_route.cli export --out exports
```

Generation writes tickets in batches; message generation and exports are chunked. Routing preloads agents, skills, queues, and active load rather than performing a full agent query for every ticket.

## API

Start the service:

```powershell
python -m uvicorn tixora_route.api:app --host 127.0.0.1 --port 8000
```

Swagger UI is at `http://127.0.0.1:8000/docs`; ReDoc is at `/redoc`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service status |
| GET | `/tickets?skip=0&limit=100` | Paginated ticket list |
| GET | `/tickets/{ticket_id}` | Ticket summary and related counts |
| GET | `/tickets/{ticket_id}/messages` | Ordered threaded messages |
| GET | `/tickets/{ticket_id}/history` | Assignment and SLA history |
| GET | `/agents?skip=0&limit=100` | Paginated agents |
| GET | `/queues` | Queues |
| POST | `/tickets/{ticket_id}/route` | Route and persist an explainable decision |
| GET | `/metrics` | Derived operating metrics |
| POST | `/validate` | Run strict data validation |

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/tickets?skip=0`&limit=10
Invoke-RestMethod -Method Post http://127.0.0.1:8000/validate
```

Unknown ticket IDs return HTTP 404. Request parameters use Pydantic validation and bounded pagination.

## Data model and routing rules

All 13 required entities and the three many-to-many bridge tables are declared in `src/tixora_route/models.py`. Cardinalities, columns, nullability, constraints, and enumerations are detailed in [`docs/data_dictionary.md`](docs/data_dictionary.md).

Routing chooses an intent queue, then filters out agents who are inactive, lack the required skill, speak a different language, are outside shift, or are at capacity. Eligible candidates receive a deterministic score:

`priority_rank × 100 + channel_bonus − current_load × 10`

Channel bonuses are phone=15, chat=10, email=5, other=0. The final tie-break is lowest current load, then stable agent public ID. Assignment/queue events persist the score, explanation, channel/intent/priority, and rejected candidate rules. Capacity uses each ticket’s latest active assignment, not its full transfer history.

Safety-intent priority is always urgent (PR-001). SLA targets are urgent=30, high=120, normal=240, and low=480 business minutes. Ticket transfers, reopenings, escalations, resolution cycles, and closure append history; earlier events and resolution records are retained.

## Validation and anomaly fixtures

`validate` checks relationship integrity, allowed values, public-ID uniqueness, timestamps, SLA calculations and event completeness, thread integrity, routing skill/language/shift/capacity, and status count reconciliation. The clean generated baseline must return `valid: true`.

The clean generator does not inject anomaly data. `tixora_route.anomalies.build_anomaly_fixture()` creates an isolated in-memory database for one of five intentional cases: over-capacity agent, wrong SLA calendar, missing reopening history, transfer loop, or safety-priority contradiction. Close returned resources with `close_anomaly_fixture(engine, session)`. Each detector uses the business records and does not consult labels.

## Exports and reproducibility

`export` writes per-table CSV and JSON files, plus:

- `ground_truth.csv` and `ground_truth.json`: expected decisions and business-rule anomaly labels
- `tixora_route.sql`: executable DDL and SQL seed inserts
- `metrics.json`, `validation_summary.json`, and `row_counts.json`
- `source_manifest.json`: per-output SHA-256 checksums, row counts, seed, and provenance

Exported event/message records include both internal foreign keys and human-facing public IDs. `repro` builds two clean SQLite databases with the same seed and compares their exported checksums. The manifest timestamp itself is intentionally not checksummed.

All sample customer names, email addresses, messages, and tickets are fictional and generated locally from the documented seed and rules. No production data, real customer records, or third-party datasets are used.

## Project layout

```text
src/tixora_route/   FastAPI app, SQLAlchemy model, services, generator, CLI
tests/              pytest coverage for models, data, routing, SLA, API, exports
scripts/            Windows and POSIX demo launchers
data/               SQLite database (generated)
exports/            CSV/JSON/SQL outputs (generated)
docs/               architecture, field dictionary, rule and anomaly docs
schema.sql          schema snapshot; SQL seed output is generated under exports/
```

## Troubleshooting

- **`ModuleNotFoundError`**: activate `.venv`, install `requirements.txt`, then `pip install -e .`.
- **PowerShell activation blocked**: invoke `.\.venv\Scripts\python.exe` directly.
- **Database has incompatible local schema**: `init` applies supported SQLite additive upgrades. For a clean independent run, pass a new SQLite URL using `--database sqlite:///data/fresh_run.db`.
- **Validation fails after an anomaly fixture**: fixtures intentionally corrupt one isolated database; they do not modify the default clean dataset.
- **Port 8000 is occupied**: choose another port with `--port`, e.g. `--port 8001`.

## Assessment traceability

The challenge-to-module/test map is in [`docs/business_rules.md`](docs/business_rules.md). Architecture is described in [`docs/architecture.md`](docs/architecture.md).
