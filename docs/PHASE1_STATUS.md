# Wedding V3 — Phase 1 status

## Completed

- Flask application factory
- Environment-based configuration
- SQLAlchemy 2 / Flask-SQLAlchemy foundation
- Flask-Migrate integration
- Flask-WTF CSRF integration
- Exact models for the four existing production tables
- Invitation repository and session service
- Authorized-event and saved-RSVP repositories
- Health and database readiness endpoints
- Initial private invitation route
- Initial dashboard shell route
- Read-only live-schema verification script
- Basic pytest coverage
- Legacy notification module preserved for controlled migration

## Intentionally not done yet

- No database migration has been applied.
- No production route has been replaced.
- No guest or RSVP data has been copied.
- No current styling has been discarded.
- The cinematic UI has not yet been migrated into fragment routes.

## Next phase

Phase 2 will build the persistent visual shell and two-buffer responsive slideshow, then move Welcome into its own server-rendered tab fragment while preserving the approved appearance and animations.
