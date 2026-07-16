# Wedding V3 — Phase 2 Status

## Completed

- Persistent cinematic dashboard shell
- Private invitation session integration
- Exact personalized guest display name
- Responsive AVIF/WebP slideshow media
- Two-buffer slideshow: only two full-screen image nodes exist
- Automatic slideshow remains enabled on iOS and across tab changes
- Manual slideshow arrows and dots
- Full Welcome composition and countdown
- Canvas-based login sparkles with the same visual behavior and far fewer DOM nodes
- Fragment-ready tab navigation with full-page fallback
- CSS split into stable design-system files
- Existing Phase 1 SQLAlchemy mapping and health endpoints preserved

## Intentionally deferred

Schedule, Travel, Registry, Q&A, RSVP, attire modals, calendar routes, notification migration, and RSVP petals are migrated in later phases. Their tab endpoints are connected now so the persistent shell architecture can be tested first.

## Production safety

This package does not run migrations and does not modify the production database.
