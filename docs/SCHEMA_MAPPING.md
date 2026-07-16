# Production schema mapping

The V3 models map directly to the existing `public` schema and do not rename or recreate production tables.

| Production table | V3 model | Primary key |
|---|---|---|
| `invitations` | `Invitation` | `invitation_id` |
| `events` | `Event` | `event_id` |
| `invitation_event_permissions` | `InvitationEventPermission` | `(invitation_id, event_id)` |
| `rsvps` | `RSVP` | `rsvp_id` |

## Confirmed production rules

- Invitation tokens are unique and cannot be blank.
- Invitation display names cannot be blank.
- Event IDs cannot be blank.
- Permissions are unique per invitation and event.
- `max_guests` must be positive.
- RSVP responses are restricted to `Yes`, `No`, or `Maybe`.
- RSVP guest counts cannot be negative.
- One RSVP exists per invitation and event.

The schema export showed duplicate rows for composite constraints because of the exporter join shape. The actual index definitions confirm the intended composite keys.
