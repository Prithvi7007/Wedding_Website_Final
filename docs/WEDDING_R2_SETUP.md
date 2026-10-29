# Wedding QR photos — Cloudflare R2 production setup

**Code-only preparation. Neither photo uploads nor gallery is enabled by a merge.**

## Architecture

Guests still upload through the original Flask wedding website. Server-side
Pillow validation, resizing, and EXIF/GPS stripping happen before normalized
JPEGs are stored in a **private Cloudflare R2 bucket**. No durable JPEG copy is
written to the VPS in production. Flask and the reverse proxy may temporarily
buffer uploads while they are processed.

The private VPS directory stores **only** small JSON moderation records and a
lock file. Each JSON record is also mirrored to R2 for manual disaster recovery.
Keep independent encrypted backups of these records and the bucket; a mirror is
not a versioned backup.

The private bucket has no public domain. Guests receive no direct R2 URL,
signed URL, object key, or API credentials. Flask checks the unlisted QR token,
consent, approval and explicit publication before it serves any photo bytes.
Publish and Unpublish remain distinct admin actions.

## Create the bucket and secrets

1. In Cloudflare R2, create a **private Standard** bucket named something like
   `adlin-prithvi-private-photos`. Do not enable public r2.dev access or a
   public custom domain.
2. Create an R2 **Object Read & Write** API token scoped to this bucket alone,
   not the whole account. Keep its Access Key ID and Secret Access Key in
   the protected wedding service environment, never in Git, screenshots or chat.
3. Configure the Wedding production environment securely:

   ```dotenv
   PUBLIC_BASE_URL=https://adlinprithvi.cloud
   WEDDING_PHOTO_STORAGE_DIR=/var/lib/wedding-guest-photos
   WEDDING_R2_ACCOUNT_ID=<32-character-account-id>
   WEDDING_R2_BUCKET=adlin-prithvi-private-photos
   WEDDING_R2_ACCESS_KEY_ID=<secret-access-key-id>
   WEDDING_R2_SECRET_ACCESS_KEY=<secret-access-key>
   WEDDING_PHOTO_SHARE_TOKEN=<fresh-secret-random-url-safe-token>
   WEDDING_PHOTO_ENABLED=false
   WEDDING_PHOTO_GALLERY_ENABLED=false
   ```

   Generate a QR token locally using `secrets.token_urlsafe(32)`. Never share
   actual credentials here. Production always uses the R2 backend; local image
   persistence is available only in automated Flask test fixtures.
4. Provision `WEDDING_PHOTO_STORAGE_DIR/metadata` as a private,
   service-owned, persistent directory. **Do not configure a persistent
   `files/` image directory for production.** Back up metadata externally
   and monitor integrity of its mirrored R2 recovery copies.

## Service and Nginx prerequisites

- Install project `requirements.txt` into the wedding production virtualenv:
  Pillow, qrcode, boto3 and botocore. The existing Wedding release agent is
  **code-only** and cannot install Python dependencies or configure host
  folders safely. Use a separately authorized dependency-aware rollout.
- Keep HTTPS on the wedding domain. For the dedicated `/photos/` Nginx
  location set a request body limit of at least **32 MiB**, disable access
  logging to avoid recording the private QR URL, preserve upstream security
  headers and apply bounded upload rate limits. Validate `nginx -t` before
  reloading. Do not modify existing invitation/RSVP routes.
- Ensure egress to the Cloudflare R2 S3-compatible account endpoint works.
  Keep the bucket private and never expose the API credentials to browsers.
- Run image-processing security updates and record R2 spend/storage alerts.

## Required launch verification

1. Use an isolated QR token and an actual iPhone and Android phone over HTTPS.
2. Upload one photo, then six photos. Confirm EXIF/GPS is stripped, JPEGs
   appear in private R2, and no permanent JPEGs are on the VPS.
3. Check admin Inbox: photos are Pending and private. Approve privately;
   the guest image URL must still return 404 until separately Published.
4. Publish a consented photo; verify it appears only in the QR-linked gallery.
   Unpublish and check direct photo URLs return 404. Test deletion.
5. Confirm old photos without gallery consent cannot be published.
6. Confirm view-only admin accounts cannot review or access private media,
   and guests without the token cannot discover the gallery or image URLs.
7. Simulate an R2 outage: uploads fail with an appropriate error, rather than
   claiming success, with no partial persisted metadata.
8. Verify the private metadata backups and the independent encrypted R2
   export. Verify a documented recovery restore procedure.
9. Enable uploads with `WEDDING_PHOTO_ENABLED=true` only after completing
   the checks. Enable `WEDDING_PHOTO_GALLERY_ENABLED=true` separately.
   To stop new uploads but preserve the gallery, disable only uploads.

Cloudflare's endpoint format is
`https://<account-id>.r2.cloudflarestorage.com` with region `auto`.
Validate bucket quota, billing and monitoring settings before activating.
