# Instant wedding gallery and photo formats implementation plan

> Implement inline using executing-plans and test-driven-development. Review the whole branch before opening the PR.

**Goal:** Accept common phone photo formats and make new consented uploads immediately visible in the guest gallery.

**Architecture:** Keep the existing Flask, private R2, JPEG normalization and QR-linked gallery. Publish new consented records when they are saved. Replace host approval/publication controls with one-step Hide/Show and Delete. Fall back to server normalization when browser decoding fails; use pillow-heif for HEIC/HEIF.

**Tech stack:** Existing Flask/Pillow/boto3/JavaScript; pillow-heif 1.8.1 or newer below 2.

**Spec:** User feedback in this conversation: non-JPG photos seem rejected; remove approve/publish and show uploads immediately. The failed source format is unknown.

## Global constraints

- Keep HTTPS CSRF protection, consent, QR access, private bucket, EXIF stripping, 6-file/12 MiB image/32 MiB request/30-million-pixel limits.
- Keep existing hidden/unconsented/deleted records hidden; no read-time migration or mass publication of old photos.
- New valid consented uploads need no host action. Hosts can hide/show consented photos in one step and delete them.
- No database schema, RSVP, invitation, or public bucket changes.
- HEIC/HEIF needs pillow-heif installed on the host before rollout; report this prerequisite explicitly.

## Review focus

- HEIC/TIFF browsers cannot decode: upload the original bytes for bounded server validation, including blank MIME types.
- Malformed, unsupported, oversized or mixed-invalid batches: reject without newly shared photos.
- Hidden, deleted or unconsented photos: never leak through stale direct image URLs or Show actions.
- R2 write failures: no success response or partially published metadata.
- Secure HTTPS form submissions and external referrer privacy: preserve existing regression coverage.

## Task 1: Server formats and immediate sharing

- [x] Write tests for real JPEG/PNG/WebP/HEIF/AVIF/GIF/BMP/TIFF files and immediate guest image access; run them red.
- [x] Extend normalization with HEIF decoding; initialize consented records with their publication timestamp.
- [x] Implement shared visibility and atomic Show/Hide actions, retaining consent and deletion checks.
- [x] Update existing route/storage tests to the new flow; run the focused suite green.

## Task 2: Guest and host experience

- [x] Test HTTPS uploads using PNG/WebP/HEIF and immediate gallery visibility; test real host Hide/Show/Delete forms.
- [x] Add bounded raw-file fallback, explicit picker extensions and a preview fallback for browser-unsupported formats.
- [x] Replace all pending-review/approval copy and host controls with immediate-sharing copy and Shared/Hidden filters.
- [x] Update deployment documentation and codec prerequisite; run focused and full suites, syntax and bridge checks.
- [x] Review the whole branch, fix material findings with tests, and prepare the verified change for CREW Bridge commit and PR.

## Execution ledger

- Ruling: "Publicly available" uses the existing QR-linked gallery, because the requested change removes host moderation rather than the guest access link.
- Ruling: Keep existing hidden photos hidden; the new behavior applies at upload time and hosts retain one-step Show for consented legacy photos.
- Ruling: Add a server HEIF decoder rather than a browser-only converter so common iPhone files work even when the browser cannot decode them.
- Preflight: Both tasks consume the saved photo visibility predicate and Show/Hide actions; browser tests must use the same live HTTPS and CSRF settings as the prior fix.

- Verification: 47 focused photo tests passed, including real input formats, HTTPS browser fallback, immediate visibility, Hide/Show/Delete, and concurrent reads during batch failure.
- Verification: full suite completed with 229 passed and one deselected existing 320px navigation-centering test; that test also fails on unchanged base 83212157. Initial unfiltered run: 225 passed, one failed before the final four regressions were added.
- Review: standards review found no material issues. Spec review identified transient visibility during a failed multi-photo R2 write; shared metadata reader locks now wait for writer success/rollback, covered for both gallery and direct image reads.
- Release prerequisite: install pillow-heif from requirements into the production virtualenv before enabling this release. The existing bridge release agent is code-only and cannot install it.
