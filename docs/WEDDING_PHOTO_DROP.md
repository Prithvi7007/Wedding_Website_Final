# Wedding QR photo sharing and instant gallery

The original QR upload and gallery experience is preserved, but production
JPEGs are now stored in a **private Cloudflare R2 bucket**, not on the VPS.

**Authoritative production setup:** [WEDDING_R2_SETUP.md](WEDDING_R2_SETUP.md).

The Flask app retains private, small moderation metadata locally and mirrors
records into R2 for recovery. New consented uploads appear immediately in the QR-linked gallery. Hosts can
Hide, Show or Delete photos in one step; old hidden records stay hidden, and
records without guest gallery consent cannot be shown.

Accepted image inputs include JPEG, PNG, WebP, HEIC/HEIF, AVIF, GIF, BMP and
TIFF. The browser prepares a JPEG where supported; otherwise the server decodes
the original (up to 12 MiB). All stored images are normalized JPEGs with metadata
removed. Multi-frame images use the primary HEIF frame or the first frame for
other formats. Install the new `pillow-heif` requirement before rollout.

Both photo feature flags remain disabled by default. A merge does **not**
configure or enable cloud photo storage. Do not use the legacy VPS-photo
deployment instructions: use the R2 rollout checklist instead.

Guests can select more than six photos in the JavaScript upload page. The page
prepares and sends them sequentially in groups of up to six, with a 30 MiB image
payload target below the existing 32 MiB request limit. These are transport
batches, not a selection-count limit. The server's per-request validation is
unchanged. Automatic grouping runs in JavaScript; direct endpoint requests
still follow its existing six-file request contract.

The page reports progress across the full selection. If a later request is
rejected, acknowledged files remain shared and Retry sends the remaining queue.
Network interruption or an unreadable response is not automatically retried:
the page asks guests to check the gallery because the server may have saved
photos before the response was lost. Reloading the page loses the browser queue.
