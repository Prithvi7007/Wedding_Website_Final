# Wedding V3 Phase 5 — Production Ready

Phase 5 hardens the completed wedding website for production without changing the PostgreSQL schema.

## Local install

Extract the upgrade over `D:\Wedding_V3`, replace files, then run:

```powershell
cd D:\Wedding_V3
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m flask --app wsgi.py run --debug
```

Keep the SSH tunnel open for local PostgreSQL access.

## Production

Read:

```text
docs/PRODUCTION_DEPLOYMENT.md
```

Run the read-only preflight on the VPS before restarting:

```bash
/var/www/wedding/.venv/bin/python -m scripts.production_preflight --check-db
```

Do not run `flask db upgrade` for this phase.
