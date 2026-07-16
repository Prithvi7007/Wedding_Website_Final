# Phase 5 — Production hardening and deployment readiness

## Included

- Release-versioned static asset URLs
- One-year immutable caching for release-versioned assets, with revalidation for unversioned nested modules and CSS background images
- Private/no-store caching for invitation and RSVP responses
- Content Security Policy with per-request nonce
- HSTS, frame denial, MIME sniffing protection, restrictive referrer and permissions policies
- Request IDs in responses and application logs
- Reverse-proxy awareness through `ProxyFix`
- Permanent 30-day invitation session containing only the internal invitation ID
- Graceful 503 response when the database readiness check fails
- Gunicorn production configuration
- Hardened systemd unit
- Nginx TLS, static delivery, compression, RSVP rate limiting, and private invite-token log suppression
- Read-only production preflight script
- Deployment and rollback runbook

## Database impact

None. No migration was generated, and no migration command is required.
