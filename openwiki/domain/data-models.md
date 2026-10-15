---
type: Reference
title: Data Models and Domain Concepts
description: "Complete model reference for mProv Control Center: System, SystemBMC, NetworkInterface, Switch/SwitchPort, Network, OSDistro/OSRepo, SystemImage, Script and Ansible artifacts, DiskLayout, and the flatten_config inheritance chain from OSDistro through SystemGroup to System."
tags: [data-model, domain, models, inheritance, inventory]
---

# Data Models and Domain Concepts

mPCC's domain is a datacenter inventory plus the configuration needed to boot
and install those machines. Models live per app; the [architecture page](/architecture/overview.md)
covers how saves turn into jobs. Slug-as-primary-key and auto-slugging in
`save()` are pervasive.

## Systems app (`systems/models.py`)

**System** — a physical or virtual machine being provisioned. Key fields:
`hostname`, provenance `created_by` (user FK, `SET(1)` fallback), `stateful`
(bool — install images **to disk** vs run from RAM; drives the
[stateful installer](/provisioning/pxe-boot-flow.md#the-stateful-installer)),
FKs to `systemimage`, `systemmodel`, `location`, M2M to `systemgroups`,
`scripts`, and the three Ansible artifact types, M2M `disks` → DiskLayout.
Carries the five inheritable config fields (below). `flatten_config()` runs on
every load and builds the non-persistent `self.config` dict.

**SystemGroup** — mid-tier config bundle between distro and system; M2M to
systems and scripts/ansible artifacts; same inheritable fields. Use groups to
set per-cluster kernel args, modules, or config params without touching each
System.

**SystemBMC** (verbose "Power Management") — IPMI endpoint of a System:
`ipaddress`, `mac`, `ipv6ll`, `vlan`, IPMI `username`/`password`, optional
`switch_port`/`network`. Consumed by the [power API](/api/rest-api.md). A
companion form blanks empty password fields so editing a BMC never wipes the
stored password.

**NetworkInterface** — NIC of a System: `mac`, `ipaddress`, `ipv6ll`,
`ipv6gua`, `mtu`, `isgateway`, and `bootable` — the flag the
[NADS registration flow](/provisioning/pxe-boot-flow.md#node-auto-detection-nads) uses to
land a discovered MAC on the right NIC. Has a **OneToOne** to `SwitchPort`
(one gateway NIC per physical port) and FK to `Network`.

**SystemImage** — a built filesystem image: slugged PK, `osdistro` FK, M2M
`osrepos` (extra repos baked in), M2M `jobservers` ("Hosted By" — the
bookkeeping that lets `/images/` redirects pick a host), `needs_rebuild`
(setting it True fires the image-rebuild job and bumps `version`), `customIPXE`
(raw iPXE override; setting it disables image building). New images get the
`install_mprov_script_runner_sh` script by default.

**SystemModel** — dmidecode vendor/model pair (slugged `vendor name` PK) used
to validate [NADS](/provisioning/pxe-boot-flow.md#node-auto-detection-nads) self-registration.

**NADSSystem** — discovery holding pen for unknown MACs (unique `mac`,
switch/port/vendor/model/serial text). When an admin assigns it to a System,
a post_save receiver copies the MAC onto the System's bootable NIC and deletes
the row.

**SystemLocation** — slugged place record (`address`, `building`, `room`,
`rack`), referenced by `System.location` (added recently for inventory
tracking, git history shows issue #178).

## Networks app (`networks/models.py`)

**Network** — subnet with `vlan`, `subnet`, CIDR `netmask`, gateway/nameserver,
`domain`, DHCP range (`dhcpstart`/`dhcpend`), and feature flags `isdhcp`,
`managedns`, `isbootable`. Saves/deletes enqueue pxe/dns/dhcp update-or-delete
jobs. Subnet changes have dedicated confirmation APIs — see
[REST API](/api/rest-api.md#network-subnet-change-apis).

**NetworkType** — catalog of physical network kinds (fixture-loaded).

**Switch / SwitchPort** — switch inventory for NADS: Switch (`hostname`,
`mgmt_ip`, management `network`, `created_by`) with cascading SwitchPorts
(`name`, optional attached `networks`). A System reaches ports only through
its NICs and BMCs.

## OS management app (`osmanagement/models.py`)

**OSType** — category (e.g. RHEL-like). **OSDistro** — distro definition:
vendor/version/arch, `baseurl`, `baserepo` FK plus M2M `osrepos`/`extrarepos`
to **OSRepo**, root password (`rootpw`, default `changeme` — change it) and
`rootsshkeys` baked into images, and the distro-level defaults for the
inheritance chain (`tmpfs_root_size=8` GiB, `initial_mods="e1000,tg3"`,
`prov_interface="eth0"`). Setting `update=True` triggers a post_save hook that
auto-creates the standard RHEL-family repo set (`BaseOS-<ver>`,
`AppStream-<ver>`, `extras`, `CRB`/`PowerTools`, `EPEL`) then resets the flag.

**OSRepo** — a repository, optionally `managed` (mProv mirrors it locally).
Setting `update` on a managed repo bumps its `version`, enqueues a `repo-update`
job, and clears `hosted_by` so jobservers must re-host it; deleting a JobServer
re-queues repo updates for all repos so they migrate to survivors.

## Scripts app (`scripts/models.py`)

**Script** — shell snippets run at image-build time or post-boot, stored on
disk under `MEDIA_ROOT/<type-slug>/<slug>-v<version>`; uploads override
`content` and edited `content` is written back to disk, then the DB copy is
**cleared** — the filesystem is source of truth (job servers pull files via
media/`File` endpoints). **File** — generic versioned downloadable.
**AnsiblePlaybook / AnsibleRole / AnsibleCollection** — same versioned-media
pattern; roles/collections are git/galaxy URLs. Execution order by type:
collections → roles → playbooks. All four attach via M2M to System,
SystemGroup, SystemImage, and OSDistro.

## Disk layouts app (`disklayouts/models.py`)

**DiskLayout** (slugged PK) — geometry for one device (`diskname`, `dtype`
scsi/nvme/mdrd) with cascade `DiskPartition`s: `partnum`, `mount` (or literal
`raid` for MD members), `size` MB or `fill` (grow), `filesystem`, `bootable`,
`format` (force wipe vs wipe-if-empty). **RaidLayout** subclasses DiskLayout
(multi-table inheritance) with `raidlevel` and member partitions. Attached to
Systems via M2M and consumed by the stateful installer, which creates disks in
order: plain scsi/nvme layouts first, then MD RAIDs (see `disklayouts/notes.txt`).

## The config inheritance chain

Precedence **OSDistro < SystemGroup(s) < System**, implemented by
`System.flatten_config()` over `inheritableFields`:

- `install_kernel_cmdline`, `initial_mods` — append by default; a leading `=`
  on a child value means *replace* the parent value instead.
- `tmpfs_root_size` — int; child overrides only when non-zero (0 = inherit).
- `prov_interface`, `config_params` — plain override; `#` comment-only values
  (e.g. the default `"# Inherit from OS"`) mean "no value here, inherit".

The flattened result is what the [PXE view](/provisioning/pxe-boot-flow.md)
renders into the kernel cmdline, so debugging "why is my node booting this
way" starts here.

## Relationship map (summary)

```
Switch 1--N SwitchPort 1--1 NetworkInterface N--1 System N--1 SystemBMC
Network N--1 NetworkInterface / SystemBMC / Switch(mgmt)
OSDistro 1--N SystemImage N--M JobServer (hosting)
OSDistro N--M/N--1 OSRepo N--M JobServer (hosting)
OSDistro --(inherit)--> SystemGroup --(inherit)--> System
System N--1 SystemImage; System N--M DiskLayout 1--N DiskPartition
System N--1 SystemLocation / SystemModel; NADSSystem --> System (assignment)
Job N--1 JobModule; Job N--1 JobServer (nullable until claimed)
```
