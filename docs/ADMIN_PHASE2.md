# Wedding Admin Portal — Phase 2

Phase 2 adds complete invitation management to the secure admin portal.

## Included

- invitation directory
- search by ID, name, email, phone, side, or guest group
- active/inactive filtering
- event-access filtering
- sorting and pagination
- invitation detail page
- create invitation
- edit invitation
- dynamic event permissions
- independent maximum guest counts
- activate/deactivate
- copy private invitation URL
- explicit private-token regeneration
- transactional database writes
- server log entries for administrative changes
- responsive desktop and mobile layouts
- automated tests

## Data-safety rules

### Removing event access

Event access cannot be removed while an RSVP exists for that invitation and
event. The RSVP must be explicitly cleared in Phase 3 before permission removal.

### Lowering a guest limit

The maximum guest count cannot be lowered below the currently saved RSVP guest
count.

### Regenerating a token

Token regeneration:

- creates a cryptographically secure unique token
- immediately invalidates the previous private URL
- preserves invitation data, permissions, and RSVP records
- requires explicit confirmation

## Database impact

No schema migration is required. Phase 2 uses the existing:

- `invitations`
- `events`
- `invitation_event_permissions`
- `rsvps`

tables.
