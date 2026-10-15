---
type: Reference
title: mProv Control Center — Quickstart
description: "Entry point for the mProv Control Center (mPCC) wiki: what the system is, how bare-metal provisioning works end to end, how the documentation is organized, and where to start changing it."
tags: [entrypoint, provisioning, bare-metal, django, overview]
---

# mProv Control Center (mPCC)

mPCC is the "brains" of the mProv bare-metal provisioning system (Johns Hopkins
ARCH). It is a Django 3.2 application that combines a Jazzmin-styled admin UI
with a REST/CRUD API, and it drives the provisioning of physical servers from
PXE boot through OS image delivery, disk installation, power control, and
post-boot scripting. Companion workers called **jobservers**
([mprov_jobserver](https://github.com/mprov-ng/mprov_jobserver)) pick up jobs
from mPCC's database-backed job queue and do the heavy lifting (building OS
images, syncing repos, updating PXE/DNS/DHCP configuration).

What mPCC does at a high level (see README.md):

- Authenticates operators (local users and optional LDAP) and API clients (API keys).
- Models the datacenter: systems, BMCs, NICs, switches/ports, networks, locations.
- Builds and hosts OS filesystem images and repositories via jobservers.
- Serves iPXE boot scripts and redirects nodes to jobservers for boot artifacts.
- Dispatches jobs (image rebuilds, repo syncs, PXE/DNS/DHCP updates) through a pull-based job queue.
- Controls power and netbooting of nodes over IPMI.

## The core loop, in one paragraph

An operator (or automation via the REST API) defines a
[Network, Switch, System, NIC, OSDistro, and SystemImage](/domain/data-models.md).
Saving these models fires Django signals that enqueue
[jobs](/provisioning/job-queue.md) — jobservers claim them, build the image, and
register themselves as hosts of the artifact. A node PXE-boots, DHCP points it
at mPCC's no-auth [`/ipxe/` endpoint](/provisioning/pxe-boot-flow.md), which
looks the node up by client IP, renders an iPXE script, and redirects the node
to the least-loaded jobserver for kernel/initrd/image. The initrd runs
`static/mprov_boot_init.sh`, downloads the image into tmpfs, and either
`switch_root`s into it (stateless) or runs the
[stateful disk installer](/provisioning/pxe-boot-flow.md#the-stateful-installer).
Unknown hardware self-registers through `systems/register` (Node Auto Detection,
NADS).

## Where to go next

| Page | What it covers |
|---|---|
| [Architecture Overview](/architecture/overview.md) | Django project layout, the `MProvView` API base class, settings/env vars, LDAP + API-key auth, the signal-as-event-bus pattern |
| [Data Models & Domain Concepts](/domain/data-models.md) | Every app's models, config inheritance (`OSDistro` < `SystemGroup` < `System`), and the relationship map |
| [PXE Boot & Provisioning Flow](/provisioning/pxe-boot-flow.md) | `/ipxe/`, image redirects, the busybox initrd scripts, stateful vs stateless installs, NADS registration, power control |
| [Job Queue & Jobservers](/provisioning/job-queue.md) | Job/JobModule/JobServer models, signal-driven job creation, pull-based claiming, artifact hosting bookkeeping |
| [REST API Surface](/api/rest-api.md) | Endpoint map, auth classes per endpoint, self-service `?self` access, network subnet-change confirmation, `datamodel/` introspection |
| [Deployment & Operations](/operations/deployment.md) | `install_mpcc.sh`/`init_mpcc.sh`, Docker images and compose stack, CI, backups, env var reference |

## Key conventions to know before editing

- **Slug-as-primary-key**: `SystemImage`, `SystemModel`, `SystemLocation`,
  `OSType`, `Script`, `JobModule`, `DiskLayout`, and the Ansible models use an
  auto-slugged `slug` as PK, not integers.
- **Inheritable config**: `install_kernel_cmdline`, `tmpfs_root_size`,
  `initial_mods`, `prov_interface`, and `config_params` are merged in
  `System.flatten_config()` with precedence distro → group → system; `#`
  comment lines mean "inherit", and a leading `=` means "overwrite instead of
  append".
- **Signals do the real work**: most jobs are created by `pre_save`/`post_save`
  receivers in `systems/models.py`, `networks/models.py`, and
  `osmanagement/models.py`, not by view code. Changing a model save path can
  silently change job creation.
- **The ORM is the integration point**: jobserver daemons, the stateful
  installer running inside a chroot, and external automation all talk to mPCC
  only through the REST API.
- **`static/` is part of the boot protocol**: the iPXE template injects files
  from `static/` (`mprov_boot.sh`, `mprov_boot_init.sh`, `busybox`,
  `mprov_stateful.py/.sh`, `genNetworkInterfaces.py`, udhcpc `default.script`)
  directly into the initrd. Recent git history is dominated by rework of these
  scripts (busybox-init boot process, EFI fixes for the stateful installer) —
  treat them as load-bearing, versioned-by-deployment boot code.

## Backlog

- `systems/admin.py` (597 lines) custom admin actions (bulk update with
  location, "Copy To New") — only skimmed; documented inline elsewhere.
- Ansible artifact execution semantics (playbooks/roles/collections ordering)
  live in the separate mprov_jobserver repo; not documented here.
- `install_scripts/install.d` plugin ordering and per-script env vars — noted
  in [Deployment](/operations/deployment.md) but not enumerated.
- `systems/kernels_urls.py` (`/kernels/`) is commented out of root urls;
  appears deprecated.
