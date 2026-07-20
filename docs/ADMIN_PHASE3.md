# Wedding Admin Portal — Phase 3

Phase 3 adds RSVP management and export capabilities.

## Included

- full invitation-event RSVP directory
- separate Yes, No, Maybe, and No response states
- search, filtering, sorting, and pagination
- filtered totals and confirmed headcount
- create and edit RSVP records
- clear an RSVP while preserving event access
- filtered CSV export
- spreadsheet-formula injection protection
- responsive layouts
- automated tests

## Safety rules

- RSVP editing requires an existing invitation-event permission.
- Yes requires at least one guest.
- Guest count cannot exceed the event-specific invitation limit.
- No always stores zero guests.
- Clearing removes only the RSVP record.
- No database migration is required.
