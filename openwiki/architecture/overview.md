---
type: Reference
title: Architecture Overview
description: "Django project structure of mProv Control Center: apps, the MProvView generic REST base class, settings and env vars, LDAP and API-key authentication, session timeout middleware, and the signal-driven job automation pattern."
tags: [architecture, django, authentication, settings, signals]
---

# Architecture Overview

mPCC is a standard Django project (`mprov_control_center/settings.py`,
`urls.py`) whose domain apps are `systems`, `networks`, `osmanagement`,
`jobqueue`, `scripts`, `disklayouts`, and `utils`, supported by `authcustom`
and `common`. Everything an operator or machine client does flows through one
of two doors: the Django **admin** (Jazzmin-themed UI) or the **REST API**,
which together share the same models. Most cross-app side effects (rebuild an
image, re-sync a repo, regenerate PXE config) happen via **Django signals**
that enqueue work for [jobservers](/provisioning/job-queue.md) rather than
calling anything synchronously.

## Project layout

```
mprov_control_center/   settings, root urls.py, index + datamodel views
systems/                System, BMC, NIC, SystemImage, SystemGroup, NADS; PXE & power views
networks/               Network, NetworkType, Switch, SwitchPort; subnet-change APIs
osmanagement/           OSType, OSDistro, OSRepo (distro/repo definitions)
jobqueue/               Job, JobModule, JobServer, JobStatus + status-change feed
scripts/                Script, File, AnsiblePlaybook/Role/Collection (media artifacts)
disklayouts/            DiskLayout, DiskPartition, RaidLayout (stateful install geometry)
common/views.py         MProvView — the generic DRF base class for all model endpoints
authcustom/             custom User admin form only (stock User model)
static/                 boot scripts injected into initrds, CSS, logo, CodeMirror
install_scripts/        installer + install.d hooks; Dockerfile builds on these
```

Entrypoints: `manage.py` (loads `.env` via `django-dotenv`), WSGI under Apache
with `python38-mod_wsgi` in production (see
[Deployment](/operations/deployment.md)), and `mprov_control_center/urls.py`
as the single URL map documented in the [REST API page](/api/rest-api.md).

## The MProvView base class (`common/views.py`)

Every model endpoint in the API subclasses `MProvView`, a composition of DRF's
`ListAPIView` + Create/Retrieve/Update/Destroy mixins with house rules:

- `permission_classes = [HasAPIKey | IsAuthenticated]` — an API key
  (`Api-Key` header, from `rest_framework_api_key`) **or** a session/Basic/Token
  login both work.
- Class attributes `model`, `queryset`, `serializer_class`; models carry an
  `endpoint` class attribute used for URL/doc generation.
- **Self-documenting GETs**: a GET with a non-JSON `Accept`/content-type
  renders the view's class docstring as styled Markdown (AdminLTE template
  `docs.html`). Each endpoint's docstring is therefore its user-facing
  documentation — write docs there, not in a separate wiki, for API behavior.
- **Reflection-powered JSON structure**: `getJSONDataStructure()` walks model
  fields to emit a JSON-schema-like shape; exposed at `/datamodel/` and
  `/datamodel/?model=<app.Model>` (see `mprov_control_center/views.py`).
- GET list filtering by arbitrary query params matched against model fields;
  `?pk` retrieve bumps serializer depth to 3.
- `PUT` is explicitly rejected; use PATCH.
- **Anonymous impersonation rule**: an API-key (AnonymousUser) caller doing
  PATCH is attributed to `User(username='admin')`. Similarly, `created_by`
  FKs use `on_delete=SET(1)` and pre_save signals resolve the current request
  off Django's `get_response` stack frames, falling back to user pk 1. This is
  how provenance is recorded for machine traffic — keep it in mind when
  changing signal code.

## Authentication

Configured in `mprov_control_center/settings.py`:

