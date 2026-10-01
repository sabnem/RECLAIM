# Maintenance notes

## Cleanup snapshot

A source archive and SQLite backup were created before this cleanup under
`.backups/cleanup-20261001-002358/`. The old generated static output is preserved
there as well. These backups contain private configuration/history and must stay
local. No user uploads, account data, database migrations, or dependency versions
were removed or replaced.

## Asset organization

The shared CSS was extracted from template includes without changing cascade
order: legacy `style.css`, navigation `sidebar.css`, page-specific styles, then
`layout.css`, `account-pages.css`, and `dark-theme.css`. Page overrides remain
after page-specific styles so light/dark mode and responsive layouts stay stable.
`sidebar.js` and `theme.js` hold shared interaction behavior. `inbox.js` and
`chat.js` keep messaging code out of the HTML template; escaped data attributes
provide its URLs and per-request values. Django's static
storage fingerprints and compresses these files during `collectstatic`.

Vendor files remain pinned to Bootstrap 5.3.2 and Bootstrap Icons 1.11.3. Keep
source maps, font variants, and licenses with the assets: missing referenced files
cause the production manifest build to fail. Re-run `collectstatic` after changing
assets; do not edit its output directly.

The unused carousel stylesheet and empty background stylesheet were archived in
`.backups/cleanup-20261001-002358/unused-assets/`. Legacy notes were moved intact
to `docs/legacy/`; they are retained for reference rather than treated as current
setup instructions.

## Code and database performance

- Shared template data lives in `context_processors.py` instead of views.
- Duplicate module imports and the duplicate profile-picture route were removed.
- Item lists fetch categories in the item query; inbox lists fetch profile data
  with participants rather than querying each avatar separately.
- `return_statistics_for()` uses one conditional aggregate for seven totals and
  one grouped query for ratings, replacing twelve separate aggregate queries.
  Leaderboards, recent returns, and monthly history retain their existing data.
- Reputation counters use one aggregate plus one update instead of loading every
  rating into Python. Regression tests enforce both query budgets.
- WebSocket diagnostics use standard logging instead of printing message bodies.

## Verification

The 17-test Django regression suite covers public and member pages, registration, login/logout,
reporting and filtering, claims/approval/OTP/return records, ratings and reputation,
PDF export, message permissions, archive/restore, and WebSocket message, typing,
edit, and delete events. Tests create their own temporary database. Cloudinary
uploads and live SMTP delivery require external credentials and are not exercised
by these isolated tests.

Before extending behavior, run the tests and migration check from the README.
The cleanup was also checked in the browser at 390px and 1440px in both themes.
An active-chat preview exercised sending, editing, deleting, and mobile back
navigation using intercepted WebSocket responses, with no test messages saved to
the working database. Live socket events are separately covered by the Django tests.
Visual changes still need browser checks of both themes and phone/desktop layouts.

## Runtime static files

Keep the generated `staticfiles/` directory in place while serving with
`DEBUG=False`. WhiteNoise serves it directly, including fingerprinted files from
its manifest. Git-ignoring generated files does not mean they can be removed from
a running deployment. After an asset change, run `collectstatic --noinput` and
restart the server so the manifest and WhiteNoise file index agree. Validate the
actual LAN URL as well as localhost before declaring the deployment healthy.
