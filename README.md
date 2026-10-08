# Bulk Certificate Generator

A backend API that accepts one request containing many recipients, generates a PDF
certificate for each valid recipient in the background, tracks the status of the job,
and lets the client retrieve the results.

Built with FastAPI, SQLAlchemy and SQLite. Certificates are drawn with ReportLab.

## Setup

Requires Python 3.11 or newer.

```bash
git clone https://github.com/anshuly0720/bulk-certificate-generator.git
cd bulk-certificate-generator

python -m venv .venv
.venv\Scripts\activate.bat        # Windows (cmd); PowerShell: .venv\Scripts\Activate.ps1
source .venv/bin/activate         # macOS / Linux

pip install -r requirements.txt
```

No database setup is needed. The tables are created on startup, and the SQLite file
appears as `certificates.db` in the project root.

## Running the application

```bash
uvicorn app.main:app --reload
```

The API is then at `http://127.0.0.1:8000`, with interactive documentation at
`http://127.0.0.1:8000/docs`.

Configuration is read from the environment, with working defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./certificates.db` | Any SQLAlchemy URL |
| `STORAGE_DIR` | `./storage` | Where generated PDFs are written |
| `MAX_RECIPIENTS` | `5000` | Largest accepted request |

## Running the tests

```bash
pytest
```

31 tests covering job creation, input validation, certificate generation, job status
and progress, individual certificate failure, and retrieval.

## Submitting a generation request

One request carries the whole recipient list. The response returns immediately, before
any PDF is drawn.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
        "course_name": "Backend Engineering Bootcamp",
        "issuer": "Acme Academy",
        "issue_date": "2026-10-08",
        "recipients": [
          {"name": "Asha Verma", "email": "asha@example.com"},
          {"name": "Rahul Singh", "email": "rahul@example.com"}
        ]
      }'
```

```json
{
  "job_id": "dae90be6-2ff9-4553-bcfd-b575e878ff0f",
  "status": "PENDING",
  "total": 2,
  "accepted": 2,
  "invalid": 0,
  "status_url": "/api/v1/jobs/dae90be6-2ff9-4553-bcfd-b575e878ff0f"
}
```

`accepted` and `invalid` are the counts after per-row validation: rows that failed
validation are stored with the reason and never attempted.

### Checking progress

```bash
curl http://127.0.0.1:8000/api/v1/jobs/{job_id}
```

```json
{
  "status": "COMPLETED_WITH_ERRORS",
  "counts": {"total": 5, "pending": 0, "generated": 4, "failed": 0, "invalid": 1},
  "progress_percent": 100.0,
  "created_at": "2026-10-07T12:51:09.458981",
  "started_at": "2026-10-07T12:51:09.468355",
  "completed_at": "2026-10-07T12:51:09.503189"
}
```

All timestamps are UTC.

| Job status | Meaning |
| --- | --- |
| `PENDING` | Saved; the background task has not started |
| `PROCESSING` | Certificates are being generated |
| `COMPLETED` | Every recipient got a certificate |
| `COMPLETED_WITH_ERRORS` | Some succeeded, some were invalid or failed |
| `FAILED` | Nothing could be generated |

| Certificate status | Meaning |
| --- | --- |
| `PENDING` | Valid, waiting its turn |
| `GENERATED` | PDF written to disk |
| `FAILED` | Generation raised an error; the message is stored |
| `INVALID` | Rejected by validation; never attempted |

## Retrieving certificates

Per-recipient results, with `status`, `limit` and `offset` query parameters:

```bash
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}/certificates?status=FAILED"
```

```json
{
  "items": [
    {
      "certificate_id": "1f2b2401-904c-411d-8639-105b3f328675",
      "row_index": 1,
      "name": "Rahul Singh",
      "status": "FAILED",
      "error": "RuntimeError: disk full",
      "download_url": null
    }
  ]
}
```

One certificate as a PDF:

```bash
curl -OJ http://127.0.0.1:8000/api/v1/certificates/{certificate_id}/download
```

Every certificate in the job as a ZIP:

```bash
curl -OJ http://127.0.0.1:8000/api/v1/jobs/{job_id}/download
```

`409` is returned when a certificate was never generated, or when the job is still
running or produced nothing.

## Design decisions

**Background processing over synchronous generation.** The brief allows either. A
single request may carry thousands of recipients, and generating them inside the
request would leave the client waiting on an open connection with no way to see
progress — and `POST /jobs` would be the only endpoint that mattered, making the
status tracking the brief asks for meaningless. Instead the request validates and
saves rows, returns `202` with a `job_id`, and schedules the work with FastAPI's
`BackgroundTasks`.

`BackgroundTasks` rather than Celery or RQ because those need a broker such as Redis,
which a reviewer would have to install and run before seeing anything work. The cost
is real and worth stating: a job that is mid-flight when the process dies stays
`PROCESSING`. `process_job(job_id)` deliberately takes only an id and opens its own
session, so the same function could be called by a Celery worker or a startup
recovery hook without changing a line.

**Per-row validation instead of rejecting the whole request.** `recipients` is typed
`list[dict]` rather than `list[RecipientIn]`. Typed as the latter, FastAPI would
reject the entire request with `422` because of a single malformed row — one typo in
a list of 500 would block 499 valid certificates. Each row is validated individually
with `RecipientIn.model_validate`, and failures are stored as `INVALID` with the
reason. The request as a whole is still rejected for structural problems: a missing
course name, an empty list, or more rows than the cap.

**One `try`/`except` per certificate.** The brief requires that one failure not
prevent other valid certificates in the same job. The loop catches `Exception` around
each row, records the error against that row, and continues. `Exception` rather than a
narrow type is deliberate: the point is that nothing escaping one certificate can take
down the other 499.

**A database commit after every row.** This is what makes progress observable. With a
single commit at the end, the status endpoint would read 0% until the job finished and
then jump to 100%.

**Counts from `GROUP BY` rather than stored counters.** Counters on the job row can
drift if a write fails midway. Counting rows by status is always consistent with the
data, and `certificates.job_id` is indexed.

**SQLite.** Relational, as required, with no setup for a reviewer. `DATABASE_URL`
points anywhere SQLAlchemy supports, so PostgreSQL is a configuration change — though
only SQLite has been tested. SQLite allows one writer at a time, which suits a single
server process.

**UUID identifiers.** Download URLs carry no authentication, so sequential integers
would let anyone enumerate other people's certificates.

**Names the certificate font cannot draw are rejected.** ReportLab's built-in
Helvetica silently draws black boxes for characters outside cp1252 — Devanagari,
Cyrillic, Chinese — and raises no error, so a broken certificate would be stored as a
success. Those rows are rejected up front with a clear reason instead.

**The name is scaled to fit.** The first version shrank the font in steps with a 14pt
floor, which let a 100-character name run past the border and off the page. The size
is now computed directly from the text width, so any name the validation allows fits
inside the border.

## Known limitations

- A job interrupted by a process restart stays `PROCESSING`; its unfinished rows stay
  `PENDING`. Re-running `process_job` for that id would pick up exactly those rows,
  but no automatic recovery hook is wired up.
- The ZIP for a job is built in memory, which is fine at the 5,000-recipient cap but
  would need streaming to disk beyond it.
- Only Latin-script names can be printed. Bundling a Unicode font would cover Cyrillic,
  Vietnamese and most European scripts; Devanagari and CJK need a font with those
  glyphs and more careful shaping.
- There is no authentication; anyone who can reach the API can create and read jobs.
