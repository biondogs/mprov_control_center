---
type: Reference
title: PXE Boot and Provisioning Flow
description: "End-to-end bare-metal provisioning in mProv Control Center: the no-auth /ipxe/ endpoint, jobserver artifact redirects, busybox initrd boot scripts, stateless vs stateful installs with GRUB/EFI handling, NADS self-registration, and IPMI power control."
tags: [pxe, ipxe, boot, initrd, stateful, nads, ipmi, provisioning]
---

# PXE Boot and Provisioning Flow

This is the heart of mPCC: how a powered-off machine becomes a running (or
disk-installed) system. The flow spans the no-auth views in
`systems/views_noauth.py` and `systems/views.py`, the iPXE template in
`systems/templates/ipxe`, and the boot scripts in `static/` that are injected
into the initrd. All node-side behavior depends on [model fields](/domain/data-models.md)
resolved by `System.flatten_config()`.

## 1. Boot: `/ipxe/` (`IPXEAPIView`, no auth)

A node PXE-boots and DHCP hands it a URL to mPCC's `/ipxe/`. The view:

1. Takes the client IP (`X-Forwarded-For` first entry, else `REMOTE_ADDR`) and
   looks up `NetworkInterface` by that IP.
2. **Known node** — picks its `bootable=True` NIC; 404 if the System has no
   `SystemImage`.
3. **Unknown node (NADS path)** — no NIC match falls back to the magic image
   named `__nads__`, spoofing a NIC so the autodetect image boots instead.
4. Sets `nic.bootserver` to mPCC's own URL, appends `mprov_rescue=0|1`
   (`?rescue` enables a maintenance shell later), and for the `__nads__` image
   passes the provisioning interface *by name* instead of MAC.
5. **Dynamic templating quirk**: both `systemimage.customIPXE` (raw override,
   bypasses everything) and `osdistro.install_kernel_cmdline` are themselves
   rendered as Django templates with `nic` in context — kernel cmdlines can be
   data-driven.
6. Renders `systems/templates/ipxe`.

The template (gated on the NIC being bootable) sets the kernel cmdline
(`mprov_image_url`, `mprov_initial_mods`, `mprov_tmpfs_size`, stateful flags,
`mprov_prov_intf=${net0/mac}`), then fetches `/images/<slug>.vmlinuz` and
`.initramfs` **from mPCC**, and live-injects files into the initrd cpio before
`boot`:

| Injected to | From `static/` | Role |
|---|---|---|
| `/linuxrc` | `mprov_boot.sh` | PID-1 bootstrap → busybox init |
| `/mprov_boot_init.sh` | same | main provisioning logic |
| `/bin/busybox` | busybox binary (fetched at install time by `init_mpcc.sh`) | all applets |
| `/bin/default.script(6)` | udhcpc scripts | DHCP handling |
| `/tmp/mprov_stateful.py`, `/tmp/mprov_stateful.sh` | same | only when `mprov_stateful=1` |

## 2. Artifact redirects: `/images/<slug>.<ext>` (`ImagesAPIView`, no auth)

mPCC does not store images; it **302-redirects** the node to a jobserver:
`getJobserver()` orders `image.jobservers` by `one_minute_load` (see
[job queue](/provisioning/job-queue.md)), health-checks the URL with a HEAD
request, drops dead jobservers from the M2M, and retries. `/osrepos/<pk>/...`
(`osmanagement/views_noath.py`) does the same with a *random* hosting jobserver
for repos. This is why `SystemImage.jobservers` and `OSRepo.hosted_by` are
cleared on version bumps — stale hosts must re-register via
`PATCH /systemimages/<slug>?addjs` after rebuilding.

## 3. Initrd boot scripts (`static/`)

`mprov_boot.sh` (`/linuxrc`): mounts proc/sys/devtmpfs, `busybox --install`,
writes inittab (`tty1` respawns `mprov_boot_init.sh`, `tty2` gives a debug
shell), `exec /bin/init`.

`mprov_boot_init.sh` — the real work:

1. Parses the kernel cmdline into env (`MPROV_TMPFS_SIZE`, `MPROV_IMAGE_URL`,
   `MPROV_INITIAL_MODS`, `MPROV_PROV_INTF`, `MPROV_STATEFUL`,
   `MPROV_BOOTDISK`, `MPROV_RESCUE`).
2. Loads all PCI NIC (class 0x02) and storage (0x01, ahci/nvme/virtio) drivers;
   records them into the image's `dracut.conf.d` so the installed system keeps
   them.
