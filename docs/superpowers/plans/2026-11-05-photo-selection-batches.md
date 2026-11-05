# Photo Selection and Automatic Upload Batches Implementation Plan

> Execute natively in the existing CREW Bridge workflow. Review the complete branch before opening its PR.

**Goal:** Guests select more than six photos and the page sends them automatically without manual splitting.

**Architecture:** Keep the existing authenticated-by-QR, consented upload endpoint. The browser streams sequential groups respecting its existing six-files/32 MiB request contract, with a 30 MiB payload target for multipart overhead. Retain acknowledged progress after a later group fails, so Retry sends only remaining files. Do not automatically retry requests with uncertain outcomes.

**Tech Stack:** Existing vanilla JavaScript, Flask, Pillow/HEIF, Playwright and pytest. No new dependencies.

**Spec:** User accepted removing the six-photo selection cap and uploading automatically in smaller batches; visible restrictions must not be introduced silently.

## Global Constraints

- No selection-count cap in the normal JavaScript guest flow; remove the six-photo picker copy.
- Keep consent, CSRF, private R2, immediate gallery sharing, existing server validation and access controls.
- Freeze selection and metadata controls during upload; report actual acknowledged progress and remaining photos after failures.
- Success count must reflect the entire selection, including more than six files.
- No schema, dependency, Nginx or production configuration changes.

## Review Focus

- Thirteen selected photos: enabled submission, all thirteen reach the guest gallery and thank-you count.
- Large browser-unsupported originals: split by bytes as well as count before exceeding the request limit.
- A later request fails: acknowledge earlier successes; Retry must not resend acknowledged files.
- Inputs edited during upload: prevent changed selection or metadata from corrupting the queue.
- Connection loss after a possible server commit: do not silently auto-retry or claim success; state uncertainty.

## Task 1: Selection and upload queue

Files: `app/static/js/photo-drop.js`, `app/templates/photos/guest_upload.html`, `tests/browser/test_guest_photo_drop.py`.

Interface: consume existing POST JSON `{success: true, count: int}`; send unchanged form fields with each group; produce final `/thanks?count=<acknowledged total>`.

- [x] Add browser regressions for thirteen photos, byte-based splitting and retry after a rejected later request; run red against the existing selection cap.
- [x] Remove browser selection cap; prepare and send sequential groups of at most six and at most 30 MiB, preserving the existing 12 MiB original-file rule.
- [x] Lock editable controls while sending; retain acknowledged progress and show remaining files on failure; avoid ambiguous automatic retries.
- [x] Remove six-photo copy and use lazy preview decoding for larger selections.
- [x] Run the new browser regressions green, then commit.

## Task 2: Completion and verification

Files: `app/photos/routes.py`, `tests/test_guest_photos.py`, `docs/WEDDING_PHOTO_DROP.md`.

Interface: thank-you route renders the integer total from the completed queue without clipping it to six.

- [x] Add a regression that `/thanks?count=13` renders thirteen; run red.
- [x] Remove count clipping, document automatic grouping and partial-failure behavior, and run focused tests green.
- [x] Run the full suite and independent review, then prepare the change for CREW pytest/syntax checks and its PR.

## Verification ledger

- Red: all four initial regressions failed against base7542f52: selection above six blocked, total clipped to six, later-request resume unavailable, and 33MiB originals sent as one request and rejected413.
- Green:58 focused photo tests passed, including 13-photo completion, preserved metadata/consent across groups, byte grouping, locked controls, rejected-request retry and a lost successful response with no automatic replay.
- Network-loss policy: a lost response can leave server-side photos saved without an acknowledgement. The page warns guests to check the gallery before retrying; this change does not claim exactly-once delivery after ambiguous network failures.

- Full local suite:240 passed, one known pre-existing failure in `tests/browser/test_guest_journey.py::test_original_mobile_navigation_labels_are_evenly_centered[320]`; that failure was previously reproduced on unchanged base. All upload-queue regressions pass.
- Independent Standards and Spec reviews: no material findings.
- Rollout: code-only through the CREW wedding release operation after merge; no new production dependency or host command.
