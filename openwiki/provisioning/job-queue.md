---
type: Reference
title: Job Queue and Jobservers
description: "How mProv Control Center delegates work to jobservers: Job/JobModule/JobServer/JobStatus models, signal-driven job creation from model saves, the pull-based claiming protocol, heartbeat garbage collection, artifact dependency injection, and the UI status-change feed."
tags: [jobqueue, jobserver, signals, dispatch, automation]
---

# Job Queue and Jobservers

mPCC never builds images or rewrites PXE/DNS/DHCP configuration itself. It
records intent as **Jobs** in the database, and external
[mprov_jobserver](https://github.com/mprov-ng/mprov_jobserver) daemons **poll,
claim, and execute** them. This makes the ORM an event bus between the
[domain models](/domain/data-models.md) and the worker fleet.

## Models (`jobqueue/models.py`)

- **JobModule** — job *type*, slug-as-PK, matching a jobserver plugin.
  Fixture slugs: `pxe-update/-delete`, `dns-update/-delete`,
  `dhcp-update/-delete`, `repo-update/-delete`, `image-update`, `image-delete`,
  `libgenders`, plus `nads`/`script-runner`. `active` gates/tracks claiming.
  Receivers fetch modules with `try/except`, so **a missing JobModule row
  silently disables that automation class**.
- **Job** — `name`, `module` FK, `params` JSONField, `status` FK (fixture pks:
  1 PENDING, 2 RUNNING, 3 FAILED, 4 SUCCESS; new jobs default to 1), nullable
  `jobserver` FK (null = unclaimed), timestamps, `return_code`. `save()`
  injects `params["deps"] = "repo-sync"` for `image-update` jobs — image builds
  implicitly wait for repo syncs.
- **JobServer** — self-registering worker: `name` (unique), `address`,
  `port` (default 8080), `heartbeat_time`, `one_minute_load`, M2M `jobmodules`
  (capability advertisement), optional management `network`. Other code selects
  artifact hosts by lowest `one_minute_load` (see
  [/images/ redirects](/provisioning/pxe-boot-flow.md#2-artifact-redirects-imageslugext-imagesapiview-no-auth)).
- **JobStatus** — plain name rows referenced by pk.

## Job creation is signal-driven

Users rarely create Jobs directly; model saves do it (`systems/models.py`,
`networks/models.py`, `osmanagement/models.py`):

| Trigger | Jobs created | Notes |
|---|---|---|
| Save System / NetworkInterface / SystemBMC | `pxe-update`, `dns-update`, `dhcp-update` | `update_or_create` dedup by name+module, status reset to PENDING |
| Save System / SystemImage / SystemGroup | `libgenders` | rebuild genders host DB |
| Save / delete Network | `pxe/dns/dhcp-update` or `-delete` | |
| `SystemImage.needs_rebuild=True` | `image-update` (params `imageId`, `origin`) | **creates**, bumps `version`, clears `jobservers` so `/images/` won't serve stale hosts |
| Delete SystemImage | one `image-delete` **pre-assigned per hosting jobserver** | the only server-pinned job type |
| OSRepo saved with `update and managed` | `repo-update` (params `repo_id`) | bumps `version`, clears `hosted_by` |
| Delete JobServer | `repo-update` for **every** repo | failover redistribution |
| NADS registration (`systems/register`) | `pxe-update` | |

## Claim protocol (pull, not push)

There is no server-side dispatcher (except the pinned `image-delete` jobs).
A jobserver:

1. **Heartbeats**: `POST /jobservers/` — `update_or_create` by name, refreshing
   `address/port/one_minute_load/heartbeat_time` and adding its jobmodules.
   `JobServer.save()` garbage-collects any servers whose heartbeat is >60 s
   stale (checked at minute boundaries), and a pre_save signal fixes naive
   timestamps to be tz-aware. Dead workers vanish automatically; jobs they
   held keep their assignment until re-queued by the signals above.
2. **Polls**: `GET /jobs/?module=<slug>&status=1&jobserver=...` —
   `JobAPIView.get` filters by module (scalar or JSON array), `params` (JSON
   contains), status, and jobserver.
3. **Claims**: `PATCH /jobs/<id>/` setting `jobserver`, `status=2`,
   `start_time`; completion PATCHes `status`, `end_time`, `return_code`.

Endpoints: `/jobs/`, `/jobmodules/`, `/jobservers/` (`jobqueue/*_urls.py`),
documented further in [REST API](/api/rest-api.md).

## Status notifications (`jobqueue/signals.py`)

Purely observational: `pre_save` stashes the old status, `post_save` appends
`{job_id, old_status, new_status, timestamp}` to the Django DB cache (last 50,
TTL 300 s), and `GET /jobqueue/status-changes/` drains it for admin-UI toast
notifications. No dispatch logic lives here — don't add any by mistake.

## Change guidance

- New job type = new JobModule slug in fixtures + a signal/receiver that
  creates it + a plugin in the jobserver repo; test that the dedup
  `update_or_create` key (name+module) still fits.
- Keep `image-delete` semantics (one job per hosting server) — jobservers use
  the pre-assignment to clean only their own copy.
- Heartbeat GC is aggressive (60 s); any jobserver change must keep heartbeat
  cadence well under that.
