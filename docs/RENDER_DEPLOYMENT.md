# Deploy RECLAIM to Render

This configuration preserves HTTP pages, live WebSocket chat, Cloudinary uploads,
and WhiteNoise CSS/JS. It does not publish services or migrate existing data by itself.

## Before publishing

For the existing RECLAIM-2 deployment, confirm its build/start commands and
Environment variables before pushing to an auto-deployed branch. The local
`.env` is ignored and will not be uploaded. The updated base settings require
`SECRET_KEY` and Cloudinary credentials to be set in Render, where older code
previously supplied hardcoded defaults. Keep ReclaimDB's existing `DATABASE_URL`.
Switching to `lost_and_found.render_settings` additionally requires `REDIS_URL`
and installation via `requirements-render.txt`. Do not switch settings modules
until these variables and services are configured.

Rotate the database password and Cloudinary API secret previously entered in
`.env.example`. That file now contains placeholders. Keep real values in your
local ignored `.env` and Render's Environment settings only.

Review the files being committed: `.env`, `.backups`, local SQLite data, media,
and virtual environments must not be published. Some generated files and SQLite
were already tracked before this work; `.gitignore` alone does not untrack them.
Remove tracked runtime data from the Git index (keep local files) before pushing.
If secrets were previously committed, rotate them even if later removed.

## Services

Use the existing **RECLAIM-2** web service and **ReclaimDB** PostgreSQL database.
The local Git remote is `https://github.com/sabnem/RECLAIM.git`; confirm that
RECLAIM-2 is connected to this repository and the branch containing these changes.
In ReclaimDB's connection details, copy the Internal Database URL directly into
RECLAIM-2's `DATABASE_URL` environment variable. Do not put it in Git or chat.
Use the public URL shown by Render; do not infer it from the service name.

Create or reuse a Render Key Value service for chat.
Put all three in the same region. Set Key Value's eviction policy to `noeviction`
and restrict datastore connections to Render's private network where possible.
Use the PostgreSQL **internal** connection URL and Key Value's internal Redis URL.

For production, select a paid web service and a durable paid PostgreSQL plan.
Free PostgreSQL expires after 30 days; free web services sleep and block outbound
SMTP on ports 25, 465, and 587. Free deployment needs an HTTP email provider
integration before email-dependent flows can be considered working.

## Web service configuration

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Root directory | Leave blank (repository root) |
| Build command | `bash build.sh` |
| Pre-deploy command (paid service) | `python manage.py migrate --noinput` |
| Start command | `daphne -b 0.0.0.0 -p $PORT lost_and_found.asgi:application` |
| Health check path | `/login/` |

`.python-version` selects the latest Python 3.14 patch release. The build installs
dependencies, checks production settings and collects static assets. Migration
failure stops the deployment before the new service starts. Do not use Django's
development `runserver` or a WSGI-only start command.

## Environment variables

| Variable | Value |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `lost_and_found.render_settings` |
| `SECRET_KEY` | Generate a new long random value in Render |
| `DATABASE_URL` | PostgreSQL internal connection URL |
| `REDIS_URL` | Key Value internal connection URL |
| `CLOUDINARY_CLOUD_NAME` | Your Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Your Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Your rotated Cloudinary secret |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | Your email provider's SMTP host |
| `EMAIL_PORT` | `587` for STARTTLS |
| `EMAIL_USE_TLS` | `True` for STARTTLS |
| `EMAIL_HOST_USER` | Provider username |
| `EMAIL_HOST_PASSWORD` | Provider password/app password |
| `DEFAULT_FROM_EMAIL` | Verified sender address |

Render supplies `RENDER_EXTERNAL_HOSTNAME`; the application automatically allows
that hostname and uses its HTTPS URL for links and CSRF checks. Do not copy the
local `.env` file to Render: its localhost `SITE_URL` is unsuitable for production.
For a custom domain set `SITE_URL=https://your-domain`,
`ALLOWED_HOSTS=your-domain,www.your-domain`, and optionally
`CSRF_TRUSTED_ORIGINS=https://your-domain,https://www.your-domain`.

## Database and first launch

Migrations create the schema; they do not transfer existing SQLite users/items.
Choose an empty database or a deliberate data transfer before accepting public
traffic. Back up both databases before any import. Never run `flush` or overwrite
an existing production database to resolve a migration error.

After deploying, use Render Shell to run:

```bash
python manage.py showmigrations
python manage.py createsuperuser
```

Create the required item categories in Django admin for a fresh database.
If preserving local data, transfer it separately and verify image references:
Cloudinary assets stay in Cloudinary, while local media files need uploading.
Do not commit a data export or credentials to Git to perform the transfer.

## Release verification

### Claim tracking update (migration 0013)

This update adds persistent claim notifications and the Ended claim status.
Run `python manage.py migrate --noinput` against ReclaimDB before the updated
web process starts. The paid pre-deploy command above handles this. If your
service has no pre-deploy command, configure a release/start step that runs
the migration successfully before starting Daphne. Do not deploy new code
without this table: authenticated navigation queries unread notifications.

Members can use My claims to view sent/received requests. Rejected claims can
be appealed while an item remains available; ended claims cannot be reopened.
Notifications are stored in PostgreSQL and the badge polls every 30 seconds
while a page is visible. Opening a notification marks only that user's event
read. Existing claims remain visible, but past events are not backfilled.
Approval OTP delivery still uses the configured email provider.

Check the deployed HTTPS URL, not only the local server:

1. Home, login, and profile load with styles in light/dark mode on mobile/desktop.
2. Registration/login, CSRF-protected forms, and logout work.
3. Upload an item/profile image; verify its Cloudinary HTTPS URL and persistence
   after a redeploy.
4. Exchange chat messages between two accounts in separate browser sessions;
   check WebSocket connections upgrade successfully and messages persist.
5. Deliver a real OTP/password reset email and follow the public HTTPS link.
6. Complete a return, rating, statistics, and PDF download.
7. Confirm database backup/retention settings for the chosen plan.

Local tests do not prove external PostgreSQL, Redis, SMTP or Cloudinary service
connectivity. Those checks are still required after configuring your accounts.

References: [Django on Render](https://render.com/docs/deploy-django),
[Render free limits](https://render.com/docs/free),
[Channels deployment](https://channels.readthedocs.io/en/stable/deploying.html).
