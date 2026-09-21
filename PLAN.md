The plan for Haus is to build a household management app.  This will be a web app for users on my internal network.  It will keep track of meal planning, house inventory, and school stuff for the kids.

# Technology Stack
This will likely run on a Raspberry Pi 5 equipped with a 1TB SSD drive, so space won't be an issue, but I'd like to keep the code tight.  To that end, I'd expect:

* linux
* python
* bootstrap for the front-end (which should be responsive)
* front-end javascript can utilize whatever framework the agent swarm thinks is best
* a database that will fit within the 16GB of RAM that the Raspberry Pi 5 has
* but also the site needs to be simply migrated (ie.: having a separate database file like DuckDB might work)

# Time
A week starts on Monday and runs through Sunday.

# Users
Four users total.  Each user will need to register (using OAuth like Google accounts); the first registered user will be the site administrator.  Once the first user is registered, the additional users will be added via an invite URL that they will open (and stop working after the first use), and then they must register using a Google account.

* Require a non-default `HAUS_SESSION_SECRET` before production deployment.
User Levels:
* administrator
* parent
* child

Each user will have a history, viewable only by parents and administrators.  It should include:
* logins
* meals requested with date

* Google OIDC boundary complete: configured login/callback routes, signed
	browser sessions, fail-closed behavior when credentials are absent, and
	registration through the identity service are in place.
* Authorization boundary started: current-user lookup, active-user checks,
	role enforcement, and parent/admin invitation issuance are in place.
* Break-glass recovery complete: `haus-admin recovery-token` creates a
	short-lived, single-use, hashed and audited administrator grant that the web
	app consumes into a normal signed session.
* Meal-planning foundation complete: reusable dishes, named ingredients,
	optional recipe URLs, monthly-limit metadata, Monday-based week keys, meal
	day approval defaults, Feral Day restrictions, and the first seven-day
	calendar API are covered by tests.
* Meal workflow complete through history: parent/admin approval,
	disapproval/rescheduling, cooking events, monthly-limit enforcement, and
	one-rating-per-user dish ratings are covered by tests.
* Shopping workflow complete: authenticated calendar and shopping reads,
	approved/non-Feral ingredient aggregation with repeated-name counts, and
	printable ReportLab PDF output are covered by tests.
* Invitation management complete: parent/admin listing, one-time token
	consumption, audited revocation, and migration support are in place.
* Calendar UI complete: authenticated server-rendered Bootstrap week view,
	week navigation, meal state display, recipe links, and shopping PDF access
	are in place and covered by route tests.
* Inventory foundation complete: room/container locations, item metadata,
	optional photo paths, active/inactive lifecycle fields, case-insensitive
	search, and authenticated location/item/search APIs are covered by tests.
* Inventory lifecycle complete: loan history, open-loan reporting,
	parent/admin-only returns, donated/sold dispositions, released-item reports,
	and authenticated lifecycle routes are in place and covered by tests.
* Next implementation block: photo upload handling, then deployment hardening
	and household acceptance testing.
Each dish has a title, a list of ingredients.  We should keep track of it's history (when it's been made and who made the request and who cooked), including ratings of what everyone thought of it (everyone can put a star rating on dishes), and some dishes should have limits to the number of times per month (where 0 = no limit).

Each day has a dish suggestion that is then approved, disapproved, or rescheduled by the parents/administrators.  (Admins/parents suggestions are approved automatically.)

A day can be listed as a "Feral Day" in which there is no meal scheduled, wherein everyone in the house has to fend for themselves.  Children cannot suggest Feral Days.

A week of dishes can have a shopping list generated.  That list will include the ingredients needed.  If an ingredient is would be listed twice, it should be listed as "Ingredient Name, x2".  The output should be a basic PDF that can be printed by the user requesting the list.  The list should have a title that indicates the date range.

## Views:
* calendar view with meal titles for that day
* shopping list (PDF)

# Inventory Control
This is a tool used for keeping track of where various items are stored throughout the household.  Every item has a room, with a container.  An item has a name, description (optional), a category (optional), serial number (optional), and a photo (optional).

Items can be marked as donated or sold and be moved off the active list.  There should be a report on those, including dates that they were released from the active list of items.

Items can be loaned out.  We should keep track of to whom they were loaned and on what date.  Only administrators and parents can mark an item as returned.

## Reports
- what's on loaned-out status
- what's been donated in a particular year

## Search
This will need the ability to search by an Item name (autocomplete in this form field would be awesome) so that we can find them.

# Education
This should log into the Kids' Schoology and Infinite Campus -- using the admin user's login credentials -- so that we can scrape their current grades per class, and list any homework due or past due for each class (with dates).

# Working Strategy

This is a small, private household application. The first version should favor
clarity, reliability, and easy recovery over a distributed architecture.

## Proposed Technology

* Python 3.12+
* FastAPI for the HTTP application
* Server-rendered Jinja templates with Bootstrap for responsive UI
* Small amounts of browser JavaScript for autocomplete, calendar interactions,
	and background refresh; no separate SPA unless the UI proves to need one
* SQLAlchemy with SQLite in WAL mode for transactional application data
* Alembic for schema migrations
* ReportLab for printable shopping-list PDFs
* pytest for unit and request-level tests

SQLite is a better initial fit than DuckDB because Haus is primarily a
transactional application: several household browsers may submit changes,
sessions and invitations must be updated atomically, and audit history needs
durable constraints. The database remains a portable file and can be backed up
or migrated without operating a separate database server. DuckDB could still
be useful later for reporting, but it should not be the system of record.

## Application Shape

Keep one deployable application with modules for:

