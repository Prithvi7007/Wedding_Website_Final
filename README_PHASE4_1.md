# Wedding V3 Phase 4.1 Travel Layout Fix

Extract the upgrade over `D:\Wedding_V3` and replace files.

Then run:

```powershell
cd D:\Wedding_V3
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m flask --app wsgi.py run --debug
```

Perform a hard refresh with `Ctrl + Shift + R`.

This patch changes only the Travel page layout and its regression test.
It does not change the database or require migrations.
