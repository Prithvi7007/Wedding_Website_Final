# Wedding Admin Portal — Phase 4

Phase 4 completes the wedding administration portal with persistent audit
history, database-backed login throttling, secure admin response headers, and
production backup/verification tooling.

## Included

- persistent `admin_audit_logs` table
- persistent `admin_login_attempts` table
- audit page at `/admin/audit`
- before-and-after summaries for invitation and RSVP changes
- token regeneration audit without storing the private token
- login success, failure, block, logout, and CSV export records
- database-backed login rate limiting across Gunicorn workers
- configurable failure window and lockout duration
- `Cache-Control: no-store` on every admin response
- `X-Robots-Tag: noindex, nofollow, noarchive`
- verified PostgreSQL backup script
- idempotent Phase 4 database schema installer
- production verification script
- automated acceptance tests

## Default login protection

- five failed attempts
- measured over fifteen minutes
- thirty-minute lockout
- successful login clears failures for that IP

Optional `.env` overrides:

```dotenv
WEDDING_ADMIN_LOGIN_MAX_FAILURES=5
WEDDING_ADMIN_LOGIN_WINDOW_MINUTES=15
WEDDING_ADMIN_LOCKOUT_MINUTES=30
```

## Database setup

This project does not currently contain an Alembic migration directory.
Phase 4 therefore includes an idempotent schema installer:

```bash
./.venv/bin/python scripts/apply_admin_phase4_schema.py
```

It creates only the two new Phase 4 tables and their indexes. Running it more
than once is safe. Existing invitations, events, permissions, and RSVP records
are not modified.

## Audit privacy

The audit history never stores:

- the administrator password
- raw private invitation tokens
- database credentials
- session cookie values

A short one-way token fingerprint is recorded so token changes can be verified
without preserving the working private link.

## Production rollback

The schema change is additive. The safest rollback is to reset the application
code to the previous Git commit and restart the `wedding` service while leaving
the two unused tables in place. The verified database backup remains available
for disaster recovery.
