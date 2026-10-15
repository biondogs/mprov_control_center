---
type: Reference
title: REST API Surface
description: "mProv Control Center REST API: complete endpoint map from urls.py, the three auth tiers (API key/session, no-auth PXE endpoints, self-service ?self access), network subnet-change confirmation endpoints, datamodel introspection, and documentation-by-docstring behavior."
tags: [api, rest, endpoints, authentication, introspection]
---

# REST API Surface

All endpoints are declared in `mprov_control_center/urls.py` (plus app
`*_urls.py` includes) and implemented on the
[`MProvView` base class](/architecture/overview.md#the-mprovview-base-class-commonviewspy),
which gives every model endpoint CRUD (GET/POST/PATCH/DELETE; PUT rejected),
query-param filtering, and **docstring-as-documentation**: a non-JSON GET
returns the view's docstring rendered as Markdown, so `curl`ing an endpoint's
base URL is the way to read its live docs. `GET /` (index) lists the sections.

## Auth tiers

1. **API key or login** (default): `HasAPIKey | IsAuthenticated` —
   `Api-Key` header (created in admin) for machines, session/Basic/Token for
   humans. Used by nearly every endpoint, including [power control](/provisioning/pxe-boot-flow.md#power-control)
   and job claiming.
2. **No auth** (provisioning network only): `/ipxe/`, `/images/<slug>.<ext>`,
   `/osrepos/<pk>/...`, `systems/register`, and the index/`datamodel` views.
   These identify nodes by client IP and must answer before credentials exist.
3. **Self-service**: authenticated callers can use `?self` on `/systems/`
   (GET and POST) — mPCC resolves the System whose NIC/source-IP matches the
   request. This is how [genNetworkInterfaces.py and the stateful installer](/provisioning/pxe-boot-flow.md)
   read/write the record of the node they run on.

## Endpoint map

| Endpoint | View | Purpose |
|---|---|---|
| `/` | `IndexAPIView` | rendered API index (no auth) |
| `/datamodel/`, `?model=` | `DataTypeView` | list all registered models / reflect a model's JSON structure |
| `/systems/`, `/systems/<pk>/` | `SystemAPIView` | CRUD systems; `?self`, `?powerstate` (SVG icon) |
| `systems/register` | `SystemRegAPIView` | NADS zero-touch registration (no auth, POST) |
| `/systembmcs/` | `SystemBMCAPIView` | BMC records |
| `/networkinterfaces/` | `NetworkInterfaceAPIView` | NICs (`?system=<id>`) |
| `/systemgroups/` | `SystemGroupAPIView` | config groups |
| `/systemimages/` | `systems/systemimage_urls.py` | image CRUD; `?addjs` attaches a rebuilt jobserver host |
| `/images/<slug>.<ext>` | `ImagesAPIView` | no-auth redirect of vmlinuz/initramfs/img to least-loaded jobserver |
| `/networks/`, `/networktypes/`, `/switches/`, `/switchports/` | networks views | inventory CRUD |
| `/networks/<pk>/update-with-confirmation/` | `update_network_with_confirmation` | subnet change with explicit confirmation flow |
| `/networks/<pk>/preview-subnet-changes/` | `preview_subnet_changes` | dry-run IP proposal |
| `/distros/`, `/ostypes/`, `/repos/`, `/osrepos/` | osmanagement urls | distro/repo definitions; `/osrepos/<pk>/` redirects repo files to a hosting jobserver |
| `/jobs/`, `/jobmodules/`, `/jobservers/` | jobqueue urls | [job claim protocol](/provisioning/job-queue.md#claim-protocol-pull-not-push) |
| `/jobqueue/status-changes/` | `JobStatusChangesView` | drains recent status transitions for UI toasts |
| `/scripts/` | scripts urls | Script/File/Ansible artifact metadata; files served from media |
| `/power/<action>/` | `SystemPowerAPIView` | IPMI on/off/cycle/reset/status/pxe/pxeefi |
| `/ipxe/` | `IPXEAPIView` | no-auth iPXE script generation |

`/kernels/` exists in code but is commented out of the root URL map.

## Network subnet-change APIs

Renumbering a `Network` rewrites attached NIC/BMC addresses only with explicit
consent (`networks/api_views.py`):

- `POST /networks/<pk>/update-with-confirmation/` with
  `{network_data, update_associated}`. On a subnet/netmask change with
  `update_associated` omitted, it **writes nothing** and returns
  `{requires_confirmation, old_subnet, new_subnet, associated_objects}` —
  proposed IPs for every interface/BMC. Resend with `update_associated: true`
  to apply; the response reports `interfaces_updated`/`bmcs_updated`/errors.
- `GET /networks/<pk>/preview-subnet-changes/?new_subnet=&new_netmask=` — same
  proposal, never writes.
- `networks/utils.py::calculate_new_ip` keeps host octets and swaps network
  octets (validating membership, else first usable host). Note saving the
  Network also enqueues the usual pxe/dns/dhcp [jobs](/provisioning/job-queue.md).

## Machine-client conventions

- Job servers: heartbeat `POST /jobservers/`, poll/claim `/jobs/` (see
  [job queue](/provisioning/job-queue.md)).
- Nodes mid-provision: `Api-Key` from `/etc/mprov/script-runner.yaml` baked
  into images; PATCH attribution for anonymous callers maps to the admin user —
  don't rely on `created_by` granularity for machine writes.
- Introspection: `GET /datamodel/` lists model class names;
  `?model=systems.System` returns the field structure — useful for generating
  clients without reading serializers.

## Change guidance

New endpoints belong in the owning app's `*_urls.py` or root urls, subclass
`MProvView`, and must state their auth tier; adding to the no-auth tier is a
security decision (IP-based identity only).
