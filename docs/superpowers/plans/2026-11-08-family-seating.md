# Family Seating Implementation Plan

> Execute natively in the existing CREW Bridge workflow. Use test-first vertical slices and independent final review.

**Goal:** One table per invitation/family, guest name search and one shared QR landing page.
**Architecture:** Two additive SQLAlchemy tables, a seating service/routes module, a shared guest-link helper, server-rendered guest/admin pages and a small appearance/control script. Existing photo uploads remain intact.
**Tech Stack:** Existing Flask, SQLAlchemy/PostgreSQL, Jinja, vanilla CSS/JS, qrcode and Playwright; no dependencies added.
**Spec:** `docs/superpowers/specs/2026-11-08-family-seating-design.md`.

## Global constraints

- User selected one table per family/invitation; assignment is event-specific.
- No guest login, new publish/approval gate, invented assignments or enforced table capacities.
- Keep existing admin roles, CSRF, audits, private QR, noindex/no-store headers and photo behavior.
- Keep new guest paths under `/photos/` and reuse the current token/base URL.
- Stable content surfaces; Liquid Glass-inspired controls only, opaque mobile/reduced-effect fallbacks and visible solid-surface preference.
- Only two new tables; no existing invitation/event/RSVP schema or data modifications.

## Review focus

- Matching surnames/partners/accents, long names and more than one page: all matching eligible families remain discoverable, no private fields or full initial roster.
- Wrong event, inactive family or removed permission: reject new assignments and hide stale saved rows; restoration retains their prior assignment.
- Capacity and RSVP changes: counts update from current data; warnings do not block host decisions.
- Bulk writes, table deletion and viewer/CSRF failures: no partial updates or unauthorized changes; audit in the same transaction.
- Missing schema, existing printed QR and phone blur history: graceful setup/empty states and working legacy photo routes, with native controls and solid mobile surfaces.

## Task 1: Data, service and route contract

Files: `app/models/seating.py`, `app/models/__init__.py`, `app/seating/{__init__,services,routes}.py`, `app/guest_links.py`, `app/__init__.py`, `tests/test_seating.py`.
Interfaces: `SeatingTable`, `SeatingAssignment`; guest paths `/photos/<token>/welcome` and `/photos/<token>/seating`; host `/admin/seating`, table CRUD and bulk assignment routes.

- [x] Write failing route regressions for lookup, host changes, cross-event/role/CSRF protections, lifecycle, occupancy, audit and CSV.
- [x] Run red against main, then implement the two models, explicit private/public view models and transactional writes with soft capacity warnings.
- [x] Implement shared QR access validation without coupling seating to R2 availability; protect all new responses and preserve form referrers.
- [x] Run focused regressions green and commit the data/route slice.

## Task 2: Guest and host UI

Files: `app/templates/experience/{base,welcome,seating,navigation}.html`, `app/templates/seating/admin.html`, `app/static/{css/guest-experience.css,js/guest-experience.js}`, existing photo templates/routes and admin base.
Interfaces: server-rendered family results, event filters, optional capacity, per-event host counts, bulk family IDs and shared guest URL.

- [x] Write real-browser regressions for host create/assign/move/delete and guest lookup/navigation with strict HTTPS CSRF.
- [x] Build bronze/ivory UI with glass navigation/toolbars and solid result/form surfaces, optional solid controls and accessible state/empty messages.
- [x] Link welcome/seating/upload/gallery, update QR downloads to the shared landing page and retain existing upload URLs.
- [x] Verify desktop/mobile, keyboard, large text, long labels, reduced effects and screenshot layouts; retain physical-phone performance caveat.

## Task 3: Schema and complete verification

Files: `scripts/apply_seating_schema.py`, `docs/WEDDING_SEATING.md`, tests for additive/idempotent schema and browser/photo regressions.

- [x] Test an additive, transactional, idempotent two-table setup and preservation of existing records; implement the schema script.
- [x] Document backup/apply/verify/code rollback with schema retained; prepare the one-time dependency-free operator rollout after merge.
- [ ] Complete final review recheck and CREW pytest/wedding_syntax on the final fingerprint, then open the reviewed PR.

## Verification ledger

- Initial 13 seating cases failed against main (routes absent), then 14 service/route cases passed. Additive schema tests failed before the setup script and passed after it.
- Initial focused seating/photo/HTTPS-browser suite: 84 passed. Browser testing found and fixed 320px large-text header overflow. Screenshots inspected for mobile guest search, welcome and the host planner.
- Initial full local suite: 266 passed; the existing `test_original_mobile_navigation_labels_are_evenly_centered[320]` failure remains in the unchanged invitation navigation when external fonts are unavailable. It was reproduced on the base before this feature.
- Independent Standards review found the index-definition verifier and startup-failure rollback gaps. Independent Spec review found missing direct-photo-page Solid controls switches. All three were corrected. The three wrong-index regressions failed before the verifier fix; all 29 seating/unit/browser cases passed after the corrections, including the appearance preference across all guest pages.
- Schema creation, idempotence, existing-record counts and transactional failure are exercised on SQLite. The PostgreSQL inspector path and DDL were reviewed; a production PostgreSQL setup has not yet run.
- Initial CREW checks passed (201 tests, 3 optional-dependency skips, plus wedding_syntax). Final checks must use the final source fingerprint.
- Physical Android GPU/flicker behavior remains a phone verification step after deployment; mobile browser tests verify solid controls and layout.
