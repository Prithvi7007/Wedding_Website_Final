# Wedding Admin Portal — V3 Audit and Phase 1

## Production source of truth

The current `v3-production` branch is a modular Flask application using:

- an application factory
- Flask Blueprints
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-WTF global CSRF protection
- PostgreSQL in production
- invitation-token guest sessions
- application-wide security response headers

The older root-level `app.py`, `index.html`, `dashboard.html`, and `style.css`
attachments belong to the earlier hardcoded/Excel prototype and are not used by
this implementation.

## Schema findings

### Invitations

The current model contains:

- `invitation_id`
- `represent_side`
- `first_name`
- `last_name`
- `partner_name`
- `display_name`
- `guest_group`
- `message`
- `invite_token`
- `email`
- `phone`
- `is_active`
- `created_at`
- `source_key`
- `invite_message`

The V3 model currently has no `access_code` column. The admin portal therefore
does not invent or query that field.

### Events

`event_id` is a text primary key. Event cards and summaries are loaded
dynamically and do not hardcode IDs.

### Permissions

`invitation_event_permissions` uses the composite key
`(invitation_id, event_id)` and requires `max_guests > 0`.

### RSVPs

The RSVP table has an integer `rsvp_id` and a unique constraint on
`(invitation_id, event_id)`. Stored values are currently `Yes`, `No`, and
`Maybe`.

## Reporting limitation

A declined RSVP stores `guest_count = 0`. The application can truthfully show:

- confirmed attending individuals
- declined RSVP records
- maybe RSVP records

It cannot infer the number of individuals represented by a declined household.
The dashboard therefore labels this metric `Declined responses`.

## Phase 1 included

- `/admin/login`
- POST-only `/admin/logout`
- protected `/admin`
- environment-based admin password
- constant-time password comparison
- 30-minute inactivity timeout
- CSRF-protected forms
- dynamic event metrics
- recent RSVP activity
- active invitations without any RSVP
- responsive admin design
- automated tests
- no schema migration

## Next safe phase

Phase 2 will add invitation search, creation, editing, event permissions, maximum
guest counts, activation, private-link copying, and explicit token regeneration.

When removing event access, the safe strategy will be to block removal while an
RSVP exists. The RSVP must be explicitly cleared first, preventing silent data
loss.