- **Local users**: stock `django.contrib.auth.User` (`authcustom` only
  customizes the admin change-form to add a Change-Password button). Default
  admin/admin is created by the installer from `DJANGO_SUPERUSER_*` env vars —
  change it after install (README).
- **API keys**: `rest_framework_api_key`; keys are created in the admin
  (name only; expiry optional). This is the credential used by jobservers and
  by the [stateful installer running inside a chroot on a provisioning node](/provisioning/pxe-boot-flow.md#the-stateful-installer).
- **LDAP (optional, `LDAP_ENABLED=1`)**: `django_auth_ldap` with direct bind
  (`LDAP_USER_DN_TEMPLATE`), a mandatory group gate (`LDAP_ADMIN_GROUP` —
  users outside it cannot log in), and PosixGroup mappings of
  `LDAP_STAFF_GROUP`→`is_staff`, `LDAP_SUPER_GROUP`→`is_superuser`.
  `LDAP_SELF_SIGNED_CERT=1` disables TLS cert checking. `LDAPBackend` is
  ordered before `ModelBackend`, so local accounts keep working as fallback.
  Never commit real LDAP config; env var names are documented in `env.example`.
- **Session hygiene**: `django_session_timeout` middleware logs admins out
  after `SESSION_EXPIRE_SECONDS` (default 1800) of inactivity.
- **No-auth endpoints**: the PXE path (`/ipxe/`, `/images/`, `/osrepos/`),
  `systems/register`, and the index view set empty
  `authentication_classes`/`permission_classes` — they must answer before a
  node has any identity. See [REST API](/api/rest-api.md) for the full list and
  the security caveats.

## Settings and env vars

All environment-driven config is loaded from `.env` (django-dotenv) or real
environment (containers). Non-secret overview (see `env.example`):
`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` (must include the host's IP/FQDN or mPCC
won't answer), `TIME_ZONE`, `SESSION_EXPIRE_SECONDS`, `DB_ENGINE`/`DB_NAME`/
`DB_USER`/`DB_PASS`/`DB_HOST`/`DB_PORT` (SQLite default, MariaDB/Postgres
supported), the `DJANGO_SUPERUSER_*` trio, and the `LDAP_*` block. Do not read
or commit a live `.env`; `env.example` is the reference.

Notable non-env settings: static/media roots (`STATIC_ROOT = BASE_DIR/static`
— the same tree the iPXE template pulls boot scripts from; `MEDIA_ROOT =
BASE_DIR/media` holds uploaded scripts/files), `djangocodemirror` configured
for shell editing in the admin, Jazzmin UI icon/theme config, DB-backed cache
(`createcachetable`) used for [job status notifications](/provisioning/job-queue.md),
and `dbbackup` writing to `/var/www/mprov_control_center/backups/`.

## Signals as the event bus

The most important architectural pattern: **model saves are the trigger for
all provisioning automation**. Receivers in `systems/models.py`,
`networks/models.py`, and `osmanagement/models.py` translate entity changes
into [queue jobs](/provisioning/job-queue.md) (`pxe-update`, `dns-update`,
`dhcp-update`, `libgenders`, `image-update`, `repo-update`, and their `-delete`
counterparts), deduplicated with `update_or_create`. Some modules are fetched
defensively (`try: JobModule.objects.get(slug=...)`) so a missing JobModule
fixture row silently disables that automation — when "nothing rebuilds", check
that the JobModule exists. `osmanagement` uses `_post_save` attribute guards to
avoid signal recursion when signals re-save models.

## Change guidance

- Adding a model endpoint: subclass `MProvView`, add the serializer, register
  the URL in `mprov_control_center/urls.py` (or an app `*_urls.py`), put the
  user docs in the view docstring.
- Adding side effects to a save: prefer a signal that enqueues a JobModule
  over synchronous work; keep `update_or_create` dedup semantics.
- `static/` boot files have no build step and are served verbatim to nodes
  mid-provision; coordinate changes with the jobserver/image side (recent git
  history: busybox init rework, EFI bootloader fixes, idempotent boot_init).