* identity, invitations, roles, sessions, and audit history
* meal planning, approvals, dish history, ratings, and shopping lists
* inventory, locations, loans, dispositions, photos, and search
* education sync and cached school data

Each module should own its routes, service logic, templates, and tests where
practical. Business rules belong in service functions rather than only in
templates or route handlers. Store timestamps in UTC and display them in the
household timezone (`America/Chicago`).

## Identity And Permissions

Use Google OpenID Connect for sign-in. The first successful registration is a
one-time bootstrap flow that creates the administrator; all later accounts
require a single-use, expiring invitation. Store the provider subject ID as
the stable identity key rather than relying only on an email address.

Authorization must be enforced server-side for every write and protected
read. The role matrix should be explicit, especially for child meal requests,
Feral Days, history, loans, and user administration. Record successful and
failed login events, invitation creation/use/expiry, and important domain
changes in an append-only audit log.

## Household Discovery And FQDN

Use `haus.home.arpa` as the canonical address; `home.arpa` is reserved for
home networks. The household router provides local DNS that maps the name to
the Raspberry Pi.
Avahi/mDNS can optionally advertise `haus.local` as a convenience fallback,
but it should not be the only name because `.local` behavior varies across
clients.

Put Caddy or another small reverse proxy in front of the app. It should own
HTTPS, redirect HTTP to HTTPS, and proxy only to the loopback/container
network. Use a locally trusted certificate authority for the internal FQDN,
or document the trust setup for household devices. Google OAuth redirect URIs
must exactly match the canonical HTTPS hostname; keep a temporary localhost
development callback separate from production.

The first-run setup should display the configured household URL and a health
check, but the app should not expose itself to the public internet or require
port forwarding.

Confirmed for the first deployment:

* Haus is local-only. Cloud deployment is a possible future architecture, not
	a requirement for the initial design.
* The household router provides local DNS and maps `haus.home.arpa` to the
	Raspberry Pi.
* Google sign-in is required for all household members.
* Children may view their own grades and activity history. Parents and
	administrators may view household history.
* School credentials may be stored on the Pi, but they must be encrypted at
	rest, excluded from logs, and excluded from backups unless the backup is
	encrypted. Credentials must never be returned to the browser after setup.
	A provider-side session or token should be preferred over repeatedly storing
	a password when possible.

Meal planning is intentionally lightweight. Ingredients are names only, with
no quantity or unit tracking in the first version. A dish may optionally store
an external recipe URL for quick access; Haus does not need to import or
manage recipe instructions.

## Deployment And Recovery

Target a 64-bit Raspberry Pi OS installation with the SSD mounted for the
database, uploaded photos, generated PDFs, and backups. A Docker Compose
deployment is a reasonable first target: app, reverse proxy, and persistent
storage are easy to reproduce on another Linux host. A systemd deployment can
remain the fallback if container overhead or ARM package support becomes a
problem.

The deployment must define:

* environment-provided secrets and Google OAuth configuration
* persistent paths for SQLite, media, and backups
* health checks and structured logs to stdout/journald
* a documented migration command run before starting a new application version
* a documented manual export/backup procedure before migrations or major
	maintenance
* an explicit decision about where an occasional copy should be stored for
	protection against SSD failure or accidental deletion

Routine scheduled backups are not required for the initial household
deployment. This is a deliberate tradeoff: low operational overhead is more
important than protection against every failure mode, while manual recovery
steps still provide a way to protect the data before risky changes.

## Delivery Order

1. Project skeleton, configuration, database migrations, health endpoint, and
	 test setup.
2. Bootstrap administrator, Google sign-in, invitations, roles, sessions, and
	 audit history.
3. Meal planning and calendar, including approval rules and week-based
	 shopping-list PDF generation.
4. Inventory, photos, loans, dispositions, reports, and item autocomplete.
5. Raspberry Pi packaging, local DNS/FQDN, HTTPS, and recovery procedure.
6. Education as a separately permissioned, cached sync with clear failure
	 status and manual refresh, designed after the first two blocks prove the
	 application's core patterns.
7. Household acceptance testing and deployment hardening.

## Open Questions To Resolve

* What exact CLI command and safeguards should be used for break-glass
	administrator recovery? It should require direct access to the Pi, be
	disabled or audited after use, and never create a normal browser password
	login.
* Can Schoology and Infinite Campus be accessed through an approved API or
	export? If browser automation is unavoidable, what are the school/provider
	terms, MFA requirements, and acceptable credential-storage policy?

# TODO

* Decide where an occasional manual database/media copy should be stored to
  protect against SSD failure or accidental deletion.
* Validate `docker compose config` on a host with the Compose plugin; this
	development environment has Docker but not the Compose subcommand.

# Build Notes

* Foundation complete: the packaged FastAPI application exposes `/health`,
	uses `uv` for dependency management, and has a passing request-level test.
* Database foundation complete: environment-backed settings, SQLAlchemy, and
	isolated SQLite metadata initialization are in place.
* Identity data foundation complete: Alembic migrations, Google-subject user
	identity, first-user administrator bootstrap, hashed single-use invitations,
	login events, and audit events are covered by tests.
* Google OIDC, invitations, roles, recovery, meal planning, calendar UI,
	shopping PDFs, and inventory workflows are implemented with migrations and
	tests.
* Inventory photo uploads are bounded to 5 MB, image-only, authenticated, and
	stored below the configured media directory.
* Deployment foundation is documented: configurable binding, Docker packaging,
	persistent Compose storage, required production secrets, health checks, and
	Caddy internal TLS for `haus.home.arpa`.
* Next implementation block: Pi deployment and household acceptance testing,
	then education integration design.
