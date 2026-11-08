# Family seating and the shared guest QR

Hosts use **Admin → Seating** to create their own tables, then select families and
apply an assignment. A complete invitation/family sits at one table per event.
Selecting **Unassigned** removes an assignment; deleting a table returns all its
families to Unassigned. Changes appear immediately in guest name searches.

Capacity is optional and produces a planning warning rather than blocking a save.
Yes RSVPs supply the latest confirmed party size. No/Maybe/no-response families
use their invitation allowance as an explicitly labelled estimate. Inactive
invitations and those without permission for the event are excluded from search
and planned counts. Their existing assignments are retained and become visible
again if eligibility returns. No sample tables or assignments are created.

Existing viewer accounts can read and export; full administrators can change the
plan. Changes use existing CSRF protection and audit logs. CSV exports escape
formula-like family/table labels. Treat exports as guest data.

The guest landing page links seating, uploads and the gallery. Download its SVG
QR or copy its private link from Seating or Photos. Existing printed photo QR
codes keep working and link to the new pages. The existing
`WEDDING_PHOTO_SHARE_TOKEN` and `PUBLIC_BASE_URL` are reused; no new configuration
or dependencies are required. Seating works independently of photo feature flags
and R2 availability. Photo links follow their existing feature availability.

Guest searches match first, last, partner and display names, ignoring case and
accents. Blank searches display no names. All matches remain accessible through
pagination. Results contain only a family name and table label/unassigned message.
The QR is a shared guest link: anyone holding it can search family names and view
tables. Keep it within the intended wedding audience.

## Appearance

The bronze/ivory wedding theme uses Liquid Glass-inspired navigation and the host
event toolbar on supported desktop browsers. Names, results and forms have solid
surfaces. Phones and coarse-pointer devices use solid controls. Reduced
transparency, increased/forced contrast and reduced motion are respected. Desktop
users can enable **Solid controls**, saved on their device. Headless browser checks
do not establish physical Android GPU/flicker performance.

## One-time production rollout after merge

This release adds only `seating_tables` and `seating_assignments`. It does not
alter existing invitation, permission, event, RSVP or audit tables. The setup
script creates and validates these two tables in one transaction and can be rerun.
Incompatible existing seating tables cause an error rather than being altered.

The wedding code-only release agent rejects schema changes. Use an operator
rollout for this release. Review the merged commit and its successful GitHub CI,
then substitute its **full immutable SHA** below. Do not substitute a moving
branch name. These commands assume the current production directory, database,
service and account shown here have been verified. Run in a root shell. There is
no package installation or Nginx change.

```bash
set -euo pipefail
umask 022
cd /var/www/wedding-v3-101f73e
expected='REPLACE_WITH_REVIEWED_MERGED_FULL_SHA'
test -z "$(git status --porcelain)"
git fetch --no-tags origin refs/heads/main
test "$(git rev-parse FETCH_HEAD)" = "$expected"
previous=$(git rev-parse HEAD)
backup=$(mktemp -d /var/backups/wedding-before-seating-XXXXXXXX)
chmod 700 "$backup"
printf '%s\n' "$previous" > "$backup/previous-commit"
cp --preserve=mode,ownership .env "$backup/environment"
runuser -u postgres -- pg_dump --format=custom wedding_db > "$backup/wedding_db.dump"
chmod 600 "$backup/wedding_db.dump"
pg_restore --list "$backup/wedding_db.dump" > /dev/null

git checkout --detach "$expected"
if ! runuser -u www-data -- env APP_CONFIG=production \
  /var/www/wedding-v3-101f73e/.venv/bin/python -m scripts.apply_seating_schema; then
  git checkout --detach "$previous"
  echo 'Seating setup failed; previous code restored. Service was not restarted.'
  exit 1
fi

if ! systemctl restart wedding.service || ! curl --fail --silent --show-error --retry 12 --retry-connrefused \
  --retry-delay 1 --unix-socket /run/wedding/wedding.sock http://localhost/readyz; then
  git checkout --detach "$previous"
  systemctl restart wedding.service
  echo 'Readiness failed; previous code restored. Verify service readiness.'
  exit 1
fi
curl --fail --silent --show-error https://adlinprithvi.cloud/readyz
printf '\nSeating code and schema deployed. Backup: %s\n' "$backup"
```

The schema command runs as `www-data`, so it verifies actual service access to the
new source and environment. It uses the application's configured database user
and must have permission to create the two new tables and indexes. No credentials
are printed. `umask 022` is intentional for readable application source; private
backups have a separate 0700 directory and the database dump is 0600.

Verify in a normal browser:

1. Open Admin → Seating. Select the intended event and create a real table.
2. Assign a test/informed family. Search a name/partner name through the shared
   guest link and check the family and table. Move/unassign it and check again.
3. Check the QR landing page and the existing photo upload/gallery on a phone.
4. Check a viewer account cannot edit, and review the seating audit entries.
5. Remove any temporary host-created test table/assignment when finished.

Until the schema is installed, the new seating pages show a setup message (503);
existing invitation and photo routes continue working. Until a host adds tables,
guests see “Seating details are on their way.”

## Code rollback

Restore the recorded previous code revision only after confirming the production
working tree is clean, then restart `wedding.service` and verify `/readyz` locally
and publicly. Retain both additive seating tables and their assignments: the old
application ignores them. Do not restore the database dump for a code rollback,
since that would discard newer RSVPs and other updates. A database restore is a
separate operator recovery decision. Never run broad `db.create_all`, `drop_all`
or an unrelated migration chain for this feature.
