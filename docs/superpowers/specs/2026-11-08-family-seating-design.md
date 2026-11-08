# Wedding family seating and shared guest QR

## Intent and approved choices

Add the accepted seating-finder experience to the existing wedding website:
guests search by their own or their family's name and see the saved table;
hosts create tables, assign/move families and find unassigned invitations.
Use one QR landing page for seating, photo uploads and the gallery.
The user chose **one table per family/invitation**, rather than individual
member seating. They also requested Apple LGD styling.

## Approaches

- Chosen by the user: assign a complete invitation/family to one table per event.
- Alternative discussed: split individual members of an invitation across tables;
  the user selected the simpler family assignment.
- Builder choice: use two new PostgreSQL tables instead of an external service or
  private JSON files, preserving the existing Flask/SQLAlchemy architecture and
  database-backed guest identities. This requires a one-time schema rollout.

## Guest experience

- New `/photos/<token>/welcome` landing page uses the existing QR token and bronze,
  ivory, serif wedding identity. Its three actions are Find your table, Share
  photos and View gallery. Photo actions follow their existing availability.
- New `/photos/<token>/seating` page lets guests choose an event with configured
  tables and search by first name, surname, partner name or invitation display
  name. Matching ignores case and accents. Multiple matching families remain
  distinct choices. Results are paginated, not cut off at an arbitrary total.
- A result shows only the family display name and table label (or an unassigned
  message). No contact details, RSVP answers, invitation tokens, admin notes or
  other guest data appear. A blank search does not list names.
- No guest login, approval/publish step, date lock or selection quota is added.
- Both new paths stay under `/photos/`, whose existing Nginx location suppresses
  private-link access logs. Responses are no-store, noindex and no-referrer.
- New QR downloads encode the welcome page; already printed upload QR codes keep
  working, with shared navigation linking to seating and the welcome page.

## Host experience and data

- `/admin/seating` uses existing login and roles: administrators edit; existing
  viewer accounts can inspect. All changes retain CSRF protection and audit logs.
- Event selector includes the existing wedding events. Hosts create/rename/delete
  their own tables, optionally enter capacity and assign selected families.
- One family assignment per event. Invitations must be active and have an existing
  event-permission row. Table and assignment event IDs must agree in the database.
- Show All/Unassigned/Assigned filters, family search, current table and RSVP state.
  A No/Maybe/missing RSVP is a visible planning cue, not an assignment prohibition.
- Occupancy uses confirmed Yes guest counts; for other assigned invitations use
  their allowed party size as an estimate and label estimates clearly. Optional
  capacity produces an over-capacity warning, never a hard assignment rejection.
- Builder lifecycle decision, consistent with existing RSVP retention: deactivation
  or removal of event permission hides an existing assignment from guests and
  occupancy counts, but retains it for restoration if eligibility returns.
- Removing a family assignment returns it to Unassigned. Deleting a table states
  that its families will become unassigned, then does so atomically.
- Export an event's family/table list as CSV with spreadsheet-formula protection.
- No tables or assignments are invented or pre-populated by the application.

`seating_tables`: integer table_id primary key, event_id FK, name, optional
nonnegative capacity, timestamps; event/name case-insensitive uniqueness and a
(table_id,event_id) unique key for assignment integrity.
`seating_assignments`: (invitation_id,event_id) primary key, table_id, updated_by,
timestamps; invitation FK and composite table/event FK with deletion cleanup.
Existing invitation, event and RSVP tables remain unaltered.

## Styling and accessibility

Liquid Glass-inspired web treatment, not native Apple rendering. Glass belongs
on navigation and the event/host toolbar; result cards, names, table numbers and
forms use stable opaque surfaces. Preserve native labels, links, buttons,
keyboard focus, readable contrast and comfortable touch targets. No nested blur.
Use solid mobile/coarse-pointer surfaces because this site previously exhibited
an Android blur-compositing artifact. Honor reduced motion, high/forced contrast
and reduced transparency, and provide a visible solid-surface preference.

## Verification and rollout

Test table CRUD, family assignments/moves/unassigning, event isolation, inactive
and uninvited families, viewer/write protection, strict HTTPS CSRF, audit/CSV,
search variants and privacy, shared QR/navigation, missing schema and empty
states. Test realistic mobile/desktop browser flows, long names, keyboard use,
200% text, reduced effects and ongoing photo-upload regressions.

A schema script creates only the two new tables transactionally and is
idempotent. Verify it leaves existing records unchanged and document backup,
apply and rollback. This is a dependency-free feature, but the code-only release
agent cannot perform its new schema step. Deployment must include that operator
step after the PR is merged; the user has been informed.
