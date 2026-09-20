# project

The WhatsApp side of CrewCare: a standalone FastAPI service that links a worker
to a WhatsApp number and runs the reporting conversation over the Meta Cloud
API. Originally named StationShield.

**The web demo does not use this.** `crewcare/` ships a browser-only worker
flow, so you can show the whole product — worker portal and operations
dashboard — with nothing but `npm run dev`. This folder is what a real
deployment would need instead: a Meta app, a verified number and a public
webhook.

```
project/
  main.py                 the FastAPI app; mounts the webhook router
  whatsapp/
    webhook.py            inbound message handling and verification
    conversation_service.py   the reporting conversation
    linking_service.py    codes that bind an employee id to a number
    auth.py               webhook signature verification
    whatsapp_client.py    outbound Cloud API calls
    ai_client.py          the reply model
    db.py, models.py      SQLAlchemy storage
    requirements.txt
    README.md             setup, local testing, and what is deliberately not done
```

## Running it

```bash
cd project
pip install -r whatsapp/requirements.txt
cp whatsapp/.env.example whatsapp/.env    # fill in the Meta credentials
uvicorn main:app --port 8000
```

`whatsapp/README.md` covers testing without real credentials, wiring the
webhook, and the production gaps.

Note it defaults to the same port as `crewcare/server`, so run one or the
other, or move one.

## Storage

The service writes `stationshield_whatsapp.db`, a SQLite file holding linking
codes, employee-to-number links, conversation state and processed webhook ids.

**It is gitignored.** A runtime database does not belong in version control:
it churns on every run, and this one accumulates the mapping between employee
ids and phone numbers — exactly the data the rest of the system is built to
avoid storing. A copy was tracked earlier in the repo's history; it held test
rows only (`EMP001`, a `555` number), and it has since been untracked.

## Relationship to the rest of the repo

Independent. It imports nothing from `admin_dashboard/` or `crewcare/`, and
nothing imports it. A worker report filed through WhatsApp would land in the
same store the dashboard reads
(`admin_dashboard/admin_dashboard_model/complaints.py`), but that wiring is not
built here yet.
