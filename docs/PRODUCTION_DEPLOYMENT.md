# Wedding V3 production deployment

This runbook deploys through Git and leaves the PostgreSQL schema unchanged.

## 1. Local verification

From `D:\Wedding_V3`:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m scripts.verify_schema_mapping
```

Commit and push only source files. Never commit `.env`, database exports, guest lists, or invite tokens.

```powershell
git status
git add .
git commit -m "Complete Wedding V3 production build"
git push origin main
```

## 2. Production `.env`

The VPS file `/var/www/wedding/.env` should include:

```dotenv
APP_CONFIG=production
SECRET_KEY=<private random value at least 32 characters>
SESSION_COOKIE_SECURE=true
TRUST_PROXY_HEADERS=true
TRUST_PROXY_COUNT=1
ASSET_VERSION=20260715-1
PUBLIC_BASE_URL=https://adlinprithvi.cloud
LOG_LEVEL=INFO

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=wedding_db
DB_USER=wedding_user
DB_PASSWORD=<database password>

RESEND_API_KEY=<resend key>
RSVP_EMAIL_FROM=Adlin & Prithvi RSVP <rsvp@adlinprithvi.cloud>
RSVP_EMAIL_TO=<comma-separated recipients>
```

Generate a secret locally or on the VPS:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Protect the file:

```bash
sudo chown root:www-data /var/www/wedding/.env
sudo chmod 640 /var/www/wedding/.env
```

Change `ASSET_VERSION` for every production release. A short Git commit hash is ideal.

## 3. Back up before deployment

```bash
PREVIOUS_COMMIT=$(cd /var/www/wedding && git rev-parse HEAD)
echo "$PREVIOUS_COMMIT" | sudo tee /var/backups/wedding_previous_commit.txt

sudo mkdir -p /var/backups/wedding
sudo -u postgres pg_dump -Fc wedding_db \
  > /var/backups/wedding/wedding_db_$(date +%Y%m%d_%H%M%S).dump
```

The database backup is precautionary. Phase 5 does not modify the schema.

## 4. Pull and install

```bash
cd /var/www/wedding
git fetch origin
git checkout main
git pull --ff-only origin main

/var/www/wedding/.venv/bin/python -m pip install -r requirements.txt
/var/www/wedding/.venv/bin/python -m pytest
/var/www/wedding/.venv/bin/python -m scripts.production_preflight --check-db
```

Do **not** run `flask db upgrade`.

## 5. Install service and Nginx configuration

```bash
sudo cp /var/www/wedding/deploy/systemd/wedding.service \
  /etc/systemd/system/wedding.service

sudo cp /var/www/wedding/deploy/nginx/adlinprithvi.cloud.conf \
  /etc/nginx/sites-available/adlinprithvi.cloud

sudo ln -sfn /etc/nginx/sites-available/adlinprithvi.cloud \
  /etc/nginx/sites-enabled/adlinprithvi.cloud

sudo systemctl daemon-reload
sudo nginx -t
```

The supplied Nginx file expects the existing Let's Encrypt certificate paths under:

```text
/etc/letsencrypt/live/adlinprithvi.cloud/
```

## 6. Restart and verify

```bash
sudo systemctl restart wedding
sudo systemctl status wedding --no-pager

curl --unix-socket /run/wedding/wedding.sock http://localhost/healthz
curl --unix-socket /run/wedding/wedding.sock http://localhost/readyz

sudo systemctl reload nginx
curl -fsS https://adlinprithvi.cloud/healthz
curl -fsS https://adlinprithvi.cloud/readyz
```

Then open a private invitation in a normal browser and test:

1. Welcome slideshow and countdown
2. Every Schedule event
3. RSVP create and edit
4. Attire dialogs
5. Calendar and directions
6. Travel, Registry, and Q&A
7. iPhone Safari and one desktop browser

## 7. Logs

```bash
sudo journalctl -u wedding -n 100 --no-pager
sudo journalctl -u wedding -f
sudo tail -f /var/log/nginx/error.log
```

Nginx access logging is intentionally disabled for `/invite/` so invite tokens are not written to logs.

## 8. Rollback

```bash
PREVIOUS_COMMIT=$(cat /var/backups/wedding_previous_commit.txt)
cd /var/www/wedding
git reset --hard "$PREVIOUS_COMMIT"
/var/www/wedding/.venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart wedding
sudo nginx -t && sudo systemctl reload nginx
```

No database rollback is needed unless a separate manual database change was made outside this release.