3. Finds the provisioning NIC **by MAC**, `udhcpc` for an address.
4. Mounts a tmpfs of `MPROV_TMPFS_SIZE` at `/image` and downloads the OS
   tarball: `wget $MPROV_IMAGE_URL | gunzip | tar -x` (the redirect above lands
   on a jobserver `.img`).
5. For non-NADS images, wgets `genNetworkInterfaces.py` and runs it chrooted —
   it pulls the node's [NIC/network records](/domain/data-models.md) over the
   API (`GET systems/?self`, `/networkinterfaces/?system=<id>`) and writes
   `ifcfg-*` files + `/etc/hostname` inside the image.
6. Branches on `MPROV_STATEFUL`.

**Stateless**: symlink `/sbin/init → /image/init` and SIGQUIT PID 1 so busybox
init `switch_root`s into the tmpfs — the RAM image *is* the OS; every reboot
re-provisions.

**Stateless rescue** (`?rescue`): early/maintenance shell instead of booting.

## The stateful installer

When `System.stateful` is true, the cmdline carries
`mprov_stateful=1 mprov_bootdisk=<diskname>` and the initrd runs
`chroot /image /tmp/mprov_stateful.sh` → `mprov_stateful.py`
(`mProvStatefulInstaller`), which authenticates to mPCC with an API key read
from `/etc/mprov/script-runner.yaml` bundled in the image:

1. `buildDisks` — `GET systems/?self` for the attached [DiskLayouts](/domain/data-models.md);
   wipes GPT on the boot disk, auto-creates biosboot (1 MiB) + 100 MiB EFI vfat
   (`/boot/efi`) partitions, then builds layout partitions (`fill` = rest of
   disk) with fixed UUIDs; honors `format: False` to preserve filesystems.
2. `buildRAIDs` — `mdadm --create` for `mdrd` layouts.
3. `mountDisks` / `copyRoot` — mount fstab under `/newroot`, `rsync -arx / /newroot`,
   merge fstab, `restorecon`.
4. `installBootLoader` — strips mprov args from the kernel cmdline, sets
   `root=<UUID>` + `rd.md/rd.auto`, regenerates initramfs with dracut
   (`--mdadmconf`), then UEFI: reinstall shim/grub2-efi and create the NVRAM
   entry explicitly with `efibootmgr` (the RPM %posttrans is a no-op chroot);
   BIOS: `grub2-install` + `grub2-mkconfig`. Git history shows this area is the
   most recently fixed code (EFI setup, reboot-to-verify).
5. `cleanupAndSwitchroot` — **POST `systems/?self` with `{"netboot": false}`**
   so mPCC marks all the node's NICs non-bootable (it won't PXE again); then
   the outer script hard-reboots (`sysrq b`) into the disk. Rescue mode drops
   to a maintenance shell instead.

## Node Auto Detection (NADS)

Zero-touch discovery (`systems/register`, `SystemRegAPIView`, no auth, POST):
a booting unknown node (the `__nads__` image) posts
`{vendor, model, switch, port, mac, serial}`. If a pre-modeled MAC-less NIC
exists on that switch port *and* the `SystemModel` slug matches
`slugify("vendor model")`, the MAC is stamped onto the bootable NIC, an EUI-64
`ipv6ll` (and `ipv6gua` when the port's network has IPv6) is generated, and a
`pxe-update` job is queued. Otherwise the MAC is parked in `NADSSystem` for an
admin to assign later (assignment auto-copies the MAC and deletes the row).
Network-side [subnet renumbering helpers](/domain/data-models.md) share the
IP-assignment utilities in `networks/utils.py`.

## Power control

`/power/<action>/` (`SystemPowerAPIView`, requires API key or login, GET only)
drives BMCs via pyipmi over `ipmitool` lanplus: `on|off|cycle|reset|status`,
plus `pxe`/`pxeefi` which shell out to
`ipmitool ... chassis bootdev pxe [options=efiboot]` then reset — this is
"netboot this node now". Selection is by `?hostname=`, `?id=`, or generic
`SystemBMC` field filters. `GET /systems/?powerstate` returns power-state SVG
icons for the UI (1-second timeout per BMC).

## Watch out for

- These views match nodes **by client IP only** and are unauthenticated — mPCC
  is expected to live on a provisioning network.
- A latent bug exists in the multi-NIC/non-bootable early-return branch of
  `IPXEAPIView` (`template.render` before `context` is defined).
- `static/` boot scripts are deployed verbatim; there is no schema/versioning
  between initrd script and mPCC — keep both sides in sync when changing API
  payloads like `systems/?self`.
