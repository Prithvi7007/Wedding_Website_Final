# Wedding V3 — Phase 3.1 Modal and RSVP Fix

This patch fixes the Schedule-tab RSVP and attire dialogs being clipped by an event card or appearing behind the following event.

## Root cause

The fixed-position dialog markup was nested inside `.cinematic-event-card`, which uses `overflow: clip` and its own stacking context. The animated tab also retained an identity transform after its entrance animation. Together, those rules caused browser engines to contain or clip the dialogs instead of treating them as true viewport overlays.

## Changes

- RSVP and attire dialogs now render in one dedicated modal layer outside all event cards.
- JavaScript moves that layer directly under `<body>` while Schedule is mounted.
- The modal layer sits above the header, slideshow, logout control, and celebration canvas.
- Backdrop click, close button, Cancel, and Escape all close the active dialog.
- Focus is trapped inside the open dialog and returned to the original trigger on close.
- Background schedule content becomes inert while a dialog is open.
- Body and document scrolling are locked while a dialog is open, including touch handling for iOS.
- RSVP controls continue working after the modal layer is portaled.
- Saved guest count and notes are synchronized with the server response.
- The tab entrance animation now ends at `transform: none` instead of retaining a transformed containing block.

## Install

Extract the upgrade ZIP directly into `D:\Wedding_V3` and choose **Replace files**.

Then run:

```powershell
cd D:\Wedding_V3
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m flask --app wsgi.py run --debug
```

Keep the SSH tunnel open while testing RSVP persistence.

No database migration is included or required.
