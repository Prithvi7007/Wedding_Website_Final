# Wedding V3 — Phase 4

Phase 4 completes the guest-information side of the wedding portal by migrating Travel, Registry, and Questions & Answers into the optimized fragment architecture.

## Apply over the existing project

1. Stop the local Flask server.
2. Back up `.env`.
3. Extract the Phase 4 Upgrade ZIP into `D:\Wedding_V3` and replace files.
4. Keep the SSH tunnel open.
5. Run:

```powershell
cd D:\Wedding_V3
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m flask --app wsgi.py run --debug
```

Open a private invitation URL and test **Travel**, **Registry**, and **Q&A**.

After replacing static files, use `Ctrl + Shift + R` once to bypass the browser cache.

## Database safety

No migration is included or required. Do not run `flask db upgrade`.
