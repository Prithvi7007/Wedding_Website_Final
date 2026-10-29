# Guest photo QR — opt-in launch checklist

The QR photo collection adds a **public-by-link uploader**, a **private host moderation inbox**, and a **guest-visible gallery of explicitly published photos**.
Pending and approved-but-unpublished uploads stay private. Only images explicitly published by the hosts are available to holders of the unlisted QR link; invitation/RSVP records are unaffected.
The feature is **disabled by default**. Deploying these code changes alone does
not make guest uploads available.

## Guest experience

- The host prints an SVG QR from **Admin → Guest Photos**.
- Guests scan the QR, choose up to **6** photos from a mobile camera roll,
  optionally add a name and celebration moment, and submit.
- The browser tries to convert selected photos (including camera formats the
  browser can decode) into compressed JPEGs before sending them. Without JS,
  JPG/PNG/WebP uploads still work. HEIC must be convertible by the browser;
  otherwise ask guests to export as JPG.
- Each uploaded photo is limited to 12 MiB; each request to 32 MiB. The server
  decodes and resizes photos to at most 2600 pixels on the longest side and
  strips all original EXIF/GPS metadata by re-encoding fresh RGB pixels.
- Guests must explicitly acknowledge that host-approved photos may be displayed in the guest gallery.
- Guests see a thank-you screen and a link to the approved-only gallery. Pending photos, submitter names and deleted images are never exposed in gallery HTML or image routes.
- Hosts first approve a photo for their private collection, then explicitly publish it to the guest gallery. Unpublishing revokes live gallery access; deleting also removes the stored file. Neither can recall prior downloads or backups.

## Host prerequisites: must be in place BEFORE enabling

1. **Dependencies**: install the exact project `requirements.txt` into the
   running Wedding venv (not just the CI environment). Verify Pillow and
   `qrcode` import successfully. Confirm the Wedding release agent supports
   a dependency-bearing code rollout; don't bypass its code-only safety gate.
2. **Durable private storage**: use a dedicated directory **outside**
   `/var/www/wedding`, its `app/static` folder, and all Git-managed folders.
   Example commands for a host administrator (adjust to their deployment):

   ```bash
   sudo install -d -m 0700 -o www-data -g www-data /var/lib/wedding-guest-photos
   sudo install -d -m 0700 -o www-data -g www-data /var/lib/wedding-guest-photos/files
   sudo install -d -m 0700 -o www-data -g www-data /var/lib/wedding-guest-photos/metadata
   ```

   Back up **both** `files/` and `metadata/` independently of code rollouts.
   Verify storage persists across reboots/rollbacks and that it is excluded from
   web-server static aliases. Do not add the image directory to Git.
3. **Nginx upload limit and access logs**: the shipped Nginx configuration
   currently has `client_max_body_size 2m`, too small for photo uploads.
   Have the host operator configure a **dedicated** location for `/photos/`
   with at least `client_max_body_size 32m` and `access_log off` so the
   bearer-token URL cannot enter normal access logs. Preserve the upstream
   headers, CSP, TLS termination, and existing RSVP/invitation rate limits.
   Add a suitable bounded request rate for this path (remember guests at the
   venue may share a NAT IP), test Nginx config before reloading, and do not
   change host settings through the code-only release agent.
4. **HTTPS canonical URL and secret token**: set these in the secured Wedding
   environment file, not in Git or in a screenshot:
   
   ```dotenv
   PUBLIC_BASE_URL=https://adlinprithvi.cloud
   WEDDING_PHOTO_STORAGE_DIR=/var/lib/wedding-guest-photos
   WEDDING_PHOTO_SHARE_TOKEN=<fresh-cryptographically-random-token-with-at-least-24-url-safe-characters>
   WEDDING_PHOTO_ENABLED=true
   WEDDING_PHOTO_GALLERY_ENABLED=true  # Enable separately after gallery review
   ```

   Generate a token locally with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`
   and replace the placeholder. Anyone with the QR link can upload; rotate the
   token if it leaks or the upload period ends. Do not include the token in
   analytics, support tickets, or publicly shared screen captures.
5. **Disk monitoring and backups**: the application bounds the collection to
   2500 photo records; plan free disk space and backup/retention accordingly.
   A deleted photo's bytes are removed immediately and only a private metadata
   tombstone remains. Backups may retain deleted bytes until backup expiry.
6. **Image processing is a trust boundary**: Pillow decodes untrusted guest
   uploads. Keep it patched; do not serve originals, SVG, GIF, arbitrary
   user-supplied filenames, or image metadata publicly.

## Live smoke test before printing any QR

- Check `/admin/photos` as Prithvi or Adlin: QR and copy-link appear.
- Test the QR from an actual iPhone and Android device over HTTPS.
- Confirm JPG, camera-roll HEIC conversion where supported, and multiple-photo
  upload. Confirm the correct success message; while the gallery switch is off, no guest gallery is accessible.
- Verify a submitted photo appears under Pending in Admin and stays hidden from guests. Approve it and verify it is **still private**, then Publish it. Confirm it appears at /photos/<token>/gallery, Unpublish to revoke access, Publish again, and Delete to remove it permanently.
- Verify users without the QR token and view-only family accounts cannot access pending photo bytes, admin download or review. Anyone holding the QR link can view **approved** images without an invitation.
- Verify upload errors show clear messages and Nginx doesn't reject normal
  batches before they reach Flask. Test at narrow 320px width.
- Confirm backups actually include the storage directory, then print the QR.
- To stop receiving uploads after the wedding, set
  `WEDDING_PHOTO_ENABLED=false`; this does **not** delete stored photos.

## Implementation notes

- Metadata is private, atomic JSON per photo. A filesystem lock serializes
  write/review operations across Gunicorn workers; no PostgreSQL migration.
- Only full Wedding admin accounts may view pending/unpublished photos, approve, publish, unpublish, download and delete. Only **published** images are served to holders of the unlisted QR link. Submitter names are never published to the guest gallery.
- Admin publication is a separate explicit action after private approval. Review each image carefully because QR recipients can copy published photos.
- The guest form has Flask-WTF CSRF protection, an anti-bot honeypot and server-validated consent.
- The QR upload page alone permits local blob: image previews in its Content Security Policy for phone uploads; the rest of the site retains its current policy.
- Do not put uploaded image files under the application's static folders.
- The QR is server-generated SVG, not rendered through a third-party QR
  website, so the secret token stays on your own domain.
