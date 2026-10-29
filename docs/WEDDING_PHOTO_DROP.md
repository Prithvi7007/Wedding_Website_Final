# Wedding QR photo sharing and curated gallery

The original QR upload and gallery experience is preserved, but production
JPEGs are now stored in a **private Cloudflare R2 bucket**, not on the VPS.

**Authoritative production setup:** [WEDDING_R2_SETUP.md](WEDDING_R2_SETUP.md).

The Flask app retains private, small moderation metadata locally and mirrors
records into R2 for recovery. The hosts explicitly approve and publish photos;
old records without guest gallery consent cannot be made public.

Both photo feature flags remain disabled by default. A merge does **not**
configure or enable cloud photo storage. Do not use the legacy VPS-photo
deployment instructions: use the R2 rollout checklist instead.
